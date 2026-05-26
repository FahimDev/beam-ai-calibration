# Spec: Session entity

## Purpose
Core unit of work in the BI Tool workflow. Represents one beam alignment task.

## Inputs
- laser_id: string (required)
- measuring_device_id: FK to MeasuringDevice (required)
- session_type: current | previous | best_practice
- notes_title: string (optional)
- notes_body: text (optional)

## Outputs
- Session row in DB with ULID primary key
- started_at auto-set to utcnow on creation
- status defaults to "open"

## Constraints
- session_id must be ULID
- measuring_device_id must reference existing MeasuringDevice
- ended_at is null until End Session action
- Only one session per laser may have status=open at a time (enforce in service layer)

## Assumptions
- Laser ID format not yet confirmed — treat as free string for now
- Session notes are optional and unstructured

## Acceptance criteria
- [ ] Session can be created with required fields only
- [ ] started_at is set automatically
- [ ] ended_at is null on creation
- [ ] second open session for same laser raises conflict error
- [ ] session_type must be one of the three enum values

## Out of scope
- Session export to BI Tool format (unknown format)
- Real-time sync with hardware
