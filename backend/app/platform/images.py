"""Checking and cleaning uploaded images (D-057).

The file name and the browser's stated type are never trusted: the first
bytes ("magic bytes") decide whether it is PNG, JPEG or WebP, and anything
else (SVG, PDF, text, a renamed file) is refused. The image is then opened
with Pillow and saved again from its pixels only, which drops EXIF data such
as GPS position and camera details, turns it the right way up and shrinks it
to at most 1200 pixels on its longer side. A broken file or an image so large
it could exhaust memory (a "decompression bomb") is refused.
"""

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import ProblemError
from app.src.files.models import IMAGE_LIMIT_BYTES

MAX_SIDE = 1200
# 40 million pixels is far beyond any logo or stamp; Pillow's own warning starts at about 89.
MAX_PIXELS = 40_000_000

FORMATS = {  # Pillow format: (content type, file extension)
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "WEBP": ("image/webp", "webp"),
}


@dataclass(frozen=True)
class CleanImage:
    data: bytes
    content_type: str
    extension: str


def unsupported() -> ProblemError:
    return ProblemError(415, "Upload a PNG, JPEG or WebP image.", code="unsupported_file")


def too_large(limit: int = IMAGE_LIMIT_BYTES) -> ProblemError:
    size = f"{limit // (1024 * 1024)} MB"
    what = "image" if limit == IMAGE_LIMIT_BYTES else "file"
    return ProblemError(413, f"The {what} must be {size} or smaller.", code="file_too_large")


def sniff(data: bytes) -> str | None:
    """The Pillow format named by the file's first bytes, if it is one we accept."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def clean_image(data: bytes, limit: int = IMAGE_LIMIT_BYTES) -> CleanImage:
    """The cleaned image; `limit` is 1 MB for logos and 4 MB for correction attachments."""
    if len(data) > limit:
        raise too_large(limit)
    kind = sniff(data)
    if kind is None:
        raise unsupported()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format != kind or probe.width * probe.height > MAX_PIXELS:
                    raise unsupported()
                probe.verify()
            with Image.open(io.BytesIO(data)) as source:
                upright = ImageOps.exif_transpose(source)
                upright.thumbnail((MAX_SIDE, MAX_SIDE))
                mode = "RGB" if kind == "JPEG" else ("RGBA" if "A" in upright.getbands() else "RGB")
                # A new image from the pixels alone: no EXIF, no text chunks, no colour tricks.
                pixels = upright.convert(mode)
                clean = Image.new(mode, pixels.size)
                clean.paste(pixels)
    except ProblemError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        SyntaxError,
        ValueError,
    ):
        raise unsupported() from None
    out = io.BytesIO()
    options: dict[str, object] = {"quality": 88} if kind in {"JPEG", "WEBP"} else {}
    clean.save(out, kind, optimize=True, **options)
    result = out.getvalue()
    if len(result) > limit:
        raise too_large(limit)
    content_type, extension = FORMATS[kind]
    return CleanImage(result, content_type, extension)
