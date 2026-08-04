import time
import threading
import subprocess
import queue
import struct
import logging
import numpy as np
import select

from config import logger

class AudioStreamer:
    def __init__(self, rtsp_url, enable_audio=True):
        self.rtsp_url = rtsp_url
        self.running = True
        self.sample_rate = 44100
        self.channels = 1
        self.clients = []
        self.clients_lock = threading.Lock()
        self.client_queue_size = 10
        self.beep_data = self._generate_beep(880, 0.1)
        self.wav_header = self._generate_wav_header()
        self.process = None
        self.enable_audio = enable_audio
        
        if self.enable_audio:
            self.thread = threading.Thread(target=self.capture_audio)
            self.thread.daemon = True
            self.thread.start()
            print("🎵 AudioStreamer initialized (low-latency mode)")
        else:
            # Still start thread for fallback beep
            self.thread = threading.Thread(target=self.capture_audio)
            self.thread.daemon = True
            self.thread.start()
            print("🎵 AudioStreamer initialized (audio disabled, using fallback)")

    def _generate_wav_header(self):
        sample_rate = self.sample_rate
        channels = self.channels
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8

        header = struct.pack(
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

    def _generate_beep(self, frequency, duration):
        try:
            sample_rate = self.sample_rate
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            wave = np.sin(frequency * 2 * np.pi * t) * 0.3
            audio = (wave * 32767).astype(np.int16)
            return audio.tobytes()
        except Exception as e:
            logger.error(f"Error generating beep: {e}")
            return b'\x00' * 1024

    def subscribe_client(self):
        new_queue = queue.Queue(maxsize=self.client_queue_size)
        with self.clients_lock:
            self.clients.append(new_queue)
        return new_queue

    def unsubscribe_client(self, client_queue):
        with self.clients_lock:
            if client_queue in self.clients:
                self.clients.remove(client_queue)

    def _broadcast_chunk(self, data):
        """Broadcasts raw PCM audio chunks safely to all registered client streams."""
        with self.clients_lock:
            disconnected = []
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

    def capture_audio(self):
        if not self.enable_audio:
            print("[AUDIO] Audio disabled, using fallback beep")
            while self.running:
                try:
                    self._broadcast_chunk(self.beep_data)
                    time.sleep(0.05)
                except Exception as e:
                    logger.error(f"Audio fallback error: {e}")
                    break
            return
        
        methods = [
            self._capture_with_ffmpeg,
            self._capture_with_gstreamer,
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

        print("[AUDIO FALLBACK] Entering live fallback test pattern loop...")
        while self.running:
            try:
                self._broadcast_chunk(self.beep_data)
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Audio fallback error: {e}")
                break

    def _capture_with_ffmpeg(self):
        cmd = [
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
            # Use stderr to check for errors
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
                stderr_output = self.process.stderr.read().decode()
                if "Invalid data found when processing input" in stderr_output or \
                   "Stream" in stderr_output and "not found" in stderr_output:
                    print("[AUDIO] No audio stream found, using fallback")
                    self.process = None
                    raise Exception("No audio stream available")

            while self.running:
                try:
                    # Check if process is still running
                    if self.process and self.process.poll() is not None:
                        print("[AUDIO] FFmpeg process ended")
                        break
                    
                    # Read audio data
                    if self.process:
                        rlist, _, _ = select.select([self.process.stdout], [], [], 0.1)
                        if rlist:
                            data = self.process.stdout.read(256)
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
            # Continue to next method or fallback

    def _capture_with_gstreamer(self):
        cmd = [
            "gst-launch-1.0",
            "rtspsrc", f"location={self.rtsp_url}", "protocols=tcp",
            "!", "decodebin",
            "!", "audioconvert",
            "!", "audioresample",
            "!", "audio/x-raw,format=S16LE,rate=44100,channels=1",
            "!", "fdsink"
        ]
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
            )
            while self.running:
                try:
                    data = self.process.stdout.read(256)
                    if not data:
                        break
                    self._broadcast_chunk(data)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    print("[AUDIO] Client disconnected, continuing...")
                    break
                except Exception as e:
                    logger.error(f"[AUDIO] Error reading from GStreamer: {e}")
                    break
                    
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
        except Exception as e:
            logger.error(f"[AUDIO] GStreamer process error: {e}")

    def cleanup(self):
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
        
        with self.clients_lock:
            for q in self.clients:
                try:
                    q.put_nowait(b'')
                except Exception:
                    pass
            self.clients.clear()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        print("🎵 AudioStreamer cleaned up")