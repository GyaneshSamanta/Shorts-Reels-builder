import os
import sys
import threading
import queue
import time
import collections
import psutil
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
try:
    import GPUtil
    HAS_GPU = True
except ImportError:
    HAS_GPU = False

from backend.transcribe_util import TranscriptionEngine
from backend.video_util import VideoEngine

# --- Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

C = {
    "bg":       "#0C0C0E",
    "panel":    "#141416",
    "card":     "#1F1F23",
    "border":   "#2A2A2E",
    "accent":   "#8B5CF6",
    "accent_h": "#7C3AED",
    "green":    "#10B981",
    "green_h":  "#059669",
    "red":      "#EF4444",
    "red_h":    "#DC2626",
    "txt":      "#FAFAFA",
    "txt2":     "#9CA3AF",
    "txt3":     "#6B7280",
    "link":     "#A78BFA",
}

HISTORY_LEN = 30  # data points for the mini graph

# ─── Info-Button Tooltip ──────────────────────────────────────────────────────
class InfoButton(ctk.CTkButton):
    """A small 'ⓘ' button that shows a tooltip on hover and hides on leave."""
    def __init__(self, master, tip_text, **kw):
        super().__init__(
            master, text="ⓘ", width=22, height=22, corner_radius=11,
            fg_color="transparent", hover_color=C["card"],
            text_color=C["txt3"], font=ctk.CTkFont(size=13), **kw
        )
        self.tip_text = tip_text
        self._tw = None
        self.bind("<Enter>", self._show)
        self.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self._tw:
            return
        x = self.winfo_rootx() + 30
        y = self.winfo_rooty() - 5
        self._tw = tk.Toplevel(self)
        self._tw.wm_overrideredirect(True)
        self._tw.wm_geometry(f"+{x}+{y}")
        self._tw.attributes("-topmost", True)
        lbl = tk.Label(
            self._tw, text=self.tip_text, background="#27272A",
            foreground="#FFFFFF", padx=8, pady=4,
            font=("Segoe UI", 9), wraplength=250, justify="left"
        )
        lbl.pack()

    def _hide(self, event=None):
        if self._tw:
            self._tw.destroy()
            self._tw = None


