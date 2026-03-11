# Technical Specification: PodcastClipper Local

## 1. Environment & Architecture
* **Language:** Python 3.10+
* **Environment:** Mandatory `venv` (virtualenv) isolation. No global pip installs.
* **GUI Framework:** `CustomTkinter` for a modern UI.
* **Packaging:** `PyInstaller` --onefile --noconsole --collect-all "whisper".

## 2. Backend Engine Specifications
### 2.1 Transcription Logic (Whisper)
* **Library:** `openai-whisper`.
* **Hardware Config:** `device="cuda"`, `torch.float16`.
* **Memory Management:** `torch.cuda.empty_cache()` must be called immediately after the `model.transcribe()` function returns its dictionary.

### 2.2 Video Processing (MoviePy + NVENC)
* **Codec:** Must use `h264_nvenc` (NVIDIA Hardware Encoder).
* **Crop Math:**
    * `w, h = clip.size`
    * `target_w = h * (9/16)`
    * `crop_x1 = (w - target_w) / 2`
    * `final_clip = clip.crop(x1=crop_x1, y1=0, width=target_w, height=h)`
* **VRAM Safety:** Process only ONE clip at a time in the loop. Close each clip instance (`clip.close()`) before starting the next to prevent 3050 Ti VRAM overflow.

## 3. UI Component Logic
### 3.1 Sidebar State Management
* The queue must be stored in a Python `List[Dict]`.
* Example: `self.queue = [{'id': str, 'start': float, 'end': float}]`.
* UI must refresh the Sidebar Frame every time `self.queue` is modified (Add/Delete/Move).

### 3.2 Threading
* **Main Thread:** UI responsiveness and Sidebar interactions.
* **Worker Thread:** Whisper transcription and MoviePy rendering.
* Communication via `queue.Queue` or `tkinter.after()` to update progress bars safely.

## 4. Directory Structure
```text
/Project_Root
├── main.py                 # UI and Event Loop
├── backend/
│   ├── transcribe_util.py  # Whisper wrapper
│   └── video_util.py       # MoviePy/FFmpeg logic
├── assets/
│   └── icons/              # Trash, Up, Down icons
├── build_scripts/
│   ├── setup_env.bat       # Venv creation script
│   └── compile_exe.py      # PyInstaller config
└── requirements.txt        # Frozen dependencies