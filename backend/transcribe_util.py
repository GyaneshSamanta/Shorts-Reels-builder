import os
import sys
import shutil
import whisper
import torch
import gc

# ── Ensure ffmpeg is available for Whisper ────────────────────────────────
# Whisper calls `ffmpeg` via subprocess.  If it's not installed system-wide,
# we grab the binary bundled inside imageio-ffmpeg and make it available
# as "ffmpeg.exe" on the PATH.
def _ensure_ffmpeg():
    """Create an ffmpeg.exe alias from imageio-ffmpeg if needed."""
    # Quick check: is ffmpeg already available?
    import subprocess
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return  # ffmpeg is already on PATH
    except FileNotFoundError:
        pass

    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe()
        if not os.path.isfile(src):
            return

        # Create a directory inside the project's temp area
        dest_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_ffmpeg_bin")
        dest_dir = os.path.normpath(dest_dir)
        os.makedirs(dest_dir, exist_ok=True)

        dest = os.path.join(dest_dir, "ffmpeg.exe")
        if not os.path.isfile(dest):
            shutil.copy2(src, dest)

        # Prepend to PATH so subprocess can find it
        os.environ["PATH"] = dest_dir + os.pathsep + os.environ.get("PATH", "")
    except Exception as exc:
        print(f"[Warning] Could not set up ffmpeg: {exc}")

_ensure_ffmpeg()

class TranscriptionEngine:
    def __init__(self, model_size="medium"):
        self.model_size = model_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None

    def _load_model(self):
        """Loads the model into VRAM/RAM only when needed."""
        if self.model is None:
            print(f"Loading Whisper '{self.model_size}' model on {self.device}...")
            # Use float16 on CUDA to save VRAM, fallback to float32 on CPU
            fp16 = True if self.device == "cuda" else False
            self.model = whisper.load_model(self.model_size, device=self.device)

    def _unload_model(self):
        """Unloads the model and clears VRAM strictly."""
        if self.model is not None:
            del self.model
            self.model = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()
            print("Whisper model unloaded from VRAM.")

    def transcribe(self, file_path, callback=None):
        """
        Transcribes the given file and returns a list of segment dictionaries.
        Each segment contains: start, end, text.
        """
        import os
        # Normalize path for Windows compatibility
        file_path = os.path.normpath(file_path)
        
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")
        
        try:
            self._load_model()
            
            if callback:
                callback(f"Transcribing: {os.path.basename(file_path)} …")
            
            # Whisper internal FP16 logic handles the inference
            fp16 = True if self.device == "cuda" else False
            result = self.model.transcribe(file_path, fp16=fp16)
            
            # Extract usable segments
            segments = []
            for seg in result["segments"]:
                segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip()
                })
                
            return segments
            
        except Exception as e:
            print(f"Transcription Error: {e}")
            raise e
        finally:
            # Always ensure VRAM is cleared after transcription
            self._unload_model()
