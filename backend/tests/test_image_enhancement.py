from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.core.config import Settings
from app.core.errors import ApiError
from app.services.image_enhancement import (
    MockImageEnhancer,
    RembgImageEnhancer,
    create_image_enhancer,
)


def source_image() -> bytes:
    image = Image.new("RGB", (80, 40), (40, 70, 120))
    ImageDraw.Draw(image).rectangle((25, 8, 55, 32), fill=(180, 50, 40))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "image_enhancement_provider": "rembg",
        "rembg_model_cache_dir": tmp_path / "models",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_rembg_provider_removes_background_corrects_image_and_reuses_session(
    tmp_path: Path,
) -> None:
    session = object()
    session_calls: list[str] = []
    remover_calls: list[dict[str, object]] = []

    def session_factory(model: str) -> object:
        session_calls.append(model)
        return session

    def remover(image: Image.Image, **kwargs: object) -> Image.Image:
        remover_calls.append(kwargs)
        cutout = image.convert("RGBA")
        alpha = Image.new("L", cutout.size, 0)
        ImageDraw.Draw(alpha).rectangle((18, 4, 62, 36), fill=255)
        cutout.putalpha(alpha)
        return cutout

    enhancer = RembgImageEnhancer(
        settings(tmp_path),
        remover=remover,
        session_factory=session_factory,
    )

    first = enhancer.enhance(source_image(), "neutral", "marketplace_square")
    second = enhancer.enhance(source_image(), "neutral", "marketplace_square")

    assert session_calls == ["u2net"]
    assert remover_calls == [
        {
            "session": session,
            "alpha_matting": False,
            "post_process_mask": True,
        },
        {
            "session": session,
            "alpha_matting": False,
            "post_process_mask": True,
        },
    ]
    for result in (first, second):
        with Image.open(BytesIO(result)) as image:
            assert image.format == "JPEG"
            assert image.size == (80, 80)
            corner = image.convert("RGB").getpixel((2, 2))
            assert all(235 <= channel <= 250 for channel in corner)


def test_keep_original_skips_background_model_but_runs_local_correction(
    tmp_path: Path,
) -> None:
    def unexpected_remover(*args: object, **kwargs: object) -> object:
        raise AssertionError("Background removal must not run")

    enhancer = RembgImageEnhancer(
        settings(tmp_path),
        remover=unexpected_remover,
        session_factory=lambda model: object(),
    )

    result = enhancer.enhance(source_image(), "keep_original", "keep_original")

    with Image.open(BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.size == (80, 40)


def test_enhancement_caps_working_copy_without_upscaling(tmp_path: Path) -> None:
    real = RembgImageEnhancer(
        settings(tmp_path, image_enhancement_max_side=512),
        remover=lambda image, **kwargs: image.convert("RGBA"),
        session_factory=lambda model: object(),
    )
    mock = MockImageEnhancer(max_side=512)
    large = Image.new("RGB", (1024, 256), (40, 70, 120))
    output = BytesIO()
    large.save(output, format="PNG")

    for result in (
        real.enhance(output.getvalue(), "neutral", "marketplace_square"),
        mock.enhance(output.getvalue(), "neutral", "marketplace_square"),
    ):
        with Image.open(BytesIO(result)) as image:
            assert image.size == (512, 512)


def test_rembg_provider_normalizes_model_failures(tmp_path: Path) -> None:
    enhancer = RembgImageEnhancer(
        settings(tmp_path),
        remover=lambda image, **kwargs: image,
        session_factory=lambda model: (_ for _ in ()).throw(RuntimeError("provider detail")),
    )

    with pytest.raises(ApiError) as error:
        enhancer.enhance(source_image(), "neutral", "marketplace_square")

    assert error.value.code == "AI_SERVICE_UNAVAILABLE"
    assert "provider detail" not in error.value.message


def test_image_enhancer_factory_keeps_deterministic_fallback(tmp_path: Path) -> None:
    assert isinstance(
        create_image_enhancer(settings(tmp_path, image_enhancement_provider="mock")),
        MockImageEnhancer,
    )
    assert isinstance(create_image_enhancer(settings(tmp_path)), RembgImageEnhancer)
