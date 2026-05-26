from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from beam_ai.db.base import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BeamMode(str, enum.Enum):
    AMP  = "AMP"
    OSC  = "OSC"
    TWIN = "Twin"


class SessionType(str, enum.Enum):
    CURRENT       = "current"
    PREVIOUS      = "previous"
    BEST_PRACTICE = "best_practice"


class SessionStatus(str, enum.Enum):
    OPEN   = "open"
    CLOSED = "closed"


class CameraType(str, enum.Enum):
    BP = "BP"
    BD = "BD"


class SaveTrigger(str, enum.Enum):
    MANUAL           = "manual"
    BEAM_MODE_CHANGE = "beam_mode_change"
    INTERVAL         = "interval"
    SYNTHETIC        = "synthetic"


class EvalResult(str, enum.Enum):
    OK = "OK"
    NG = "NG"


class EvalLabel(str, enum.Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class CalibrationStatus(str, enum.Enum):
    VALID   = "valid"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class RecommendationMode(str, enum.Enum):
    NONE       = "none"
    SHADOW     = "shadow"
    FSE_REVIEW = "fse_review"


class SafetyStatus(str, enum.Enum):
    OK   = "ok"
    WARN = "warn"
    BLOCK = "block"


# ---------------------------------------------------------------------------
# MeasuringDevice
# ---------------------------------------------------------------------------

class MeasuringDevice(Base):
    __tablename__ = "measuring_device"

    measuring_device_id: Mapped[str] = mapped_column(String, primary_key=True)
    name:                Mapped[str] = mapped_column(String, nullable=False)
    bp_camera_id:        Mapped[str] = mapped_column(String, nullable=False)
    bd_camera_id:        Mapped[str] = mapped_column(String, nullable=False)
    device_status:       Mapped[str] = mapped_column(String, default="active")

    calibrations: Mapped[list[CameraCalibration]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[Session]] = relationship(
        back_populates="device",
    )


# ---------------------------------------------------------------------------
# CameraCalibration
# ---------------------------------------------------------------------------

class CameraCalibration(Base):
    __tablename__ = "camera_calibration"

    calibration_id:      Mapped[str]               = mapped_column(String, primary_key=True)
    measuring_device_id: Mapped[str]               = mapped_column(
        ForeignKey("measuring_device.measuring_device_id"), nullable=False
    )
    camera_type:         Mapped[CameraType]         = mapped_column(Enum(CameraType), nullable=False)
    calibration_date:    Mapped[datetime]           = mapped_column(DateTime, nullable=False)
    expiry_date:         Mapped[datetime]           = mapped_column(DateTime, nullable=False)
    status:              Mapped[CalibrationStatus]  = mapped_column(
        Enum(CalibrationStatus), default=CalibrationStatus.UNKNOWN
    )
    # assumption: µm/pixel — unit must be confirmed with hardware team
    pixel_scale_x:       Mapped[float | None]       = mapped_column(Float, nullable=True)
    pixel_scale_y:       Mapped[float | None]       = mapped_column(Float, nullable=True)
    calibration_file:    Mapped[str | None]         = mapped_column(String, nullable=True)
    calibration_version: Mapped[str]                = mapped_column(String, default="v0")
    updated_by:          Mapped[str | None]         = mapped_column(String, nullable=True)

    device: Mapped[MeasuringDevice] = relationship(back_populates="calibrations")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "session"

    session_id:          Mapped[str]           = mapped_column(String, primary_key=True)
    session_type:        Mapped[SessionType]   = mapped_column(Enum(SessionType), nullable=False)
    laser_id:            Mapped[str]           = mapped_column(String, nullable=False, index=True)
    measuring_device_id: Mapped[str]           = mapped_column(
        ForeignKey("measuring_device.measuring_device_id"), nullable=False
    )
    started_at:  Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    ended_at:    Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    status:      Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.OPEN
    )
    notes_title: Mapped[str|None]  = mapped_column(String, nullable=True)
    notes_body:  Mapped[str|None]  = mapped_column(Text, nullable=True)

    # constraint: only one open session per laser at a time
    __table_args__ = (
        UniqueConstraint(
            "laser_id", "status",
            name="uq_session_laser_open",
            # partial unique handled in service layer for postgres
        ),
    )

    device:    Mapped[MeasuringDevice]  = relationship(back_populates="sessions")
    histories: Mapped[list[HistoryItem]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="HistoryItem.saved_at",
    )


