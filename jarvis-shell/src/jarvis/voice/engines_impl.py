"""Concrete voice engines (Phase 5): openWakeWord, faster-whisper, piper.

Design note
-----------
These implement the pipeline Protocols using real libraries, but every import
and device access is guarded so a missing engine/mic degrades to text rather
than crashing. They are only constructed when ``engines.py`` reports the
dependency present, so importing this module is always safe.

Audio format: 16 kHz mono float32, the common denominator for openWakeWord and
faster-whisper. sounddevice provides capture/playback.
"""

from __future__ import annotations

import asyncio
import logging

from . import engines

log = logging.getLogger("jarvis.voice.engines_impl")

SAMPLE_RATE = 16000
FRAME = 1280  # 80 ms at 16 kHz — openWakeWord's expected chunk


class OpenWakeWordDetector:
    """Fires when the wake phrase is heard; doubles as the barge-in VAD."""

    def __init__(self, wake_word: str = "jarvis") -> None:
        import numpy as np  # noqa: F401  (ensured available by engines.wake_available)
        import sounddevice as sd  # noqa: F401
        from openwakeword.model import Model  # type: ignore

        self._sd = sd
        self._np = __import__("numpy")
        self._model = Model()  # bundled default models incl. "hey jarvis"
        self._wake_word = wake_word
        self._recent_level = 0.0

    async def wait_for_wake(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._blocking_wait)

    def _blocking_wait(self) -> None:
        with self._sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=FRAME
        ) as stream:
            while True:
                data, _ = stream.read(FRAME)
                mono = data[:, 0]
                self._recent_level = float(min(1.0, (mono ** 2).mean() ** 0.5 * 8))
                pcm = (mono * 32767).astype(self._np.int16)
                scores = self._model.predict(pcm)
                if any(v > 0.5 for v in scores.values()):
                    return

    def barge_in_detected(self) -> bool:
        # Simple energy gate; a full impl would run the model concurrently.
        return self._recent_level > 0.15


class WhisperTranscriber:
    def __init__(self) -> None:
        import sounddevice as sd  # noqa: F401
        from faster_whisper import WhisperModel  # type: ignore

        self._sd = sd
        self._np = __import__("numpy")
        size = engines.recommend_whisper_size()
        self._model = WhisperModel(size, device="auto", compute_type="int8")
        log.info("faster-whisper model=%s loaded", size)

    async def listen_and_transcribe(self) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._blocking_listen)

    def _blocking_listen(self, max_seconds: float = 8.0, silence_s: float = 0.8) -> str:
        frames = []
        silent = 0.0
        with self._sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=FRAME
        ) as stream:
            elapsed = 0.0
            while elapsed < max_seconds:
                data, _ = stream.read(FRAME)
                mono = data[:, 0]
                frames.append(mono.copy())
                rms = float((mono ** 2).mean() ** 0.5)
                silent = silent + FRAME / SAMPLE_RATE if rms < 0.01 else 0.0
                elapsed += FRAME / SAMPLE_RATE
                if silent >= silence_s and elapsed > 1.0:
                    break
        if not frames:
            return ""
        audio = self._np.concatenate(frames)
        segments, _ = self._model.transcribe(audio, language=None)
        return " ".join(s.text for s in segments).strip()


class PiperSpeaker:
    def __init__(self, voice_model: str = "") -> None:
        import sounddevice as sd  # noqa: F401
        from piper.voice import PiperVoice  # type: ignore

        self._sd = sd
        self._np = __import__("numpy")
        self._voice = PiperVoice.load(voice_model) if voice_model else None
        self._interrupt = False

    def barge_in_detected(self) -> bool:
        return self._interrupt

    async def speak(self, text_stream: "asyncio.Queue[str | None]") -> None:
        self._interrupt = False
        buffer = ""
        while True:
            tok = await text_stream.get()
            if tok is None:
                break
            buffer += tok
            # Speak at sentence boundaries so speech stays natural but prompt.
            if any(buffer.rstrip().endswith(p) for p in (".", "!", "?", "\n")):
                await self._flush(buffer)
                buffer = ""
        if buffer.strip():
            await self._flush(buffer)

    async def _flush(self, text: str) -> None:
        if not text.strip() or self._voice is None:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._blocking_say, text)

    def _blocking_say(self, text: str) -> None:
        for chunk in self._voice.synthesize_stream_raw(text):  # type: ignore[union-attr]
            if self._interrupt:
                return
            audio = self._np.frombuffer(chunk, dtype=self._np.int16)
            self._sd.play(audio, samplerate=22050)
            self._sd.wait()
