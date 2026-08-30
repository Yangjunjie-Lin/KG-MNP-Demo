"""WAV container metadata parser; no speech recognition."""

import wave
from io import BytesIO

from kg_mnp.plugins.errors import PluginError
from kg_mnp.plugins.models import ParsedUnit, ParseRequest


class WavMetadataParser:
    def parse(self, request: ParseRequest) -> tuple[ParsedUnit, ...]:
        try:
            with wave.open(BytesIO(request.content), "rb") as wav:
                channels = wav.getnchannels()
                sample_rate = wav.getframerate()
                frame_count = wav.getnframes()
                sample_width = wav.getsampwidth()
        except (wave.Error, EOFError) as exc:
            raise PluginError(f"corrupt WAV: {exc}") from exc
        duration_ms = 0 if sample_rate == 0 else frame_count * 1000 // sample_rate
        if duration_ms > request.limits.max_audio_duration_ms:
            raise PluginError("AUDIO_DURATION_LIMIT_EXCEEDED")
        entries = (
            ("channels", channels), ("sample_rate", sample_rate),
            ("frame_count", frame_count), ("sample_width", sample_width),
            ("duration_ms", duration_ms),
        )
        return (ParsedUnit("audio-metadata", None, {"locator_kind": "time-range", "start_ms": 0, "end_ms": max(duration_ms, 1)}, "audio/wav", 0, entries, ("MISSING_TRANSCRIPTION_PROVIDER",)),)
