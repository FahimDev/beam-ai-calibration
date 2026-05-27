from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from beam_ai.config import settings
from beam_ai.db.models import (
    AIAnalysisResult,
    CalibrationStatus,
    CameraCalibration,
    CameraType,
    RecommendationMode,
    SafetyStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CalibrationCheck — return value of check_calibration()
# ---------------------------------------------------------------------------

@dataclass
class CalibrationCheck:
    device_id: str
    bp_status: CalibrationStatus
    bd_status: CalibrationStatus
    bp_expiry: datetime | None
    bd_expiry: datetime | None
    overall:   CalibrationStatus
    blocking:  bool

    @property
    def message(self) -> str:
        if self.overall == CalibrationStatus.VALID:
            return "Calibration valid."
        if self.overall == CalibrationStatus.EXPIRED:
            return (
                f"Calibration EXPIRED — "
                f"BP: {self.bp_status.value} "
                f"(expires {self.bp_expiry}), "
                f"BD: {self.bd_status.value} "
                f"(expires {self.bd_expiry})."
            )
        return (
            "Calibration status UNKNOWN — "
            "no calibration record found for one or both cameras. "
            "Open Measuring Device Settings to register calibration."
        )


# ---------------------------------------------------------------------------
# Precedence helper
# ---------------------------------------------------------------------------

_STATUS_RANK: dict[CalibrationStatus, int] = {
    CalibrationStatus.VALID:   0,
    CalibrationStatus.EXPIRED: 1,
    CalibrationStatus.UNKNOWN: 2,   # worst
}


def _worst(a: CalibrationStatus, b: CalibrationStatus) -> CalibrationStatus:
    """Return whichever status is worse: UNKNOWN > EXPIRED > VALID."""
    return a if _STATUS_RANK[a] >= _STATUS_RANK[b] else b


# ---------------------------------------------------------------------------
# Internal: resolve one camera's latest calibration record
# ---------------------------------------------------------------------------

def _resolve(
    cal: CameraCalibration | None,
    now: datetime,
) -> tuple[CalibrationStatus, datetime | None]:
    """
    Given the most recent CameraCalibration row (or None),
    return (status, expiry_date).
    """
    if cal is None:
        return CalibrationStatus.UNKNOWN, None
    if cal.expiry_date < now:
        return CalibrationStatus.EXPIRED, cal.expiry_date
    return CalibrationStatus.VALID, cal.expiry_date


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_latest_calibration(
    db: DBSession,
    device_id: str,
    camera: CameraType,
) -> CameraCalibration | None:
    """Return the most recent calibration row for a device+camera pair."""
    stmt = (
        select(CameraCalibration)
        .where(
            CameraCalibration.measuring_device_id == device_id,
            CameraCalibration.camera_type == camera,
        )
        .order_by(CameraCalibration.calibration_date.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def check_calibration(
    db: DBSession,
    device_id: str,
    now: datetime | None = None,
) -> CalibrationCheck:
    """
    Check BP and BD calibration status for a measuring device.

    Args:
        db:        SQLAlchemy session.
        device_id: MeasuringDevice primary key.
        now:       Reference time (injectable for testing). Defaults to utcnow.

    Returns:
        CalibrationCheck with per-camera status and overall blocking flag.
    """
    now = now or datetime.utcnow()

    bp_cal = get_latest_calibration(db, device_id, CameraType.BP)
    bd_cal = get_latest_calibration(db, device_id, CameraType.BD)

    bp_status, bp_expiry = _resolve(bp_cal, now)
    bd_status, bd_expiry = _resolve(bd_cal, now)

    overall  = _worst(bp_status, bd_status)
    blocking = overall != CalibrationStatus.VALID

    logger.debug(
        "calibration_check device=%s bp=%s bd=%s overall=%s blocking=%s",
        device_id, bp_status.value, bd_status.value, overall.value, blocking,
    )

    return CalibrationCheck(
        device_id=device_id,
        bp_status=bp_status,
        bd_status=bd_status,
        bp_expiry=bp_expiry,
        bd_expiry=bd_expiry,
        overall=overall,
        blocking=blocking,
    )


def register_calibration(
    db: DBSession,
    *,
    calibration_id: str,
    device_id: str,
    camera: CameraType,
    calibration_date: datetime,
    pixel_scale_x: float | None = None,   # assumption: µm/pixel
    pixel_scale_y: float | None = None,   # assumption: µm/pixel
    validity_days: int | None = None,
    updated_by: str | None = None,
    version: str = "v1",
    file_path: str | None = None,
) -> CameraCalibration:
    """
    Register a new calibration record for one camera on a measuring device.

    Args:
        calibration_id:   ULID string (caller provides).
        device_id:        FK to MeasuringDevice.
        camera:           CameraType.BP or CameraType.BD.
        calibration_date: When calibration was performed.
        pixel_scale_x/y:  Physical scale in µm/pixel (assumption — confirm).
        validity_days:    Override default from settings.
        updated_by:       Operator or technician ID.
        version:          Calibration procedure version string.
        file_path:        Path to calibration file if available.

    Returns:
        Committed CameraCalibration row.

    Raises:
        sqlalchemy.exc.IntegrityError: if device_id does not exist.
    """
    days    = validity_days or settings.default_calibration_validity_days
    expiry  = calibration_date + timedelta(days=days)

    cal = CameraCalibration(
        calibration_id      = calibration_id,
        measuring_device_id = device_id,
        camera_type         = camera,
        calibration_date    = calibration_date,
        expiry_date         = expiry,
        status              = CalibrationStatus.VALID,
        pixel_scale_x       = pixel_scale_x,
        pixel_scale_y       = pixel_scale_y,
        calibration_file    = file_path,
        calibration_version = version,
        updated_by          = updated_by,
    )

    db.add(cal)
    db.commit()
    db.refresh(cal)

    logger.info(
        "calibration_registered device=%s camera=%s expires=%s",
        device_id, camera.value, expiry.date(),
    )

    return cal


def gate_ai_result(
    db: DBSession,
    device_id: str,
    ai_result: AIAnalysisResult,
    now: datetime | None = None,
) -> AIAnalysisResult:
    """
    Enforce calibration ledger on an AIAnalysisResult before it is committed.

    MUST be called before every AIAnalysisResult db.add() / db.commit().
    Never bypass this function.

    Mutations applied to ai_result:
    - calibration_status_used ← overall calibration status
    - recommendation_mode     ← NONE if blocking, else SHADOW
    - safety_status           ← BLOCK if blocking, else unchanged
    - recommendation_text     ← [BLOCKED] reason appended if blocking

    NOTE: This function never sets recommendation_mode = FSE_REVIEW.
          Only an explicit FSE action in the UI may set FSE_REVIEW.

    Returns:
        The mutated AIAnalysisResult (same object, not a copy).
    """
    check = check_calibration(db, device_id, now=now)

    ai_result.calibration_status_used = check.overall

    if check.blocking:
        ai_result.recommendation_mode = RecommendationMode.NONE
        ai_result.safety_status       = SafetyStatus.BLOCK
        existing_text                 = ai_result.recommendation_text or ""
        ai_result.recommendation_text = (
            f"{existing_text}\n[BLOCKED] {check.message}".strip()
        )
        logger.warning(
            "ai_result_blocked history_id=%s reason=%s",
            ai_result.history_id, check.message,
        )
    else:
        # minimum safe mode — never auto-promote to FSE_REVIEW
        if ai_result.recommendation_mode == RecommendationMode.NONE:
            ai_result.recommendation_mode = RecommendationMode.SHADOW

    return ai_result