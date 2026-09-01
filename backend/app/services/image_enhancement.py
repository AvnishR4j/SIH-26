from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache
from io import BytesIO
from threading import Lock
from typing import Protocol

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from app.core.config import REPOSITORY_ROOT, Settings, get_settings
from app.core.errors import ApiError

RemoveBackground = Callable[..., object]
SessionFactory = Callable[[str], object]


class ImageEnhancer(Protocol):
    def enhance(self, content: bytes, background: str, crop_style: str) -> bytes: ...


class MockImageEnhancer:
    def __init__(self, max_side: int = 4096) -> None:
        self.max_side = max_side

    def enhance(self, content: bytes, background: str, crop_style: str) -> bytes:
        image = _fit_max_side(_decode_rgb(content), self.max_side)
        if crop_style == "marketplace_square":
            fill = (245, 245, 245) if background == "neutral" else (255, 255, 255)
            image = _square_pad(image, fill)
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = ImageEnhance.Sharpness(image).enhance(1.1)
        return _jpeg_bytes(image)


class RembgImageEnhancer:
    def __init__(
        self,
        settings: Settings,
        *,
        remover: RemoveBackground | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        cache = settings.rembg_model_cache_dir.expanduser()
        self.model_cache = (
            cache.resolve() if cache.is_absolute() else (REPOSITORY_ROOT / cache).resolve()
        )
        self.model = settings.rembg_model
        self.max_side = settings.image_enhancement_max_side
        self._remover = remover
        self._session_factory = session_factory
        self._session: object | None = None
        self._session_lock = Lock()

    def enhance(self, content: bytes, background: str, crop_style: str) -> bytes:
        image = _fit_max_side(_decode_rgb(content), self.max_side)
        if background == "neutral":
            foreground = self._remove_background(image)
            foreground = self._correct_lighting_and_detail(foreground)
            if crop_style == "marketplace_square":
                foreground = _frame_foreground(foreground, target_side=max(image.size))
            image = _composite_on_neutral(foreground)
        else:
            image = self._correct_lighting_and_detail(image)
            if crop_style == "marketplace_square":
                image = _square_pad(image, (245, 245, 245))
        return _jpeg_bytes(image)

    def _remove_background(self, image: Image.Image) -> Image.Image:
        remover = self._remover
        if remover is None:
            from rembg import remove

            remover = remove
        try:
            result = remover(
                image,
                session=self._get_session(),
                alpha_matting=False,
                post_process_mask=True,
            )
            if not isinstance(result, Image.Image):
                raise TypeError("Background remover did not return an image")
            foreground = result.convert("RGBA")
            alpha = np.array(foreground.getchannel("A"), dtype=np.uint8)
            # Low-alpha pixels are almost always background shadows or mask noise.
            alpha[alpha < 28] = 0
            foreground.putalpha(Image.fromarray(alpha))
            if foreground.getbbox() is None:
                raise ApiError(
                    422,
                    "IMAGE_SUBJECT_NOT_CLEAR",
                    "We could not clearly find the product. Retake the photo with the product clearly visible.",
                )
            return foreground
        except ApiError:
            raise
        except Exception as error:
            raise ApiError(
                503,
                "AI_SERVICE_UNAVAILABLE",
                "Image enhancement is temporarily unavailable.",
            ) from error

    def _get_session(self) -> object:
        if self._session is not None:
            return self._session
        with self._session_lock:
            if self._session is None:
                try:
                    self.model_cache.mkdir(parents=True, exist_ok=True)
                    os.environ["U2NET_HOME"] = str(self.model_cache)
                    factory = self._session_factory
                    if factory is None:
                        from rembg import new_session

                        factory = new_session
                    self._session = factory(self.model)
                except Exception as error:
                    raise ApiError(
                        503,
                        "AI_SERVICE_UNAVAILABLE",
                        "Image enhancement is temporarily unavailable.",
                    ) from error
        return self._session

    @staticmethod
    def _correct_lighting_and_detail(image: Image.Image) -> Image.Image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        luminance, channel_a, channel_b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        corrected = cv2.merge((clahe.apply(luminance), channel_a, channel_b))
        corrected_rgb = cv2.cvtColor(corrected, cv2.COLOR_LAB2RGB)
        blurred = cv2.GaussianBlur(corrected_rgb, (0, 0), sigmaX=1.0)
        sharpened = cv2.addWeighted(corrected_rgb, 1.08, blurred, -0.08, 0)
        corrected = Image.fromarray(sharpened)
        if image.mode != "RGBA":
            return corrected
        # Keep the background transparent while correcting only the extracted product.
        corrected.putalpha(image.getchannel("A"))
        return corrected


def validate_product_photo(image: Image.Image, settings: Settings) -> None:
    """Reject technically unusable photos before they enter a catalogue draft."""
    if not settings.image_quality_gate_enabled:
        return

    normalized = ImageOps.exif_transpose(image).convert("RGB")
    if min(normalized.size) < settings.image_quality_min_side:
        raise ApiError(
            422,
            "IMAGE_TOO_SMALL",
            "Retake the photo closer to the product so it is clear enough to use.",
            {"min_side": settings.image_quality_min_side},
        )

    rgb = np.asarray(normalized, dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    contrast = float(gray.std())
    low, high = np.percentile(gray, (2, 98))
    if contrast < settings.image_quality_min_contrast or high - low < 35:
        raise ApiError(
            422,
            "IMAGE_NOT_CLEAR",
            "This photo has too little visible detail. Use a clear background and retake it.",
        )

    average_light = float(gray.mean())
    if average_light < 38:
        raise ApiError(
            422,
            "IMAGE_TOO_DARK",
            "This photo is too dark. Move the product into better light and retake it.",
        )
    if average_light > 228:
        raise ApiError(
            422,
            "IMAGE_TOO_BRIGHT",
            "This photo is too bright. Avoid strong glare and retake it.",
        )

    analysis = _fit_max_side(normalized, 1024)
    analysis_gray = cv2.cvtColor(np.asarray(analysis), cv2.COLOR_RGB2GRAY)
    blur_score = float(cv2.Laplacian(analysis_gray, cv2.CV_64F).var())
    if blur_score < settings.image_quality_min_blur_score:
        raise ApiError(
            422,
            "IMAGE_BLURRY",
            "This photo is blurry. Hold the camera steady, focus on the product, and retake it.",
            {"blur_score": round(blur_score, 1)},
        )


def _decode_rgb(content: bytes) -> Image.Image:
    with Image.open(BytesIO(content)) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


def _square_pad(image: Image.Image, fill: tuple[int, int, int]) -> Image.Image:
    side = max(image.size)
    return ImageOps.pad(
        image,
        (side, side),
        method=Image.Resampling.LANCZOS,
        color=fill,
    )


def _frame_foreground(foreground: Image.Image, *, target_side: int) -> Image.Image:
    """Centre the extracted product with a consistent breathing room in a square frame."""
    alpha = foreground.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ApiError(
            422,
            "IMAGE_SUBJECT_NOT_CLEAR",
            "We could not clearly find the product. Retake the photo with the product clearly visible.",
        )
    product = foreground.crop(bounds)
    product_width, product_height = product.size
    # The product uses about 78% of the output frame, leaving a clean sales-photo margin.
    target_product_side = max(1, round(target_side * 0.78))
    scale = target_product_side / max(product_width, product_height)
    resized_size = (
        max(1, round(product_width * scale)),
        max(1, round(product_height * scale)),
    )
    product = product.resize(resized_size, Image.Resampling.LANCZOS)
    product_width, product_height = product.size
    frame = Image.new("RGBA", (target_side, target_side), (0, 0, 0, 0))
    offset = ((target_side - product_width) // 2, (target_side - product_height) // 2)
    frame.alpha_composite(product, offset)
    return frame


def _composite_on_neutral(foreground: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", foreground.size, (245, 245, 245, 255))
    return Image.alpha_composite(canvas, foreground).convert("RGB")


def _fit_max_side(image: Image.Image, max_side: int) -> Image.Image:
    if max(image.size) <= max_side:
        return image
    return ImageOps.contain(
        image,
        (max_side, max_side),
        method=Image.Resampling.LANCZOS,
    )


def _jpeg_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def create_image_enhancer(settings: Settings) -> ImageEnhancer:
    if settings.image_enhancement_provider == "rembg":
        return RembgImageEnhancer(settings)
    return MockImageEnhancer(settings.image_enhancement_max_side)


@lru_cache
def get_image_enhancer() -> ImageEnhancer:
    return create_image_enhancer(get_settings())
