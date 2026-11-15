"""Document ingestion (Milestone 2): PDF text, scanned-PDF OCR and image OCR."""

from app.ingestion.errors import (
    CorruptFileError,
    EmptyFileError,
    EncryptedPDFError,
    FileTooLargeError,
    IngestionError,
    OCRLanguageError,
    OCRProcessingError,
    OCRUnavailableError,
    TooManyPagesError,
    UnsupportedFileTypeError,
)
from app.ingestion.schemas import (
    ExtractionMethod,
    FileType,
    IngestedDocument,
    PageText,
    SourceType,
    TextLine,
)
from app.ingestion.service import ingest_bytes, ingest_file

__all__ = [
    "CorruptFileError",
    "EmptyFileError",
    "EncryptedPDFError",
    "ExtractionMethod",
    "FileTooLargeError",
    "FileType",
    "IngestedDocument",
    "IngestionError",
    "OCRLanguageError",
    "OCRProcessingError",
    "OCRUnavailableError",
    "PageText",
    "SourceType",
    "TextLine",
    "TooManyPagesError",
    "UnsupportedFileTypeError",
    "ingest_bytes",
    "ingest_file",
]
