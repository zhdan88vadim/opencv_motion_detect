import time
import threading
import subprocess
import queue
import struct
import select
from typing import Optional, List, Any

from config import logger


class AudioStreamer:
    def __init__(self, rtsp_url: str) -> None:
        self.rtsp_url: str = rtsp_url
        self.running: bool = True
        self.sample_rate: int = 44100
        self.channels: int = 1
        self.clients: List[queue.Queue] = []
        self.clients_lock: threading.Lock = threading.Lock()
        self.client_queue_size: int = 10
        self.wav_header: bytes = self._generate_wav_header()
        self.process: Optional[subprocess.Popen] = None
        self.thread: threading.Thread = threading.Thread(target=self.capture_audio)
        self.thread.daemon = True
        self.thread.start()

    def _generate_wav_header(self) -> bytes:
        sample_rate = self.sample_rate
        channels = self.channels
        bits_per_sample: int = 16
        byte_rate: int = sample_rate * channels * bits_per_sample // 8
        block_align: int = channels * bits_per_sample // 8

        header: bytes = struct.pack(
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
            bits_per_sample,
            b"data",
            0x7FFFFFFF
        )
        return header

    def subscribe_client(self) -> queue.Queue:
        """Subscribe a client to receive audio"""
        new_queue: queue.Queue = queue.Queue(maxsize=self.client_queue_size)
        with self.clients_lock:
            self.clients.append(new_queue)
        return new_queue

    def unsubscribe_client(self, client_queue: queue.Queue) -> None:
        with self.clients_lock:
            if client_queue in self.clients:
                self.clients.remove(client_queue)

    def _broadcast_chunk(self, data: bytes) -> None:
        """Broadcasts raw PCM audio chunks safely to all registered client streams."""
        with self.clients_lock:
            disconnected: List[queue.Queue] = []
            for client_queue in self.clients:
                try:
                    if client_queue.full():
                        try:
                            client_queue.get_nowait()
                        except queue.Empty:
                            pass
                    client_queue.put_nowait(data)
                except Exception:
                    disconnected.append(client_queue)
            # Remove disconnected clients
            for client in disconnected:
                if client in self.clients:
                    try:
                        self.clients.remove(client)
                    except ValueError:
                        pass

    def capture_audio(self) -> None:
        """Capture audio from RTSP stream"""
        methods: List[Any] = [
            self._capture_with_ffmpeg,
        ]
        
        for method in methods:
            if not self.running:
                return
            try:
                print(f"[AUDIO] Launching pipeline: {method.__name__}...")
                method()
                if not self.running:
                    return
            except Exception as e:
                logger.error(f"[AUDIO ERROR] Pipeline {method.__name__} failed: {e}")
                continue

        # If all methods fail, just keep thread alive
        print("[AUDIO] All audio capture methods failed, no audio available")
        while self.running:
            time.sleep(0.1)

    def _capture_with_ffmpeg(self) -> None:
        cmd: List[str] = [
            "ffmpeg", "-loglevel", "error", "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-f", "s16le",
            "-"
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Check if process starts successfully
            time.sleep(0.5)
            if self.process.poll() is not None:
                # Process exited immediately - likely no audio
                if self.process.stderr:
                    stderr_output: str = self.process.stderr.read().decode()
                    if "Invalid data found when processing input" in stderr_output or \
                    "Stream" in stderr_output and "not found" in stderr_output:
                        print("[AUDIO] No audio stream found")
                        self.process = None
                        raise Exception("No audio stream available")

            while self.running and self.process is not None:
                try:
                    # Check if process is still running
                    if self.process.poll() is not None:
                        print("[AUDIO] FFmpeg process ended")
                        break
                    
                    # Read audio data - properly handle stdout
                    if self.process.stdout is not None:
                        rlist, _, _ = select.select([self.process.stdout], [], [], 0.1)
                        if rlist and self.process.stdout is not None:
                            data: Optional[bytes] = self.process.stdout.read(256)
                            if data:
                                self._broadcast_chunk(data)
                            else:
                                break
                except (BrokenPipeError, ConnectionResetError, OSError):
                    print("[AUDIO] Client disconnected")
                    break
                except Exception as e:
                    logger.error(f"[AUDIO] Error reading from FFmpeg: {e}")
                    break
            
            # Clean up process
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except:
                    try:
                        self.process.kill()
                    except:
                        pass
                self.process = None
        except Exception as e:
            logger.error(f"[AUDIO] FFmpeg process error: {e}")

    def cleanup(self) -> None:
        self.running = False
        
        # Kill subprocess
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
        
        # Clear clients
        with self.clients_lock:
            for q in self.clients:
                try:
                    q.put_nowait(b'')
                except Exception:
                    pass
            self.clients.clear()
        
        # Only join thread if it exists and is alive
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        print("🎵 AudioStreamer cleaned up")