"""Language detection and multilingual document processing services."""

from .multilingual_handler import (
    MultilingualDocumentHandler,
    MultilingualVerificationResult,
    ScriptType,
    LanguageType
)

__all__ = [
    "MultilingualDocumentHandler",
    "MultilingualVerificationResult",
    "ScriptType",
    "LanguageType"
]