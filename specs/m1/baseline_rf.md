# Spec: RandomForest Baseline Classifier (Layer C, Gen 1)

## Purpose
Train and evaluate a RandomForest classifier that predicts laser
performance rank (S/A/B/C/D/E) from beam features.

This reproduces and replaces the existing Gen 1 Sakou model
(AMP 54% / OSC 66%) using our own modular pipeline.

Once trained, the model becomes the first AI output that flows
through the calibration ledger into AIAnalysisResult rows.

This is Layer C of the three-layer feature pipeline.
Default input source is Layer A (classical features).
Layer B (embeddings) can be swapped in later without changing this module.

## Location
beam_ai/ml/baseline_rf.py

## Background
RandomForest is chosen because:
  - It works well on small tabular feature sets (11–100 features)
  - It is robust to feature scaling and missing values
  - It provides feature importance for interpretability
  - It is the same model family as Gen 1, enabling direct comparison
  - It requires no GPU and trains in seconds

This module does not invent the algorithm. It wraps scikit-learn's
RandomForestClassifier with project-specific:
  - Data loading from our DB schema
  - Train/test split that respects session boundaries
  - Hyperparameter search bounded to safe ranges
  - Evaluation report matching Gen 1's confusion matrix format
  - Model versioning aligned with settings.ai_model_version

## Inputs

### train(config) → TrainResult
- config : TrainConfig (see below)

### predict(features, model) → Prediction
- features : FeatureSet (Layer A) | np.ndarray (Layer B embedding)
- model    : trained model object (from train() or load_model())

### evaluate(model, test_data) → EvaluationReport
- model     : trained model
- test_data : list of (features, true_label) tuples

### TrainConfig (dataclass)
- feature_source       : str = "classical"
    "classical" — use Layer A FeatureSet fields
    "embedding" — use Layer B embedding vectors
- training_data_filter : dict | None
    Filters applied when querying training data from DB. Examples:
      - {"session_type": "previous"}
      - {"beam_mode": "AMP"}
      - {"min_score": 0.0}
- test_size            : float = 0.30
- random_state         : int   = 42
- class_balance        : str   = "balanced"
    "balanced" — auto-weight rare classes (S, A)
    "none"     — no weighting
    dict       — explicit class weights
- hyperparameter_search : bool = True
    If True, run GridSearchCV. If False, use defaults.
- cv_folds             : int  = 3
- scoring              : str  = "f1_macro"
    Macro F1 better than accuracy for imbalanced S/A/B/C/D/E.
- model_version        : str  = "rf_baseline_v1"
- output_path          : str | None — where to save trained model

## Outputs

### TrainResult (dataclass)
- model              : sklearn estimator object
- best_params        : dict — chosen hyperparameters
- cv_score           : float — best cross-validation score
- feature_names      : list[str]
- feature_importance : dict[str, float]
- training_samples   : int
- model_version      : str
- training_metadata  : dict (timestamp, config used, data filter)

### Prediction (dataclass)
- predicted_label    : str (one of S/A/B/C/D/E)
- confidence         : float (0.0–1.0)
- class_probabilities : dict[str, float]
- model_version      : str

### EvaluationReport (dataclass)
- accuracy           : float
- per_class_accuracy : dict[str, float]
- per_class_recall   : dict[str, float]
- per_class_precision: dict[str, float]
- macro_f1           : float
- confusion_matrix   : np.ndarray (6x6 for S/A/B/C/D/E)
- confusion_labels   : list[str]
- test_samples       : int

## Constraints

1. Training data MUST come from the DB schema we defined.
   No raw CSV ingestion. Query through SQLAlchemy.
2. Train/test split must be at the session level, not history-item level.
   Two history items from the same session must not appear in both
   train and test sets (data leakage prevention).
3. Only HistoryItems with has_evaluation=True are used for training.
   Beam_mode must be TWIN for the source of labels.
4. Predictions are NEVER written to AIAnalysisResult directly by
   this module. Caller must pass through gate_ai_result() in the
   calibration ledger.
5. Model artifacts saved as joblib files with model_version in filename.
   Never overwrite an existing model — append timestamp if collision.
6. Hyperparameter search is bounded:
     n_estimators:        [100, 500]
     max_depth:           [5, 10, 30, None]
     min_samples_split:   [2, 5, 10]
     min_samples_leaf:    [1, 2, 4]
   Larger searches require explicit config override.
7. Random state must be reproducible. Default 42, settable in config.
8. Confidence is max class probability from predict_proba(),
   not a calibrated probability. Future work may add calibration.
9. If training data has <50 samples or <2 samples per class,
   train() raises InsufficientDataError. Do not silently train
   on too-small datasets.
10. Module must run on CPU only. No CUDA dependency.

## Assumptions
- A1: RandomForest is sufficient for the first baseline. Gradient boosting
      (XGBoost/LightGBM) may follow in a separate module.
- A2: 11 classical features (Layer A output) provide enough signal
      for B/C/D/E ranks. S/A ranks may need Layer B embeddings.
- A3: Per Gen 1 results, accuracy will be lower for top ranks (S, A)
      due to class imbalance. Macro F1 is therefore the primary metric.
- A4: Twin-oscillation evaluation labels are the ground truth.
      Single-oscillation images (AMP, OSC) are the features.
- A5: 30% test split is sufficient given small dataset size.
      Stratified split ensures all classes appear in both train and test.

## Acceptance criteria

- [ ] AC-01: train() with synthetic dataset of 60+ samples returns
             a TrainResult with non-null model and feature_importance
- [ ] AC-02: train() raises InsufficientDataError when given <50 samples
- [ ] AC-03: train() raises InsufficientDataError when any class has <2 samples
- [ ] AC-04: predict() returns Prediction with valid label and
             confidence in [0, 1]
- [ ] AC-05: predict() class_probabilities sum to 1.0 (within float tolerance)
- [ ] AC-06: evaluate() returns confusion_matrix of shape (6, 6)
- [ ] AC-07: evaluate() returns macro_f1 in [0, 1]
- [ ] AC-08: Train/test split respects session boundaries — no session
             appears in both train and test
- [ ] AC-09: Two training runs with same random_state and same data
             produce identical model predictions
- [ ] AC-10: feature_importance dict has one entry per input feature
             and values sum to 1.0
- [ ] AC-11: Saved model can be loaded and produces identical predictions
             as the in-memory model
- [ ] AC-12: model_version is included in TrainResult and every Prediction
- [ ] AC-13: feature_source="classical" pulls 11 features per FeatureSet
- [ ] AC-14: feature_source="embedding" accepts arbitrary-dim vector input
- [ ] AC-15: class_balance="balanced" produces higher recall on rare
             classes than class_balance="none" on imbalanced synthetic data
- [ ] AC-16: Module imports do not fail on CPU-only systems (no CUDA required)
- [ ] AC-17: Predictions can flow through gate_ai_result() to produce
             a valid AIAnalysisResult row (integration test)

## Out of scope
- XGBoost, LightGBM, or other tree ensembles (separate spec)
- Neural network classifiers (separate spec)
- Online learning / incremental training
- Active learning / sample selection
- Hyperparameter Bayesian optimization
- Model serving / deployment infrastructure (FastAPI spec separately)
- Probability calibration (Platt scaling, isotonic)
- Multi-task learning (predicting score + rank simultaneously)
- Cross-laser-model transfer learning