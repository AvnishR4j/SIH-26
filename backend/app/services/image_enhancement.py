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
            image = self._remove_background(image)
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
            canvas = Image.new("RGBA", foreground.size, (245, 245, 245, 255))
            return Image.alpha_composite(canvas, foreground).convert("RGB")
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
        return Image.fromarray(sharpened)


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
