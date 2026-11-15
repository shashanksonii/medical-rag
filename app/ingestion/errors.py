"""Ingestion errors.

Every error carries a stable machine-readable ``code`` so that the API layer
(added in a later milestone) can map errors to HTTP responses without parsing
messages. Messages are written for the person running the system and never
include document text.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for all document-ingestion failures."""

    code = "ingestion_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileTypeError(IngestionError):
    code = "unsupported_file_type"


class EmptyFileError(IngestionError):
    code = "empty_file"


class FileTooLargeError(IngestionError):
    code = "file_too_large"


class TooManyPagesError(IngestionError):
    code = "too_many_pages"


class CorruptFileError(IngestionError):
    code = "corrupt_file"


class EncryptedPDFError(IngestionError):
    code = "encrypted_pdf"


class OCRUnavailableError(IngestionError):
    """Tesseract (or a requested language pack) is not installed/usable."""

    code = "ocr_unavailable"


class OCRLanguageError(OCRUnavailableError):
    code = "ocr_language_unavailable"


class OCRProcessingError(IngestionError):
    """Tesseract was available but failed or timed out on a page/image."""

    code = "ocr_failed"
