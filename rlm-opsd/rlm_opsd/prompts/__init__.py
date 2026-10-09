"""SPEC §3 prompt construction and token-preserving prefix replacement."""
from .alignment import build_teacher_sequence
from .chat import ChatRenderer, PrefixPair, PromptConfig, prepare_tokenizer
from .templates import PromptBuilder, PromptPair, render_named

__all__ = ['PromptBuilder', 'PromptPair', 'render_named', 'ChatRenderer', 'PrefixPair',
           'PromptConfig', 'prepare_tokenizer', 'build_teacher_sequence']
