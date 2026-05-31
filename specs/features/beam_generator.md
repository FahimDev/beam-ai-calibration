# Spec: Synthetic Beam Generator

## Purpose
Generate synthetic BP and BD beam images for offline R&D.
No real hardware or camera data available yet.
Images must be realistic enough to test feature extraction,
model training, and session replay without real data.

## Location
beam_ai/synthetic/beam_generator.py

## Background
BP (Beam Profile): shows spatial intensity distribution of the beam.
  - Real image: tall vertical oval heat map, bright center, fading edges.
  - Typical appearance: red/yellow center, green/blue edges, dark background.

BD (Beam Divergence): shows far-field beam spot.
  - Real image: small bright spot on dark background.
  - Typical appearance: single tight gaussian spot, much smaller than BP.

Both are grayscale intensity matrices saved as PNG.
Pixel values represent light intensity (0 = dark, 65535 = max for 16-bit).

## Inputs

### BeamGeneratorConfig (dataclass)
BP image:
  - width_px        : int   (default 512)
  - height_px       : int   (default 896)  # tall aspect ratio for BP
  - bit_depth       : int   (default 16)   # assumption: 16-bit grayscale
  - sigma_x         : float (default 60.0) # beam width in pixels
  - sigma_y         : float (default 140.0)# beam height in pixels
  - center_x        : float (default None) # defaults to image center
  - center_y        : float (default None) # defaults to image center
  - peak_intensity  : float (default 0.85) # fraction of max value
  - noise_level     : float (default 0.02) # gaussian noise fraction
  - beam_type       : BeamType enum

BD image:
  - width_px        : int   (default 192)
  - height_px       : int   (default 256)
  - sigma_x         : float (default 8.0)  # tight spot
  - sigma_y         : float (default 10.0)
  - center_x        : float (default None)
  - center_y        : float (default None)
  - peak_intensity  : float (default 0.90)
  - noise_level     : float (default 0.01)

### BeamType enum
  NORMAL      : centered gaussian, good beam
  SHIFTED_H   : centroid shifted horizontally
  SHIFTED_V   : centroid shifted vertically
  ELLIPTICAL  : exaggerated aspect ratio
  WEAK        : low peak intensity
  NOISY       : high noise level
  CLIPPED     : beam truncated at image edge
  MULTI_PEAK  : two gaussian spots (bad alignment)

## Outputs

### generate_bp(config) → BeamImageResult
### generate_bd(config) → BeamImageResult

BeamImageResult dataclass:
  - image_array  : np.ndarray  (H x W, uint16)
  - image_path   : str         (saved PNG path)
  - width_px     : int
  - height_px    : int
  - intensity_min: float
  - intensity_max: float
  - beam_type    : BeamType
  - camera_type  : CameraType  (BP or BD)
  - config       : BeamGeneratorConfig

### generate_pair(bp_config, bd_config) → tuple[BeamImageResult, BeamImageResult]
Generates matching BP and BD for the same beam state.

### generate_dataset(n, beam_types, output_dir) → list[BeamImageResult]
Generates n images per beam_type, saves to output_dir.

## Constraints

1. All images saved to IMAGE_STORE_PATH from settings.
   Never hardcode paths.
2. Output format: PNG, 16-bit grayscale.
   assumption — confirm with hardware team.
3. BP aspect ratio must be taller than wide (height > width).
4. BD spot must be significantly smaller than BP beam.
5. MULTI_PEAK type must have exactly two gaussian peaks.
6. CLIPPED type must have at least one edge where beam is truncated.
7. All numpy arrays must be uint16 dtype before saving.
8. Noise must be additive gaussian, not multiplicative.
9. No random seed hardcoded globally — seed injectable for testing.

## Assumptions
- A1: BP resolution ~512x896 px — not confirmed, placeholder.
- A2: BD resolution ~192x256 px — not confirmed, placeholder.
- A3: 16-bit grayscale PNG format — not confirmed.
- A4: Gaussian beam model is sufficient for synthetic data.
      Real beams may have speckle, hot spots, or asymmetry.
- A5: Color heat map (false color) is display-only in BI Tool.
      Underlying data is grayscale intensity matrix.

## Acceptance criteria

- [ ] AC-01: generate_bp() returns uint16 numpy array
             with shape (height_px, width_px)
- [ ] AC-02: generate_bd() returns uint16 numpy array
             with shape (height_px, width_px)
- [ ] AC-03: NORMAL beam has peak near image center (within 10% of center)
- [ ] AC-04: SHIFTED_H beam has centroid shifted >10% from center horizontally
- [ ] AC-05: SHIFTED_V beam has centroid shifted >10% from center vertically
- [ ] AC-06: WEAK beam peak intensity < 30% of max pixel value
- [ ] AC-07: NOISY beam std deviation > 3x NORMAL beam std deviation
- [ ] AC-08: CLIPPED beam has pixels at maximum value on at least one edge
- [ ] AC-09: MULTI_PEAK beam has two distinct local maxima
- [ ] AC-10: generate_pair() returns (BP, BD) with matching beam_type
- [ ] AC-11: All output files are saved as valid

```
https://researchportal.hw.ac.uk/en/datasets/laser-resonator-beam-alignment-dataset-subset/
```