# ─── Section Header Helper ─────────────────────────────────────────────────
def section_header(parent, title, tip=None):
    """Creates a styled heading row with optional info button."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=20, pady=(18, 4))
    ctk.CTkLabel(
        row, text=title,
        font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
        text_color=C["txt"]
    ).pack(side="left")
    if tip:
        InfoButton(row, tip).pack(side="left", padx=6)
    return row


# ═══════════════════════════════════════════════════════════════════════════════
class PodcastClipperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.title("Podcast-to-Shorts")
        self.geometry("1440x820")
        self.minsize(1100, 650)
        self.configure(fg_color=C["bg"])

        # ── State ──
        self.input_file = None
        self.output_dir = None
        self.transcription_data = []
        self.clip_queue = []
        self.queue_counter = 1
        self.msg_queue = queue.Queue()

        # Resource history for graphs
        self.cpu_hist = collections.deque([0]*HISTORY_LEN, maxlen=HISTORY_LEN)
        self.ram_hist = collections.deque([0]*HISTORY_LEN, maxlen=HISTORY_LEN)

        self._build_ui()
        self.after(100, self._poll_queue)

        self.monitor_active = True
        threading.Thread(target=self._resource_loop, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  UI Construction
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # ── Main PanedWindow (resizable) ──
        self.pw = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashwidth=6,
            bg=C["border"], bd=0, handlesize=0
        )
        self.pw.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 4))

        # Three pane frames
        self.left_frame  = ctk.CTkFrame(self.pw, fg_color=C["panel"], corner_radius=14)
        self.center_frame = ctk.CTkFrame(self.pw, fg_color=C["panel"], corner_radius=14)
        self.right_frame  = ctk.CTkFrame(self.pw, fg_color=C["panel"], corner_radius=14)

        self.pw.add(self.left_frame,   minsize=280, stretch="always")
        self.pw.add(self.center_frame, minsize=260, stretch="middle")
        self.pw.add(self.right_frame,  minsize=280, stretch="always")

        self._build_left()
        self._build_center()
        self._build_right()
        self._build_footer()

    # ── Left Pane ─────────────────────────────────────────────────────────
    def _build_left(self):
        section_header(self.left_frame, "Transcription",
                       "Click any timestamp block to add it to the clip queue on the right.")
        ctk.CTkLabel(
            self.left_frame, text="AI-generated speech segments appear here after transcription.",
            text_color=C["txt3"], font=ctk.CTkFont(size=11)
        ).pack(padx=20, anchor="w", pady=(0, 6))

        self.transcript_scroll = ctk.CTkScrollableFrame(
            self.left_frame, fg_color="transparent",
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent"]
        )
        self.transcript_scroll.pack(expand=True, fill="both", padx=8, pady=(4, 10))

    # ── Center Pane ───────────────────────────────────────────────────────
    def _build_center(self):
        section_header(self.center_frame, "Controls",
                       "Follow steps 1-4 from top to bottom to generate your shorts.")

        # Step 1
        self._step_label(self.center_frame, "STEP 1")
        self.btn_load = ctk.CTkButton(
            self.center_frame, text="Load Source Video",
            font=ctk.CTkFont(weight="bold"), height=42, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_h"],
            command=self._load_video
        )
        self.btn_load.pack(padx=20, fill="x", pady=(0, 2))
        self.lbl_input = ctk.CTkLabel(
            self.center_frame, text="No video selected",
            text_color=C["txt3"], font=ctk.CTkFont(size=11)
        )
        self.lbl_input.pack(pady=(0, 14))

        # Step 2
        self._step_label(self.center_frame, "STEP 2")
        self.btn_output = ctk.CTkButton(
            self.center_frame, text="Set Output Folder",
            font=ctk.CTkFont(weight="bold"), height=42, corner_radius=8,
            fg_color=C["card"], hover_color="#2A2A2E",
            border_width=1, border_color=C["border"],
            command=self._set_output_dir
        )
        self.btn_output.pack(padx=20, fill="x", pady=(0, 2))
        self.lbl_output = ctk.CTkLabel(
            self.center_frame, text="No directory selected",
            text_color=C["txt3"], font=ctk.CTkFont(size=11)
        )
        self.lbl_output.pack(pady=(0, 14))

        # Step 3
        self._step_label(self.center_frame, "STEP 3")
        self.btn_transcribe = ctk.CTkButton(
            self.center_frame, text="Generate Transcript",
            font=ctk.CTkFont(weight="bold"), height=42, corner_radius=8,
            fg_color="transparent", border_width=2, border_color=C["accent"],
            hover_color=C["card"], command=self._start_transcription
        )
        self.btn_transcribe.pack(padx=20, fill="x", pady=(0, 14))

        # Step 4
        self._step_label(self.center_frame, "STEP 4")
        self.btn_render = ctk.CTkButton(
            self.center_frame, text="Batch Render Queue",
            font=ctk.CTkFont(weight="bold"), height=42, corner_radius=8,
            fg_color=C["green"], hover_color=C["green_h"],
            text_color="#FFFFFF", command=self._start_rendering
        )
        self.btn_render.pack(padx=20, fill="x", pady=(0, 10))

        # Progress
        self.progressbar = ctk.CTkProgressBar(
            self.center_frame, progress_color=C["accent"], fg_color=C["card"]
        )
        self.progressbar.pack(side="bottom", padx=20, fill="x", pady=(0, 14))
        self.progressbar.set(0)
        self.lbl_status = ctk.CTkLabel(
            self.center_frame, text="Awaiting input…",
            text_color=C["txt2"], font=ctk.CTkFont(size=11)
        )
        self.lbl_status.pack(side="bottom", pady=(0, 6))

    def _step_label(self, parent, text):
        ctk.CTkLabel(
            parent, text=text,
            text_color=C["accent"], font=ctk.CTkFont(size=10, weight="bold")
        ).pack(padx=22, anchor="w", pady=(6, 2))

    # ── Right Pane ────────────────────────────────────────────────────────
    def _build_right(self):
        section_header(self.right_frame, "Clip Queue",
                       "Each clip can have its own framing mode. Use ↑↓ to reorder, or delete clips.")

        ctk.CTkLabel(
            self.right_frame,
            text="Add clips manually below, or click transcript blocks.",
            text_color=C["txt3"], font=ctk.CTkFont(size=11)
        ).pack(padx=20, anchor="w", pady=(0, 8))

        # Manual add row
        add_row = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        add_row.pack(fill="x", padx=14, pady=(0, 6))
        self.entry_start = ctk.CTkEntry(
            add_row, placeholder_text="Start (s)", width=80,
            corner_radius=6, fg_color=C["card"], border_width=1, border_color=C["border"]
        )
        self.entry_start.pack(side="left", padx=2)
        self.entry_end = ctk.CTkEntry(
            add_row, placeholder_text="End (s)", width=80,
            corner_radius=6, fg_color=C["card"], border_width=1, border_color=C["border"]
        )
        self.entry_end.pack(side="left", padx=2)
        ctk.CTkButton(
            add_row, text="+ Add", width=70, corner_radius=6,
            fg_color=C["accent"], hover_color=C["accent_h"],
            command=self._manual_add
        ).pack(side="left", padx=(6, 0), fill="x", expand=True)

        self.queue_scroll = ctk.CTkScrollableFrame(
            self.right_frame, fg_color="transparent",
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent"]
        )
        self.queue_scroll.pack(expand=True, fill="both", padx=8, pady=(0, 10))
        self._refresh_queue()

    # ── Footer ────────────────────────────────────────────────────────────
    def _build_footer(self):
        import webbrowser
        ft = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=10, height=70)
        ft.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        ft.grid_propagate(False)

        # Left side – links
        left = ctk.CTkFrame(ft, fg_color="transparent")
        left.pack(side="left", padx=16, pady=8)
        ctk.CTkLabel(left, text="Built with <3 by Gyanesh  •",
                     text_color=C["txt3"], font=ctk.CTkFont(size=11)).pack(side="left")
        lf = ctk.CTkFont(size=11, underline=True)
        for name, url in [
            ("LinkedIn", "https://www.linkedin.com/in/gyanesh-samanta/"),
            ("GitHub",   "https://github.com/GyaneshSamanta"),
            ("Newsletter", "https://www.linkedin.com/newsletters/gyanesh-on-product-6979386586404651008/"),
        ]:
            lbl = ctk.CTkLabel(left, text=name, text_color=C["link"], cursor="hand2", font=lf)
            lbl.pack(side="left", padx=5)
            lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open_new(u))

        # Right side – resource text + mini graph
        right = ctk.CTkFrame(ft, fg_color="transparent")
        right.pack(side="right", padx=16, pady=4)

        self.lbl_res = ctk.CTkLabel(
            right, text="CPU 0% • RAM 0 GB • VRAM N/A",
            text_color=C["txt3"], font=ctk.CTkFont(size=10, family="Consolas")
        )
        self.lbl_res.pack(anchor="e")

        self.canvas_graph = tk.Canvas(
            right, width=180, height=32, bg=C["panel"],
            highlightthickness=0, bd=0
        )
        self.canvas_graph.pack(anchor="e", pady=(2, 0))

    # ─────────────────────────────────────────────────────────────────────────
    #  Resource Monitoring
    # ─────────────────────────────────────────────────────────────────────────
    def _resource_loop(self):
        while self.monitor_active:
            try:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().used / (1024**3)
                vram = "N/A"
                if HAS_GPU:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        vram = f"{gpus[0].memoryUsed}MB"
                self.cpu_hist.append(cpu)
                self.ram_hist.append(ram)
                self.msg_queue.put({
                    "type": "res",
                    "txt": f"CPU {cpu:.0f}%  •  RAM {ram:.1f} GB  •  VRAM {vram}"
                })
            except Exception:
                pass
            time.sleep(2)

    def _draw_graph(self):
        c = self.canvas_graph
        c.delete("all")
        w, h = 180, 32
        # CPU line (purple)
        pts = list(self.cpu_hist)
        if len(pts) > 1:
            step = w / (len(pts) - 1)
            coords = []
            for i, v in enumerate(pts):
                coords.append(i * step)
                coords.append(h - (v / 100) * h)
            c.create_line(coords, fill=C["accent"], width=1.5, smooth=True)
        # RAM line (green) – normalise to 32 GB max
        pts_r = list(self.ram_hist)
        if len(pts_r) > 1:
            step = w / (len(pts_r) - 1)
            coords = []
            for i, v in enumerate(pts_r):
                coords.append(i * step)
                coords.append(h - (min(v, 32) / 32) * h)
            c.create_line(coords, fill=C["green"], width=1.5, smooth=True)

    def destroy(self):
        self.monitor_active = False
        super().destroy()

    # ─────────────────────────────────────────────────────────────────────────
    #  Message Queue
    # ─────────────────────────────────────────────────────────────────────────
    def _log(self, msg):
        self.msg_queue.put({"type": "log", "msg": msg})

    def _poll_queue(self):
        try:
            while not self.msg_queue.empty():
                m = self.msg_queue.get_nowait()
                t = m["type"]
                if t == "log":
                    self.lbl_status.configure(text=m["msg"])
                elif t == "progress":
                    self.progressbar.set(m["val"])
                elif t == "transcribe_done":
                    self._populate_transcript()
                elif t == "render_done":
                    messagebox.showinfo("Done", "All clips rendered successfully!")
                elif t == "error":
                    messagebox.showerror("Error", m["msg"])
                elif t == "res":
                    self.lbl_res.configure(text=m["txt"])
                    self._draw_graph()
        except Exception:
            pass
        self.after(100, self._poll_queue)

    # ─────────────────────────────────────────────────────────────────────────
    #  File I/O
    # ─────────────────────────────────────────────────────────────────────────
    def _load_video(self):
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[("Video Files", "*.mp4 *.mkv *.mov")]
        )
        if path:
            # Normalize to platform path (Whisper needs backslash on Windows)
            self.input_file = os.path.normpath(path)
            name = os.path.basename(self.input_file)
            self.lbl_input.configure(text=name if len(name) <= 35 else f"…{name[-32:]}")
            self._log(f"Loaded: {name}")

    def _set_output_dir(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir = os.path.normpath(path)
            name = os.path.basename(self.output_dir)
            self.lbl_output.configure(text=name if len(name) <= 35 else f"…{name[-32:]}")
            self._log("Output folder set.")

    # ─────────────────────────────────────────────────────────────────────────
    #  Transcription
    # ─────────────────────────────────────────────────────────────────────────
    def _start_transcription(self):
        if not self.input_file:
            messagebox.showwarning("Missing File", "Please load a video first.")
            return
        if not os.path.isfile(self.input_file):
            messagebox.showerror("File Not Found",
                                 f"Cannot access:\n{self.input_file}\n\nMake sure the file exists.")
            return
        self.btn_transcribe.configure(state="disabled")
        self.progressbar.configure(mode="indeterminate")
        self.progressbar.start()
        threading.Thread(target=self._worker_transcribe, daemon=True).start()

    def _worker_transcribe(self):
        try:
            self._log("Loading Whisper model (this may take a minute)…")
            engine = TranscriptionEngine(model_size="medium")
            self._log("Model loaded. Transcribing audio…")
            segs = engine.transcribe(self.input_file, callback=self._log)
            self.transcription_data = segs
            self._log(f"Transcription complete — {len(segs)} segments found.")
            self.msg_queue.put({"type": "transcribe_done"})
        except Exception as e:
            self.msg_queue.put({"type": "error", "msg": f"Transcription failed:\n{e}"})
            self._log("Transcription failed.")
        finally:
            def _reset():
                self.progressbar.stop()
                self.progressbar.configure(mode="determinate")
                self.progressbar.set(0)
                self.btn_transcribe.configure(state="normal")
            self.after(0, _reset)

    def _populate_transcript(self):
        for w in self.transcript_scroll.winfo_children():
            w.destroy()
        if not self.transcription_data:
            return
        for seg in self.transcription_data:
            ts = f"[{seg['start']:.1f}s – {seg['end']:.1f}s]"
            txt = seg["text"][:90]
            frame = ctk.CTkFrame(self.transcript_scroll, fg_color=C["card"], corner_radius=8)
            frame.pack(fill="x", pady=3, padx=4)
            btn = ctk.CTkButton(
                frame, text=f"{ts}  {txt}", anchor="w",
                fg_color="transparent", hover_color="#2A2A30",
                text_color=C["txt"], font=ctk.CTkFont(size=12),
                command=lambda s=seg["start"], e=seg["end"]: self._add_clip(s, e)
            )
            btn.pack(fill="x", padx=4, pady=6)

    # ─────────────────────────────────────────────────────────────────────────
    #  Queue Management
    # ─────────────────────────────────────────────────────────────────────────
    def _add_clip(self, start, end):
        label = f"Clip {self.queue_counter}"
        self.queue_counter += 1
        self.clip_queue.append({
            "id": str(time.time()),
            "start": round(float(start), 2),
            "end": round(float(end), 2),
            "label": label,
            "mode": "Crop (Center)"
        })
        self._refresh_queue()

    def _manual_add(self):
        try:
            s = float(self.entry_start.get())
            e = float(self.entry_end.get())
            if s >= e:
                raise ValueError
            self._add_clip(s, e)
            self.entry_start.delete(0, "end")
            self.entry_end.delete(0, "end")
        except ValueError:
            messagebox.showwarning("Invalid", "Enter valid Start and End seconds (Start < End).")

    def _del_clip(self, cid):
        self.clip_queue = [c for c in self.clip_queue if c["id"] != cid]
        self._refresh_queue()

    def _move_clip(self, cid, direction):
        idx = next((i for i, c in enumerate(self.clip_queue) if c["id"] == cid), -1)
        if idx == -1:
            return
        if direction == "up" and idx > 0:
            self.clip_queue[idx], self.clip_queue[idx-1] = self.clip_queue[idx-1], self.clip_queue[idx]
        elif direction == "down" and idx < len(self.clip_queue) - 1:
            self.clip_queue[idx], self.clip_queue[idx+1] = self.clip_queue[idx+1], self.clip_queue[idx]
        self._refresh_queue()

    def _set_clip(self, cid, key, val):
        for c in self.clip_queue:
            if c["id"] == cid:
                if key in ("start", "end"):
                    try:
                        c[key] = round(float(val), 2)
                    except ValueError:
                        pass
                else:
                    c[key] = val
                break

    def _refresh_queue(self):
        for w in self.queue_scroll.winfo_children():
            w.destroy()
        for clip in self.clip_queue:
            self._queue_card(clip)

    def _queue_card(self, clip):
        card = ctk.CTkFrame(
            self.queue_scroll, fg_color=C["card"], corner_radius=10,
            border_color=C["border"], border_width=1
        )
        card.pack(fill="x", pady=5, padx=4)

        # Row 1 – label + controls
        r1 = ctk.CTkFrame(card, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(r1, text=clip["label"],
                     font=ctk.CTkFont(weight="bold", size=13)).pack(side="left")
        ctk.CTkButton(
            r1, text="✕", width=26, height=22, corner_radius=6,
            fg_color=C["red"], hover_color=C["red_h"],
            font=ctk.CTkFont(size=11),
            command=lambda: self._del_clip(clip["id"])
        ).pack(side="right", padx=(4, 0))
        ctk.CTkButton(
            r1, text="↓", width=26, height=22,
            fg_color="#2A2A2E", hover_color="#3A3A3E",
            command=lambda: self._move_clip(clip["id"], "down")
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            r1, text="↑", width=26, height=22,
            fg_color="#2A2A2E", hover_color="#3A3A3E",
            command=lambda: self._move_clip(clip["id"], "up")
        ).pack(side="right", padx=2)

        # Row 2 – timestamps + mode
        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(r2, text="In:", font=ctk.CTkFont(size=10),
                     text_color=C["txt3"]).pack(side="left")
        e_s = ctk.CTkEntry(r2, width=52, height=22, justify="center",
                           fg_color=C["bg"], border_width=0)
        e_s.insert(0, str(clip["start"]))
        e_s.bind("<FocusOut>", lambda ev: self._set_clip(clip["id"], "start", e_s.get()))
        e_s.pack(side="left", padx=(2, 8))

        ctk.CTkLabel(r2, text="Out:", font=ctk.CTkFont(size=10),
                     text_color=C["txt3"]).pack(side="left")
        e_e = ctk.CTkEntry(r2, width=52, height=22, justify="center",
                           fg_color=C["bg"], border_width=0)
        e_e.insert(0, str(clip["end"]))
        e_e.bind("<FocusOut>", lambda ev: self._set_clip(clip["id"], "end", e_e.get()))
        e_e.pack(side="left", padx=(2, 8))

        mode_var = ctk.StringVar(value=clip.get("mode", "Crop (Center)"))
        ctk.CTkOptionMenu(
            r2, values=["Crop (Center)", "Fit (Add Borders)"],
            variable=mode_var, width=130, height=22,
            font=ctk.CTkFont(size=10),
            fg_color="#2A2A2E", button_color="#3A3A3E",
            button_hover_color="#4A4A4E",
            command=lambda v: self._set_clip(clip["id"], "mode", v)
        ).pack(side="right")

    # ─────────────────────────────────────────────────────────────────────────
    #  Rendering
    # ─────────────────────────────────────────────────────────────────────────
    def _start_rendering(self):
        if not self.input_file or not self.output_dir:
            messagebox.showwarning("Missing", "Set both video and output folder first.")
            return
        if not self.clip_queue:
            messagebox.showwarning("Empty", "Add at least one clip to the queue.")
            return
        self.btn_render.configure(state="disabled")
        self.progressbar.set(0)
        self.progressbar.configure(mode="determinate")
        threading.Thread(target=self._worker_render, daemon=True).start()

    def _worker_render(self):
        try:
            engine = VideoEngine()
            total = len(self.clip_queue)
            for i, clip in enumerate(self.clip_queue):
                name = f"{clip['label'].replace(' ', '_')}.mp4"
                out = os.path.join(self.output_dir, name)
                mode = clip.get("mode", "Crop (Center)")
                self._log(f"Rendering {i+1}/{total}: {name} [{mode}]")
                engine.process_clip(self.input_file, out, clip["start"], clip["end"], mode=mode)
                self.msg_queue.put({"type": "progress", "val": (i+1)/total})
            self._log("All clips rendered.")
            self.msg_queue.put({"type": "render_done"})
        except Exception as e:
            self.msg_queue.put({"type": "error", "msg": str(e)})
            self._log("Render failed.")
        finally:
            self.after(0, lambda: (self.btn_render.configure(state="normal"),
                                   self.progressbar.set(1.0)))


if __name__ == "__main__":
    app = PodcastClipperApp()
    app.mainloop()
