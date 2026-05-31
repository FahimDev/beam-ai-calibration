# Spec: Classical Feature Extractor (Layer A)

## Purpose
Extract numerical, interpretable features from BP and BD beam images
using OpenCV and NumPy.
These features fill the Output table fields and serve as input to
the Layer C classifier (RandomForest baseline).

This is Layer A of the three-layer feature pipeline:
  Layer A — Classical features (this module)
  Layer B — Pretrained embeddings (embedder.py, separate spec)
  Layer C — Classifier (baseline_rf.py, separate spec)

Modularity is the core design goal: this layer must work standalone
and must not depend on Layer B or Layer C.

## Location
beam_ai/features/extractor.py

## Background
Real BP/BD images are 2D intensity matrices.
Classical features answer questions like:
  - Where is the beam centered? (COG)
  - How big is it? (size_hor, size_ver)
  - Is it symmetric? (symmetry)
  - Is the energy spread evenly? (uniformity)
  - Are there sharp edges? (ContM — contour moment)
  - How bright is it? (intensity_mean, max, std)

These features are interpretable. A senior engineer can look at
"COG shifted +47 pixels horizontally" and immediately know what is wrong.
A neural network embedding does not give this.

## Inputs

### extract_features(image, camera_type, config=None)
- image       : np.ndarray (H x W, uint16 or uint8) — beam image
- camera_type : CameraType (BP or BD)
- config      : ExtractorConfig | None — optional override

### ExtractorConfig (dataclass)
- background_threshold : float = 0.05
    Pixel intensity below this fraction of max is treated as background.
    Affects COG and size computations (only "beam" pixels count).
- size_method          : str   = "d4sigma"
    Method for computing beam size. Options:
      - "d4sigma" — 4 * standard deviation of intensity-weighted distribution
                    (ISO 11146 standard for laser beam width)
      - "fwhm"    — full width at half maximum
- symmetry_method      : str   = "flip_correlation"
    How to measure symmetry. Options:
      - "flip_correlation" — correlate image with its horizontal/vertical flip
      - "moment_ratio"     — ratio of second-order central moments
- normalize_intensity  : bool  = True
    If True, intensity stats are reported as fractions of max possible value
    (e.g. 0.0–1.0 for any bit depth). If False, raw pixel values.

## Outputs

### FeatureSet (dataclass)
All fields are float | None. Returned values match the Output table schema.

- cog_x          : Centroid X coordinate in pixels
- cog_y          : Centroid Y coordinate in pixels
- size_hor       : Horizontal beam size in pixels (per size_method)
- size_ver       : Vertical beam size in pixels (per size_method)
- intensity_mean : Mean pixel intensity (normalized 0.0–1.0 if normalize_intensity)
- intensity_max  : Max pixel intensity (normalized 0.0–1.0 if normalize_intensity)
- intensity_std  : Std dev of pixel intensity (normalized)
- uniformity     : 0.0–1.0 score of how uniform intensity distribution is
                   (1.0 = perfectly uniform within beam region)
- symmetry       : 0.0–1.0 score (1.0 = perfectly symmetric)
- contm_hor      : Horizontal contour moment (edge sharpness indicator)
- contm_ver      : Vertical contour moment

If the image is entirely background (no beam detected),
all features return None. A warning is logged.

## Constraints

1. No external API calls. All computation is local NumPy/OpenCV.
2. Input image must not be modified. Use copies if needed.
3. Function must work for both BP and BD images without code branching
   on camera_type. The math is the same; only typical value ranges differ.
4. uint16 and uint8 inputs both supported. Internally convert to float64.
5. COG is computed only on pixels above background_threshold.
   Pure-background images return cog_x = cog_y = None.
6. size_hor and size_ver use ISO 11146 D4σ method by default.
   This is the standard for laser beam measurement.
7. All outputs must be JSON-serializable (no numpy types in return).
8. Function must handle edge cases without raising:
   - All-zero image → all features None
   - Single bright pixel → COG at that pixel, size near zero
   - Saturated image (all max value) → COG at image center, uniformity 1.0
9. No image resizing or cropping. Caller is responsible for ROI.
10. No dependency on the database. Pure function: image in, features out.

## Assumptions
- A1: Beam intensity follows roughly a Gaussian or near-Gaussian profile.
      Multi-peak beams will still produce a single COG (intensity-weighted center).
- A2: Background level is consistent across the image.
      No spatial gradient correction is applied.
- A3: 16-bit grayscale PNG is the primary image format.
      Other formats are converted to grayscale before extraction.
- A4: Pixel coordinates: (0, 0) is top-left. cog_x increases rightward,
      cog_y increases downward (standard image convention).
- A5: ISO 11146 D4σ is the appropriate size metric for excimer laser beams.
      Confirm with FSE if FWHM is preferred.

## Acceptance criteria

- [ ] AC-01: extract_features() on a NORMAL synthetic BP image returns
             cog_x within 5% of image center
- [ ] AC-02: extract_features() on a NORMAL synthetic BP image returns
             cog_y within 5% of image center
- [ ] AC-03: extract_features() on a SHIFTED_H beam returns cog_x
             shifted >10% from center in the expected direction
- [ ] AC-04: extract_features() on a SHIFTED_V beam returns cog_y
             shifted >10% from center
- [ ] AC-05: size_hor of an ELLIPTICAL beam differs from size_ver by >50%
- [ ] AC-06: size_hor and size_ver of a NORMAL beam are within 20% of
             expected values derived from generator config sigma values
             (D4σ ≈ 4*sigma)
- [ ] AC-07: intensity_max of a NORMAL beam matches generator peak_intensity
             within 5%
- [ ] AC-08: intensity_max of a WEAK beam is <30% of NORMAL beam
- [ ] AC-09: symmetry of a NORMAL beam is >0.85
- [ ] AC-10: symmetry of a SHIFTED_H beam is lower than symmetry of NORMAL
- [ ] AC-11: uniformity of a flat (all-equal) image is 1.0 ± 0.05
- [ ] AC-12: uniformity of a NOISY beam is lower than NORMAL
- [ ] AC-13: All-zero image returns all features as None and logs warning
- [ ] AC-14: All-max image (saturated) returns COG at image center
- [ ] AC-15: Returned FeatureSet has no numpy scalar types
             (all values are native Python float or None)
- [ ] AC-16: extract_features() does not modify the input image array
- [ ] AC-17: BD image (small spot) and BP image (large beam) both
             produce valid FeatureSet without code branching on camera_type

## Out of scope
- Embedding extraction (Layer B — see embedder.md)
- Multi-peak detection or count
- Beam tilt or rotation angle
- Wavelength or color analysis
- Time-series features across multiple captures
- ROI auto-detection
- Real-time streaming feature extraction
- Database writes (caller does that)