# ---------------------------------------------------------------------------
# HistoryItem
# ---------------------------------------------------------------------------

class HistoryItem(Base):
    __tablename__ = "history_item"

    history_id:   Mapped[str]         = mapped_column(String, primary_key=True)
    session_id:   Mapped[str]         = mapped_column(
        ForeignKey("session.session_id"), nullable=False
    )
    beam_mode:    Mapped[BeamMode]    = mapped_column(Enum(BeamMode), nullable=False)
    saved_at:     Mapped[datetime]    = mapped_column(DateTime, default=datetime.utcnow)
    save_trigger: Mapped[SaveTrigger] = mapped_column(Enum(SaveTrigger), nullable=False)
    notes_title:  Mapped[str|None]    = mapped_column(String, nullable=True)
    notes_body:   Mapped[str|None]    = mapped_column(Text, nullable=True)
    has_evaluation: Mapped[bool]      = mapped_column(Boolean, default=False)
    snapshot_path:  Mapped[str|None]  = mapped_column(String, nullable=True)

    session:    Mapped[Session]             = relationship(back_populates="histories")
    images:     Mapped[list[BeamImage]]     = relationship(
        back_populates="history", cascade="all, delete-orphan"
    )
    outputs:    Mapped[list[Output]]        = relationship(
        back_populates="history", cascade="all, delete-orphan"
    )
    condition:  Mapped[Condition|None]      = relationship(
        back_populates="history", uselist=False, cascade="all, delete-orphan"
    )
    evaluation: Mapped[Evaluation|None]     = relationship(
        back_populates="history", uselist=False, cascade="all, delete-orphan"
    )
    ai_result:  Mapped[AIAnalysisResult|None] = relationship(
        back_populates="history", uselist=False, cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# BeamImage
# ---------------------------------------------------------------------------

class BeamImage(Base):
    __tablename__ = "beam_image"

    image_id:             Mapped[str]        = mapped_column(String, primary_key=True)
    history_id:           Mapped[str]        = mapped_column(
        ForeignKey("history_item.history_id"), nullable=False
    )
    camera_type:          Mapped[CameraType] = mapped_column(Enum(CameraType), nullable=False)
    image_path:           Mapped[str]        = mapped_column(String, nullable=False)
    # assumption: 16-bit grayscale PNG — confirm with hardware team
    image_format:         Mapped[str]        = mapped_column(String, default="png16")
    width_px:             Mapped[int]        = mapped_column(Integer, nullable=False)
    height_px:            Mapped[int]        = mapped_column(Integer, nullable=False)
    intensity_min:        Mapped[float]      = mapped_column(Float, nullable=False)
    intensity_max:        Mapped[float]      = mapped_column(Float, nullable=False)
    preprocessing_version: Mapped[str]       = mapped_column(String, default="v0")

    history: Mapped[HistoryItem] = relationship(back_populates="images")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

class Output(Base):
    __tablename__ = "output"

    output_id:      Mapped[str]        = mapped_column(String, primary_key=True)
    history_id:     Mapped[str]        = mapped_column(
        ForeignKey("history_item.history_id"), nullable=False
    )
    camera_type:    Mapped[CameraType] = mapped_column(Enum(CameraType), nullable=False)
    # all output fields nullable — formula not confirmed, filled by extractor
    cog_x:          Mapped[float|None] = mapped_column(Float, nullable=True)
    cog_y:          Mapped[float|None] = mapped_column(Float, nullable=True)
    size_hor:       Mapped[float|None] = mapped_column(Float, nullable=True)
    size_ver:       Mapped[float|None] = mapped_column(Float, nullable=True)
    intensity_mean: Mapped[float|None] = mapped_column(Float, nullable=True)
    intensity_max:  Mapped[float|None] = mapped_column(Float, nullable=True)
    intensity_std:  Mapped[float|None] = mapped_column(Float, nullable=True)
    uniformity:     Mapped[float|None] = mapped_column(Float, nullable=True)
    symmetry:       Mapped[float|None] = mapped_column(Float, nullable=True)
    contm_hor:      Mapped[float|None] = mapped_column(Float, nullable=True)
    contm_ver:      Mapped[float|None] = mapped_column(Float, nullable=True)

    history: Mapped[HistoryItem] = relationship(back_populates="outputs")


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------

class Condition(Base):
    __tablename__ = "condition"

    condition_id:          Mapped[str]      = mapped_column(String, primary_key=True)
    history_id:            Mapped[str]      = mapped_column(
        ForeignKey("history_item.history_id"), unique=True, nullable=False
    )
    beam_mode:             Mapped[BeamMode] = mapped_column(Enum(BeamMode), nullable=False)
    roi_x:                 Mapped[int|None] = mapped_column(Integer, nullable=True)
    roi_y:                 Mapped[int|None] = mapped_column(Integer, nullable=True)
    roi_width:             Mapped[int|None] = mapped_column(Integer, nullable=True)
    roi_height:            Mapped[int|None] = mapped_column(Integer, nullable=True)
    threshold:             Mapped[float|None] = mapped_column(Float, nullable=True)
    exposure:              Mapped[float|None] = mapped_column(Float, nullable=True)
    gain:                  Mapped[float|None] = mapped_column(Float, nullable=True)
    crosshair_visible:     Mapped[bool]     = mapped_column(Boolean, default=True)
    graph_overlay_enabled: Mapped[bool]     = mapped_column(Boolean, default=True)

    history: Mapped[HistoryItem] = relationship(back_populates="condition")


# ---------------------------------------------------------------------------
# Evaluation  — beam_mode MUST be TWIN (enforced in service layer)
# ---------------------------------------------------------------------------

class Evaluation(Base):
    __tablename__ = "evaluation"

    evaluation_id: Mapped[str]            = mapped_column(String, primary_key=True)
    history_id:    Mapped[str]            = mapped_column(
        ForeignKey("history_item.history_id"), unique=True, nullable=False
    )
    # invariant: beam_mode must always be TWIN — reject at service layer
    beam_mode:     Mapped[BeamMode]       = mapped_column(Enum(BeamMode), nullable=False)
    result:        Mapped[EvalResult]     = mapped_column(Enum(EvalResult), nullable=False)
    # score 0–100 per Gen 1 scoring sheet — formula not fully confirmed
    score:         Mapped[float|None]     = mapped_column(Float, nullable=True)
    label:         Mapped[EvalLabel|None] = mapped_column(Enum(EvalLabel), nullable=True)
    # DTL-sourced values — units must be confirmed with hardware team
    energy:        Mapped[float|None]     = mapped_column(Float, nullable=True)
    energy_sigma:  Mapped[float|None]     = mapped_column(Float, nullable=True)
    dose_hk:       Mapped[float|None]     = mapped_column(Float, nullable=True)
    wavelength:    Mapped[float|None]     = mapped_column(Float, nullable=True)
    hv:            Mapped[float|None]     = mapped_column(Float, nullable=True)
    f2_pressure:   Mapped[float|None]     = mapped_column(Float, nullable=True)

    history: Mapped[HistoryItem] = relationship(back_populates="evaluation")


# ---------------------------------------------------------------------------
# AIAnalysisResult
# ---------------------------------------------------------------------------

class AIAnalysisResult(Base):
    __tablename__ = "ai_analysis_result"

    ai_result_id:                Mapped[str]                = mapped_column(String, primary_key=True)
    history_id:                  Mapped[str]                = mapped_column(
        ForeignKey("history_item.history_id"), unique=True, nullable=False
    )
    model_version:               Mapped[str]                = mapped_column(String, nullable=False)
    prediction_label:            Mapped[str|None]           = mapped_column(String, nullable=True)
    confidence:                  Mapped[float|None]         = mapped_column(Float, nullable=True)
    extracted_feature_set_version: Mapped[str]              = mapped_column(String, default="v0")
    # soft FK — may reference a HistoryItem in another session or future Vector DB
    nearest_case_id:             Mapped[str|None]           = mapped_column(String, nullable=True)
    recommendation_text:         Mapped[str|None]           = mapped_column(Text, nullable=True)
    # NEVER set to fse_review by code — only by explicit FSE action
    recommendation_mode:         Mapped[RecommendationMode] = mapped_column(
        Enum(RecommendationMode), default=RecommendationMode.NONE
    )
    safety_status:               Mapped[SafetyStatus]       = mapped_column(
        Enum(SafetyStatus), default=SafetyStatus.OK
    )
    calibration_status_used:     Mapped[CalibrationStatus]  = mapped_column(
        Enum(CalibrationStatus), default=CalibrationStatus.UNKNOWN
    )

    history: Mapped[HistoryItem] = relationship(back_populates="ai_result")