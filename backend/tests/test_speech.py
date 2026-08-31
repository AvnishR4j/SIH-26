from types import SimpleNamespace

from app.core.config import get_settings
from app.services.speech import FasterWhisperTranscriber


class RecordingModel:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def transcribe(self, content: object, **kwargs: object) -> tuple[list[object], object]:
        del content
        self.kwargs = kwargs
        return [SimpleNamespace(text=" यह हाथ से बुना दुपट्टा है। ")], object()


def test_hindi_transcription_uses_accuracy_focused_decoding() -> None:
    settings = get_settings().model_copy(
        update={"whisper_beam_size": 8, "whisper_vad_min_silence_ms": 500}
    )
    transcriber = FasterWhisperTranscriber(settings)
    model = RecordingModel()
    transcriber._model = model

    result = transcriber.transcribe(b"voice", "hi")

    assert result.text == "यह हाथ से बुना दुपट्टा है।"
    assert result.language == "hi"
    assert model.kwargs is not None
    assert model.kwargs["language"] == "hi"
    assert model.kwargs["task"] == "transcribe"
    assert model.kwargs["beam_size"] == 8
    assert model.kwargs["temperature"] == 0.0
    assert model.kwargs["vad_filter"] is True
    assert model.kwargs["vad_parameters"] == {"min_silence_duration_ms": 500}
    assert "हस्तशिल्प" in str(model.kwargs["initial_prompt"])
