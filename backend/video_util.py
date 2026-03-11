import os
from PIL import Image

# ── Pillow 10+ compatibility ──────────────────────────────────────────────
# MoviePy 1.0.3 calls PIL.Image.ANTIALIAS which was removed in Pillow 10.
# Monkey-patch it back so .resize() and .on_color() don't crash.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import VideoFileClip


class VideoEngine:
    def __init__(self):
        # Try NVENC first; fall back to libx264 if the GPU encoder is unavailable
        self.codec = self._choose_codec()

    @staticmethod
    def _choose_codec():
        """Pick the best available H.264 encoder."""
        import subprocess
        try:
            r = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if "h264_nvenc" in r.stdout:
                return "h264_nvenc"
        except Exception:
            pass
        return "libx264"

    def process_clip(self, input_path, output_path, start_time, end_time,
                     mode="Crop (Center)", callback=None):
        """
        1. Extracts the subclip.
        2. Applies Crop (Center) or Fit (Add Borders).
        3. Renders via NVENC (or libx264 fallback).
        4. Closes the clip to free memory.
        """
        clip = None
        try:
            if callback:
                callback(f"Loading video: {os.path.basename(input_path)}…")

            clip = VideoFileClip(input_path).subclip(start_time, end_time)
            w, h = clip.size

            # Target 9:16 width based on source height
            target_w = int(h * (9 / 16))

            if mode == "Crop (Center)":
                if w > target_w:
                    x1 = int((w - target_w) / 2)
                    clip = clip.crop(x1=x1, y1=0, x2=x1 + target_w, y2=h)

            elif mode == "Fit (Add Borders)":
                # Shrink the whole frame so width == target_w, then centre
                # on a black 9:16 canvas.
                clip = clip.resize(width=target_w)
                canvas_h = int(target_w * (16 / 9))
                clip = clip.on_color(
                    size=(target_w, canvas_h),
                    color=(0, 0, 0),
                    pos="center",
                )

            if callback:
                callback(f"Rendering ({self.codec}): {os.path.basename(output_path)}…")

            write_kw = dict(
                codec=self.codec,
                audio_codec="aac",
                logger=None,
                threads=4,
            )
            if self.codec == "h264_nvenc":
                write_kw["preset"] = "fast"

            clip.write_videofile(output_path, **write_kw)

        except Exception as e:
            print(f"Video Processing Error for {output_path}: {e}")
            raise
        finally:
            if clip is not None:
                clip.close()

