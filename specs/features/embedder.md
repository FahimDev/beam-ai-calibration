# Spec: Pretrained Image Embedder (Layer B)

## Purpose
Convert BP/BD beam images into fixed-length numerical vectors (embeddings)
using a pretrained vision encoder.

These embeddings capture visual patterns that classical features
(Layer A) cannot, including subtle shape, texture, and intensity
relationships learned from millions of images during pretraining.

Embeddings are used for:
  - Gen 2 Vector DB similarity search (find similar past beams)
  - Higher-accuracy classification when Layer A features plateau
  - Anomaly detection via distance from known-good cluster

This is Layer B of the three-layer feature pipeline.
It is a separate, optional module. Layer A features remain primary
until Layer B is proven to improve accuracy on real data.

## Location
beam_ai/features/embedder.py

## Background
A pretrained vision encoder is a neural network trained on a large
general image dataset (ImageNet, LAION, etc.) by a major lab.
Without any further training, it can take an image and produce a
vector that encodes its visual content.

For our use case, the encoder is FROZEN — we do not retrain it.
We only use it as a feature extractor. The output vector becomes
input to a small classifier (Layer C) or stored in a Vector DB.

## Inputs

### embed_image(image, config=None)
- image  : np.ndarray (H x W, any dtype) — single beam image
- config : EmbedderConfig | None

### embed_batch(images, config=None)
- images : list[np.ndarray] — batch for efficient GPU/CPU processing
- config : EmbedderConfig | None

### EmbedderConfig (dataclass)
- model_name        : str = "dinov2_vits14"
    Which pretrained model to use. Default options:
      - "dinov2_vits14"  — Meta DINOv2 small, 384-d output, recommended default
      - "dinov2_vitb14"  — Meta DINOv2 base, 768-d output, slower
      - "resnet50"       — torchvision ResNet50, 2048-d output, classic
      - "clip_vit_b32"   — OpenAI CLIP ViT-B/32, 512-d output
- device            : str  = "auto"  ("cpu" | "cuda" | "auto")
- target_resolution : tuple[int, int] = (224, 224)
    Input resolution required by most pretrained encoders.
- normalize_input   : bool = True
    Apply standard ImageNet normalization before encoding.
- grayscale_to_rgb  : bool = True
    Most pretrained models expect 3-channel input. If True,
    grayscale beam image is replicated to 3 channels.
- l2_normalize_output : bool = True
    Apply L2 normalization to output vector. Required for
    cosine similarity in Vector DB.

## Outputs

### EmbeddingResult (dataclass)
- vector         : np.ndarray (1D, float32)
- dim            : int — vector dimensionality
- model_name     : str
- model_version  : str — version/hash of the pretrained weights
- preprocessing_version : str — version of preprocessing pipeline
- l2_normalized  : bool

### embed_batch returns list[EmbeddingResult] in same order as input.

## Constraints

1. Encoder weights are FROZEN. Never train or fine-tune in this module.
   Fine-tuning belongs in a separate dedicated module.
2. No internet calls at inference time. Model weights downloaded once
   on first load and cached locally (default: ~/.cache/torch/hub).
3. Model loading is lazy and cached. Multiple calls to embed_image
   in the same process reuse the loaded model.
4. Device selection is automatic: use CUDA if available, else CPU.
   Explicit override via config.device.
5. Output vector dtype is always float32.
   uint16 / uint8 input images are converted internally.
6. Grayscale input is supported and is the expected case for BP/BD.
7. l2_normalize_output must be True when storing for cosine similarity.
8. Output vector dimension depends on model_name. Caller must not
   assume a fixed dimension — read it from EmbeddingResult.dim.
9. preprocessing_version string changes when input pipeline changes.
   This protects against silent drift between training and inference.
10. No dependency on the database. Pure function: image in, vector out.

## Assumptions
- A1: DINOv2-small is the best default for industrial inspection
      with small datasets. Self-supervised pretraining means it
      learned general visual features without label bias.
- A2: 224x224 resolution is sufficient. Beam shape is preserved
      at this resolution for both BP and BD typical sizes.
- A3: Grayscale-to-RGB replication is acceptable for excimer beam images.
      Pretrained encoders expect RGB; replicating the grayscale channel
      three times has been shown to work well for medical and
      industrial grayscale imagery.
- A4: ImageNet normalization mean/std is appropriate even for
      beam images. Alternative normalizations can be tried later.
- A5: Inference time of <100 ms per image on CPU is acceptable.
      GPU is optional, not required.

## Acceptance criteria

- [ ] AC-01: embed_image() returns EmbeddingResult with vector shape (dim,)
             matching model_name's expected output dimension
- [ ] AC-02: Vector dtype is np.float32
- [ ] AC-03: When l2_normalize_output=True, np.linalg.norm(vector) ≈ 1.0
- [ ] AC-04: embed_image() is deterministic — same input produces
             identical vector across calls (within float tolerance)
- [ ] AC-05: embed_batch(N images) returns a list of length N in same order
- [ ] AC-06: Two visually similar beams (e.g. two NORMAL beams with
             different seeds) have cosine similarity > 0.7
- [ ] AC-07: Two visually different beams (NORMAL vs MULTI_PEAK) have
             cosine similarity < 0.9 (i.e. measurably different)
- [ ] AC-08: Model loading is cached — second call to embed_image
             within same process is faster than first call by >10x
- [ ] AC-09: Grayscale uint16 input is accepted and produces valid output
- [ ] AC-10: Grayscale uint8 input is accepted and produces valid output
- [ ] AC-11: Input image is not modified by embed_image()
- [ ] AC-12: EmbeddingResult.model_version is non-empty string
- [ ] AC-13: Both BP-sized and BD-sized images are accepted
             (resizing handled internally)
- [ ] AC-14: Running on CPU when device="cpu" — no GPU required for tests

## Out of scope
- Fine-tuning the encoder on beam images (separate future module)
- Vector DB storage and indexing (separate module under ml/)
- Similarity search logic (separate retrieval module)
- Multi-image fusion (BP + BD combined into one embedding)
- Streaming / batched real-time inference
- Quantization or model optimization