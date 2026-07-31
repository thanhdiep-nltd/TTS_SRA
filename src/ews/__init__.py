# -*- coding: utf-8 -*-
"""
src/ews/__init__.py — Early Warning System (EWS) Runtime Inference Module

Package chứa các module cho pipeline tích hợp mô hình CatBoost EWS:
  - feature_extractor.py : Trích xuất 22 features từ DB s360
  - inference_service.py : Load model, predict_proba, SHAP
  - pipeline_runner.py   : Batch UPSERT DB, orchestrator
"""

from src.ews.feature_extractor import extract_live_features, EWS_FEATURE_COLS
from src.ews.inference_service import load_model, run_inference
from src.ews.pipeline_runner import persist_predictions, run_pipeline

__version__ = "1.0.0"

__all__ = [
    "extract_live_features",
    "EWS_FEATURE_COLS",
    "load_model",
    "run_inference",
    "persist_predictions",
    "run_pipeline",
]
