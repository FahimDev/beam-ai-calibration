# Spec: Calibration Ledger

## Purpose
Gate every AIAnalysisResult against camera calibration validity.
Ensure no AI recommendation is shown when calibration is expired or unknown.
Track full calibration history per measuring device and camera.

## Location
beam_ai/ledger/calibration.py

## Inputs

### register_calibration()
- calibration_id     : str (ULID, provided by caller)
- device_id          : str (FK to MeasuringDevice)
- camera             : CameraType (BP | BD)
- calibration_date   : datetime
- pixel_scale_x      : float | None  (µm/pixel — assumption, confirm with FSE)
- pixel_scale_y      : float | None  (µm/pixel — assumption, confirm with FSE)
- validity_days      : int (default from settings, assumption: 90 days)
- updated_by         : str | None
- version            : str (default "v1")
- file_path          : str | None

### check_calibration()
- db        : SQLAlchemy Session
- device_id : str
- now       : datetime | None (defaults to utcnow — injectable for testing)

### gate_ai_result()
- db        : SQLAlchemy Session
- device_id : str
- ai_result : AIAnalysisResult (mutates in place, returns same object)

## Outputs

### register_calibration()
Returns: CameraCalibration ORM row (committed to DB)

### check_calibration()
Returns: CalibrationCheck dataclass
  - device_id   : str
  - bp_status   : CalibrationStatus
  - bd_status   : CalibrationStatus
  - bp_expiry   : datetime | None
  - bd_expiry   : datetime | None
  - overall     : CalibrationStatus  (worst of BP and BD)
  - blocking    : bool               (True if AI must not recommend)
  - message     : str                (human-readable status)

### gate_ai_result()
Returns: AIAnalysisResult (mutated)
  Mutations applied:
  - calibration_status_used  ← overall status from check_calibration()
  - recommendation_mode      ← NONE if blocking, else SHADOW
  - safety_status            ← BLOCK if blocking, else unchanged
  - recommendation_text      ← appends [BLOCKED] message if blocking

## Constraints (hard rules — never break)

1. gate_ai_result() MUST be called before any AIAnalysisResult is committed.
   Never bypass this function.

2. recommendation_mode is NEVER set to FSE_REVIEW by this module.
   Only a human FSE action may set FSE_REVIEW.

3. When overall == EXPIRED or UNKNOWN:
   - recommendation_mode = NONE
   - safety_status       = BLOCK
   - recommendation_text appends [BLOCKED] reason

4. When overall == VALID:
   - recommendation_mode = SHADOW (minimum safe mode)
   - safety_status       = unchanged (caller sets it)

5. check_calibration() always returns the most recent calibration per camera.
   If no calibration exists for a camera → status = UNKNOWN.

6. overall status precedence (worst-of-two rule):
   UNKNOWN > EXPIRED > VALID

7. All DB writes go through the provided SQLAlchemy session.
   No new engine or session created inside this module.

## Assumptions (must be confirmed with FSE/hardware team)

- A1: Default calibration validity is 90 days.
      Source: settings.default_calibration_validity_days
- A2: pixel_scale unit is µm/pixel.
      Not confirmed from BI Tool spec.
- A3: One calibration record per camera per date is sufficient.
      No intra-day re-calibration expected.
- A4: BP and BD are always calibrated together in practice
      but are stored and checked independently.

## Acceptance criteria (all must pass as pytest tests)

- [ ] AC-01: register_calibration() creates a CameraCalibration row with
             correct expiry_date = calibration_date + validity_days
- [ ] AC-02: check_calibration() returns VALID when both BP and BD
             have unexpired calibrations
- [ ] AC-03: check_calibration() returns EXPIRED when either camera
             has an expired calibration
- [ ] AC-04: check_calibration() returns UNKNOWN when no calibration
             exists for either camera
- [ ] AC-05: check_calibration() returns UNKNOWN (not EXPIRED) when
             one camera has no record and the other is valid
             (UNKNOWN > EXPIRED > VALID precedence)
- [ ] AC-06: gate_ai_result() sets recommendation_mode=NONE and
             safety_status=BLOCK when calibration is EXPIRED
- [ ] AC-07: gate_ai_result() sets recommendation_mode=NONE and
             safety_status=BLOCK when calibration is UNKNOWN
- [ ] AC-08: gate_ai_result() sets recommendation_mode=SHADOW when
             calibration is VALID
- [ ] AC-09: gate_ai_result() never sets recommendation_mode=FSE_REVIEW
- [ ] AC-10: gate_ai_result() appends [BLOCKED] to recommendation_text
             when blocking
- [ ] AC-11: check_calibration() uses injectable `now` param —
             same calibration appears VALID at T and EXPIRED at T+91days
- [ ] AC-12: register_calibration() raises IntegrityError when
             device_id does not exist in measuring_device table

## Out of scope
- Multi-device calibration sync
- Calibration file parsing or format validation
- Automatic calibration expiry notifications
- Hardware-triggered re-calibration
- Any UI for calibration management