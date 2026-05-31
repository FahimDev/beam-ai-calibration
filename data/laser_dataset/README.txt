Dataset: Laser Resonator Beam Alignment (Subset)

Contents
--------
1. beam_images/ : 500 resized PNG images (256×256). Filenames are timestamps.
2. labels.json  : Alignment metadata per image (see example below).
3. sampled_pairs_500K.json : 500,000 index pairs used for ML training.
4. This README.

labels.json example
-------------------
{
  "filename": "beam_2025-02-27_10-10-00",
  "Date": "27/02/2025",
  "Timestamp": "10:10",
  "Iris Position": 3500.0,
  "Z Position": 0.0,
  "Pitch Position": 2.75,
  "Yaw Position": 2.02,
  "Power Measurement": 7.324e-05,
  …
}

Notes
-----
• Full-resolution raw TXT images (>6,000, 2048×2048) will be released after publication.
• Contact: S.Guo@hw.ac.uk
• Licence: CC BY 4.0
