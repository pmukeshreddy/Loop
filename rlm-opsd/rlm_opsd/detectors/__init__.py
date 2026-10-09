"""Offline RLM behavior analysis; no model calls or training side effects."""
from .config import DetectorConfig
from .evaluate import analyze_trajectory
from .categories import classify_text_spans, classify_token_offsets, summarize_token_divergence
from .reports import aggregate_behavior, write_behavior_report

__all__ = ['DetectorConfig', 'analyze_trajectory', 'classify_text_spans',
           'classify_token_offsets', 'summarize_token_divergence',
           'aggregate_behavior', 'write_behavior_report']
