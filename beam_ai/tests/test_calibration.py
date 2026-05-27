"""
Tests for beam_ai/ledger/calibration.py
Covers all 12 acceptance criteria from specs/features/calibration_ledger.md
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from beam_ai.db.base import Base
from beam_ai.db.models import (
    AIAnalysisResult,
    CalibrationStatus,
    CameraType,
    MeasuringDevice,
    RecommendationMode,
    SafetyStatus,
)
from beam_ai.ledger.calibration import (
    CalibrationCheck,
    check_calibration,
    gate_ai_result,
    register_calibration,
)


# ---------------------------------------------------------------------------
# Test DB setup — SQLite in-memory, isolated per test
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture()
def db():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_fk_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def device(db):
    """Insert a MeasuringDevice row and return its ID."""
    dev = MeasuringDevice(
        measuring_device_id="md_test_01",
        name="Test Device",
        bp_camera_id="bp_cam_01",
        bd_camera_id="bd_cam_01",
    )
    db.add(dev)
    db.commit()
    return dev.measuring_device_id


NOW = datetime(2024, 6, 1, 12, 0, 0)
PAST = NOW - timedelta(days=200)    # clearly expired
FUTURE = NOW + timedelta(days=30)   # clearly valid


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _register_both(db, device_id, cal_date, validity_days=90):
    """Register BP and BD calibrations on the same date."""
    register_calibration(
        db,
        calibration_id=f"cal_bp_{cal_date.date()}",
        device_id=device_id,
        camera=CameraType.BP,
        calibration_date=cal_date,
        validity_days=validity_days,
    )
    register_calibration(
        db,
        calibration_id=f"cal_bd_{cal_date.date()}",
        device_id=device_id,
        camera=CameraType.BD,
        calibration_date=cal_date,
        validity_days=validity_days,
    )


def _make_ai_result(history_id: str = "hist_001") -> AIAnalysisResult:
    return AIAnalysisResult(
        ai_result_id                  = f"ai_{history_id}",
        history_id                    = history_id,
        model_version                 = "rf_baseline_v0",
        recommendation_mode           = RecommendationMode.NONE,
        safety_status                 = SafetyStatus.OK,
        calibration_status_used       = CalibrationStatus.UNKNOWN,
        extracted_feature_set_version = "v0",
    )


# ---------------------------------------------------------------------------
# AC-01: register creates row with correct expiry
# ---------------------------------------------------------------------------

def test_ac01_register_creates_row_with_correct_expiry(db, device):
    cal = register_calibration(
        db,
        calibration_id   = "cal_bp_001",
        device_id        = device,
        camera           = CameraType.BP,
        calibration_date = NOW,
        validity_days    = 90,
    )
    assert cal.calibration_id == "cal_bp_001"
    assert cal.expiry_date    == NOW + timedelta(days=90)
    assert cal.status         == CalibrationStatus.VALID


# ---------------------------------------------------------------------------
# AC-02: both cameras valid → overall VALID
# ---------------------------------------------------------------------------

def test_ac02_both_valid(db, device):
    _register_both(db, device, FUTURE)
    result = check_calibration(db, device, now=NOW)
    assert result.overall  == CalibrationStatus.VALID
    assert result.blocking is False


# ---------------------------------------------------------------------------
# AC-03: one camera expired → overall EXPIRED
# ---------------------------------------------------------------------------

def test_ac03_one_expired(db, device):
    register_calibration(
        db,
        calibration_id   = "cal_bp_ok",
        device_id        = device,
        camera           = CameraType.BP,
        calibration_date = FUTURE,
        validity_days    = 90,
    )
    register_calibration(
        db,
        calibration_id   = "cal_bd_old",
        device_id        = device,
        camera           = CameraType.BD,
        calibration_date = PAST,
        validity_days    = 90,
    )
    result = check_calibration(db, device, now=NOW)
    assert result.bd_status == CalibrationStatus.EXPIRED
    assert result.overall   == CalibrationStatus.EXPIRED
    assert result.blocking  is True


# ---------------------------------------------------------------------------
# AC-04: no calibration at all → UNKNOWN
# ---------------------------------------------------------------------------

def test_ac04_no_calibration_returns_unknown(db, device):
    result = check_calibration(db, device, now=NOW)
    assert result.overall  == CalibrationStatus.UNKNOWN
    assert result.blocking is True


# ---------------------------------------------------------------------------
# AC-05: one camera unknown, other valid → overall UNKNOWN (precedence)
# ---------------------------------------------------------------------------

def test_ac05_unknown_beats_valid(db, device):
    register_calibration(
        db,
        calibration_id   = "cal_bp_valid",
        device_id        = device,
        camera           = CameraType.BP,
        calibration_date = FUTURE,
        validity_days    = 90,
    )
    # BD has no record → UNKNOWN
    result = check_calibration(db, device, now=NOW)
    assert result.bp_status == CalibrationStatus.VALID
    assert result.bd_status == CalibrationStatus.UNKNOWN
    assert result.overall   == CalibrationStatus.UNKNOWN
    assert result.blocking  is True


# ---------------------------------------------------------------------------
# AC-06: gate blocks when EXPIRED
# ---------------------------------------------------------------------------

def test_ac06_gate_blocks_expired(db, device):
    register_calibration(
        db,
        calibration_id   = "cal_bp_exp",
        device_id        = device,
        camera           = CameraType.BP,
        calibration_date = PAST,
        validity_days    = 90,
    )
    register_calibration(
        db,
        calibration_id   = "cal_bd_exp",
        device_id        = device,
        camera           = CameraType.BD,
        calibration_date = PAST,
        validity_days    = 90,
    )
    ai = _make_ai_result()
    gate_ai_result(db, device, ai)

    assert ai.recommendation_mode     == RecommendationMode.NONE
    assert ai.safety_status           == SafetyStatus.BLOCK
    assert ai.calibration_status_used == CalibrationStatus.EXPIRED
    assert "[BLOCKED]" in (ai.recommendation_text or "")


# ---------------------------------------------------------------------------
# AC-07: gate blocks when UNKNOWN
# ---------------------------------------------------------------------------

def test_ac07_gate_blocks_unknown(db, device):
    ai = _make_ai_result()
    gate_ai_result(db, device, ai)

    assert ai.recommendation_mode     == RecommendationMode.NONE
    assert ai.safety_status           == SafetyStatus.BLOCK
    assert ai.calibration_status_used == CalibrationStatus.UNKNOWN
    assert "[BLOCKED]" in (ai.recommendation_text or "")


# ---------------------------------------------------------------------------
# AC-08: gate sets SHADOW when VALID
# ---------------------------------------------------------------------------

def test_ac08_gate_sets_shadow_when_valid(db, device):
    _register_both(db, device, FUTURE)
    ai = _make_ai_result()
    gate_ai_result(db, device, ai, now=NOW)

    assert ai.recommendation_mode     == RecommendationMode.SHADOW
    assert ai.calibration_status_used == CalibrationStatus.VALID
    assert ai.safety_status           == SafetyStatus.OK


# ---------------------------------------------------------------------------
# AC-09: gate never sets FSE_REVIEW
# ---------------------------------------------------------------------------

def test_ac09_gate_never_sets_fse_review(db, device):
    _register_both(db, device, FUTURE)
    ai = _make_ai_result()
    gate_ai_result(db, device, ai)

    assert ai.recommendation_mode != RecommendationMode.FSE_REVIEW


# ---------------------------------------------------------------------------
# AC-10: gate appends [BLOCKED] to existing recommendation_text
# ---------------------------------------------------------------------------

def test_ac10_blocked_appends_to_existing_text(db, device):
    ai = _make_ai_result()
    ai.recommendation_text = "Some prior text."
    gate_ai_result(db, device, ai)

    assert "Some prior text." in ai.recommendation_text
    assert "[BLOCKED]"        in ai.recommendation_text


# ---------------------------------------------------------------------------
# AC-11: injectable `now` — same calibration valid at T, expired at T+91d
# ---------------------------------------------------------------------------

def test_ac11_injectable_now(db, device):
    _register_both(db, device, NOW, validity_days=90)

    result_valid = check_calibration(db, device, now=NOW + timedelta(days=1))
    assert result_valid.overall == CalibrationStatus.VALID

    result_expired = check_calibration(db, device, now=NOW + timedelta(days=91))
    assert result_expired.overall == CalibrationStatus.EXPIRED


# ---------------------------------------------------------------------------
# AC-12: register raises IntegrityError for unknown device_id
# ---------------------------------------------------------------------------

def test_ac12_unknown_device_raises(db):
    with pytest.raises(Exception):   # IntegrityError or similar FK violation
        register_calibration(
            db,
            calibration_id   = "cal_bad",
            device_id        = "nonexistent_device",
            camera           = CameraType.BP,
            calibration_date = NOW,
        )