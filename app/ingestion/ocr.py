"""OCR with Tesseract (via pytesseract) and Pillow image preparation.

``OCRBackend`` is a small protocol so tests (and later experiments) can swap in
a fake engine; ``TesseractOCR`` is the real implementation.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import Settings
from app.ingestion.errors import (
    CorruptFileError,
    FileTooLargeError,
    OCRLanguageError,
    OCRProcessingError,
    OCRUnavailableError,
)
from app.ingestion.layout import Word

logger = logging.getLogger(__name__)

MAX_IMAGE_PIXELS = 100_000_000
# Images whose long side is below this are upscaled before OCR (small text
# recognises poorly). Upscaling is undone when reporting coordinates.
UPSCALE_BELOW_LONG_SIDE = 1500
UPSCALE_FACTOR = 2.0

_WINDOWS_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)

INSTALL_HELP = (
    "Install Tesseract OCR and make sure it can be found. On Windows, install the "
    "64-bit build from https://github.com/UB-Mannheim/tesseract/wiki (default folder "
    r"C:\Program Files\Tesseract-OCR), then either add that folder to PATH or set "
    r"MEDRAG_TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe in your .env file."
)


@dataclass(frozen=True)
class OCRResult:
    words: list[Word]
    mean_confidence: float | None  # 0-100, None when no words were recognised


class OCRBackend(Protocol):
    def ensure_available(self) -> None:
        """Raise ``OCRUnavailableError`` if OCR cannot run."""

    def recognize(self, image: Image.Image) -> OCRResult:
        """OCR ``image``; word boxes are in the pixel space of ``image``."""


def load_image(data: bytes) -> Image.Image:
    """Decode JPG/PNG bytes into an upright RGB image.

    Applies EXIF orientation and flattens transparency onto white (a naive
    conversion would turn transparent PNG backgrounds black and hide the text).
    """
    try:
        probe = Image.open(io.BytesIO(data))
        width, height = probe.size
        if width * height > MAX_IMAGE_PIXELS:
            raise FileTooLargeError(
                f"Image is {width}x{height} pixels; the limit is {MAX_IMAGE_PIXELS:,} pixels."
            )
        probe.load()  # force full decode so truncated files fail here
        image = ImageOps.exif_transpose(probe)
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba)
        return image.convert("RGB")
    except FileTooLargeError:
        raise
    except Image.DecompressionBombError as exc:
        raise FileTooLargeError("Image is too large to process safely.") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise CorruptFileError("The image file is corrupt or cannot be decoded.") from exc


def prepare_for_ocr(image: Image.Image) -> tuple[Image.Image, float]:
    """Grayscale + contrast stretch (+ upscale small images). Returns ``(image, scale)``.

    Deliberately no binarisation/denoising: aggressive filters can erase
    decimal points and faint digits. Tesseract applies its own thresholding.
    """
    prepared = ImageOps.autocontrast(image.convert("L"), cutoff=1)
    long_side = max(prepared.size)
    scale = 1.0
    if long_side < UPSCALE_BELOW_LONG_SIDE:
        scale = UPSCALE_FACTOR
        prepared = prepared.resize(
            (round(prepared.width * scale), round(prepared.height * scale)),
            Image.Resampling.LANCZOS,
        )
    return prepared, scale


def find_tesseract(configured: Path | None) -> str | None:
    """Locate the tesseract executable: setting, then PATH, then Windows defaults."""
    if configured is not None:
        return str(configured) if configured.is_file() else None
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    candidates = list(_WINDOWS_TESSERACT_PATHS)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            str(Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
        )
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return None


class TesseractOCR:
    """Tesseract-backed OCR engine."""

    def __init__(self, settings: Settings) -> None:
        self._configured_cmd = settings.tesseract_cmd
        self._languages = settings.ocr_languages
        self._psm = settings.ocr_psm
        self._timeout = settings.ocr_timeout_seconds
        self._checked = False
        self._cmd: str | None = None

    def ensure_available(self) -> None:
        if self._checked:
            return
        cmd = find_tesseract(self._configured_cmd)
        if cmd is None:
            where = (
                f"The configured path '{self._configured_cmd}' does not exist. "
                if self._configured_cmd
                else "Tesseract was not found. "
            )
            raise OCRUnavailableError(where + INSTALL_HELP)
        self._cmd = cmd
        pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            pytesseract.get_tesseract_version()
            installed = set(pytesseract.get_languages(config=""))
        except (pytesseract.TesseractNotFoundError, OSError, RuntimeError) as exc:
            raise OCRUnavailableError(
                f"Tesseract could not be started ({cmd}). {INSTALL_HELP}"
            ) from exc
        missing = [lang for lang in self._languages.split("+") if lang not in installed]
        if missing:
            raise OCRLanguageError(
                f"Tesseract language data missing: {', '.join(missing)}. Installed: "
                f"{', '.join(sorted(installed)) or 'none'}. Install the language pack(s) or change "
                "MEDRAG_OCR_LANGUAGES."
            )
        self._checked = True
        logger.info("Tesseract ready (languages=%s)", self._languages)

    def recognize(self, image: Image.Image) -> OCRResult:
        self.ensure_available()
        # pytesseract keeps the executable path globally; re-assert ours in case
        # another engine instance with a different path ran in between.
        pytesseract.pytesseract.tesseract_cmd = self._cmd
        prepared, scale = prepare_for_ocr(image)
        config = f"--oem 3 --psm {self._psm} -c preserve_interword_spaces=1"
        try:
            data = pytesseract.image_to_data(
                prepared,
                lang=self._languages,
                config=config,
                output_type=pytesseract.Output.DICT,
                timeout=self._timeout,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRUnavailableError(f"Tesseract disappeared during OCR. {INSTALL_HELP}") from exc
        except RuntimeError as exc:  # TesseractError and timeouts
            raise OCRProcessingError(f"Tesseract failed or timed out: {exc}") from exc

        words: list[Word] = []
        confidences: list[float] = []
        for i, raw_text in enumerate(data["text"]):
            text = str(raw_text).strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            left, top = float(data["left"][i]), float(data["top"][i])
            width, height = float(data["width"][i]), float(data["height"][i])
            words.append(
                Word(
                    text,
                    left / scale,
                    top / scale,
                    (left + width) / scale,
                    (top + height) / scale,
                    conf,
                )
            )
            confidences.append(conf)
        mean = sum(confidences) / len(confidences) if confidences else None
        return OCRResult(words=words, mean_confidence=mean)


_ENGINES: dict[tuple[object, ...], TesseractOCR] = {}


def get_default_ocr(settings: Settings) -> TesseractOCR:
    """Return a shared engine per configuration so availability is checked once."""
    key = (
        settings.tesseract_cmd,
        settings.ocr_languages,
        settings.ocr_psm,
        settings.ocr_timeout_seconds,
    )
    if key not in _ENGINES:
        _ENGINES[key] = TesseractOCR(settings)
    return _ENGINES[key]
