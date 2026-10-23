from __future__ import annotations

import contextlib
import logging
import queue
import struct
import subprocess
import threading

log = logging.getLogger(__name__)


def wav_header(sample_rate: int = 44100, channels: int = 1, bits: int = 16) -> bytes:
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        0xFFFFFFFF,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        0x7FFFFFFF,
    )


class AudioService:
    def __init__(self, rtsp_url: str, sample_rate: int = 44100, channels: int = 1) -> None:
        self.rtsp_url = rtsp_url
        self.sample_rate = sample_rate
        self.channels = channels
        self.header = wav_header(sample_rate, channels)
        self._clients: list[queue.Queue[bytes]] = []
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[bytes] | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="audio", daemon=True)
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.5)
            except Exception:
                with contextlib.suppress(Exception):
                    self._proc.kill()
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)
        with self._lock:
            self._clients.clear()

    def subscribe(self) -> queue.Queue[bytes]:
        q: queue.Queue[bytes] = queue.Queue(maxsize=32)
        with self._lock:
            self._clients.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[bytes]) -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def _run(self) -> None:
        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            self.rtsp_url,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(self.sample_rate),
            "-ac",
            str(self.channels),
            "-f",
            "s16le",
            "-",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
            )
        except Exception as e:
            log.warning("ffmpeg not available: %s", e)
            self._available = False
            return

        assert self._proc.stdout is not None
        assert self._proc.stderr is not None

        def drain() -> None:
            assert self._proc and self._proc.stderr
            for line in iter(self._proc.stderr.readline, b""):
                if b"No such" in line or b"Invalid data" in line:
                    log.info("Audio: no stream (%s)", line.decode(errors="ignore").strip())
                    self._available = False

        threading.Thread(target=drain, daemon=True).start()

        got_data = False
        while not self._stop.is_set():
            chunk = self._proc.stdout.read(4096)
            if not chunk:
                break
            got_data = True
            with self._lock:
                dead: list[queue.Queue[bytes]] = []
                for q in self._clients:
                    if q.full():
                        with contextlib.suppress(queue.Empty):
                            q.get_nowait()
                    try:
                        q.put_nowait(chunk)
                    except queue.Full:
                        dead.append(q)
                for q in dead:
                    self._clients.remove(q)

        if not self._stop.is_set() and not got_data:
            self._available = False
