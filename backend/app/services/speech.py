from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any, Literal, Protocol
from unicodedata import normalize

from app.core.config import REPOSITORY_ROOT, Settings, get_settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: Literal["hi", "en"]


class SpeechTranscriber(Protocol):
    def transcribe(self, content: bytes, language: Literal["hi", "en"]) -> TranscriptionResult: ...


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Any | None = None
        self._model_lock = Lock()

    def transcribe(self, content: bytes, language: Literal["hi", "en"]) -> TranscriptionResult:
        try:
            model = self._get_model()
            segments, _ = model.transcribe(
                BytesIO(content),
                language=language,
                task="transcribe",
                beam_size=self.settings.whisper_beam_size,
                best_of=self.settings.whisper_beam_size,
                temperature=0.0,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": self.settings.whisper_vad_min_silence_ms,
                },
                condition_on_previous_text=False,
                initial_prompt=self._initial_prompt(language),
            )
            text = normalize(
                "NFC",
                " ".join(segment.text.strip() for segment in segments).strip(),
            )
        except Exception as error:
            raise ApiError(
                503,
                "AI_SERVICE_UNAVAILABLE",
                "Local speech transcription is temporarily unavailable.",
            ) from error
        if not text:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "No clear speech was detected in the voice note.",
            )
        return TranscriptionResult(text=text, language=language)

    @staticmethod
    def _initial_prompt(language: Literal["hi", "en"]) -> str:
        if language == "hi":
            return (
                "यह हिन्दी में भारतीय हस्तशिल्प उत्पाद का स्पष्ट विवरण है। "
                "सामग्री, कारीगरी, रंग, आकार, मात्रा और बनने का समय ठीक से लिखें।"
            )
        return (
            "This is a clear description of an Indian handmade craft product. "
            "Transcribe material, technique, colour, size, quantity, and production time accurately."
        )

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                cache_dir = self._cache_dir()
                cache_dir.mkdir(parents=True, exist_ok=True)
                self._model = WhisperModel(
                    self.settings.whisper_model_size,
                    device=self.settings.whisper_device,
                    compute_type=self.settings.whisper_compute_type,
                    cpu_threads=self.settings.whisper_cpu_threads,
                    download_root=str(cache_dir),
                )
        return self._model

    def _cache_dir(self) -> Path:
        configured = self.settings.whisper_model_cache_dir.expanduser()
        return (
            configured.resolve()
            if configured.is_absolute()
            else (REPOSITORY_ROOT / configured).resolve()
        )


@lru_cache
def get_speech_transcriber() -> FasterWhisperTranscriber:
    return FasterWhisperTranscriber(get_settings())
