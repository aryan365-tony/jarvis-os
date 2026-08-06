"""Phase 5: voice pipeline state machine + barge-in (fake engines, no audio)."""

import asyncio

import pytest

from jarvis.eventbus import EventBus
from jarvis.events import VOICE_ACTIVITY, VoicePhase
from jarvis.voice.pipeline import VoicePipeline


class FakeWake:
    def __init__(self, fires: int = 1):
        self._fires = fires
        self.barge = False

    async def wait_for_wake(self):
        if self._fires <= 0:
            # block "forever" so run() can be cancelled cleanly
            await asyncio.sleep(3600)
        self._fires -= 1

    def barge_in_detected(self):
        return self.barge


class FakeSTT:
    def __init__(self, text="hello jarvis"):
        self.text = text

    async def listen_and_transcribe(self):
        return self.text


class FakeSpeaker:
    def __init__(self, hang=False):
        self.spoken = []
        self.hang = hang
        self.cancelled = False

    async def speak(self, q):
        try:
            while True:
                tok = await q.get()
                if tok is None:
                    break
                self.spoken.append(tok)
            if self.hang:
                await asyncio.sleep(3600)  # simulate long TTS for barge-in test
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    def barge_in_detected(self):
        return False


async def _collect_phases(bus, seen):
    sub = bus.subscribe(VOICE_ACTIVITY)
    with sub:
        async for _topic, payload in sub:
            seen.append(payload.phase)


async def test_full_cycle_reaches_all_phases():
    bus = EventBus()
    seen = []
    collector = asyncio.create_task(_collect_phases(bus, seen))
    await asyncio.sleep(0)

    tokens_sent = []

    async def agent_turn(transcript, on_token):
        assert transcript == "hello jarvis"
        for t in ("Hi", " there."):
            tokens_sent.append(t)
            await on_token(t)
        return "Hi there."

    speaker = FakeSpeaker()
    pipe = VoicePipeline(bus, FakeWake(fires=1), FakeSTT(), speaker, agent_turn)

    async def stop_after():
        # let one interaction complete, then stop the idle wait
        await asyncio.sleep(0.2)
        pipe.request_stop()

    stopper = asyncio.create_task(stop_after())
    # FakeWake blocks forever after first fire; cancel the run once done.
    run_task = asyncio.create_task(pipe.run())
    await asyncio.sleep(0.3)
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass
    stopper.cancel()
    collector.cancel()

    assert speaker.spoken == ["Hi", " there."]
    for phase in (VoicePhase.LISTENING, VoicePhase.THINKING, VoicePhase.SPEAKING, VoicePhase.IDLE):
        assert phase in seen


async def test_barge_in_cancels_speech():
    bus = EventBus()

    async def agent_turn(transcript, on_token):
        await on_token("speaking...")
        return "speaking..."

    wake = FakeWake(fires=1)
    speaker = FakeSpeaker(hang=True)  # TTS would run long
    pipe = VoicePipeline(bus, wake, FakeSTT(), speaker, agent_turn)

    run_task = asyncio.create_task(pipe.run())
    await asyncio.sleep(0.15)
    wake.barge = True  # user interrupts
    await asyncio.sleep(0.2)
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    assert speaker.cancelled is True
