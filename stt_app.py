"""
WhisperType - Speech to Text untuk Windows
Mendukung input: Microphone & Internal Audio (WASAPI Loopback)
Mendukung output: Auto-type & Clipboard Paste
"""

import threading
import time
import queue
import numpy as np
import pyperclip
import pyautogui
import sounddevice as sd
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sys

# ── Coba import Whisper (pilih faster-whisper jika ada) ──────────────────────
try:
    from faster_whisper import WhisperModel
    BACKEND = "faster-whisper"
except ImportError:
    try:
        import whisper
        BACKEND = "whisper"
    except ImportError:
        BACKEND = None

# ── Konstanta ─────────────────────────────────────────────────────────────────
SAMPLERATE   = 16000
CHUNK_SECS   = 0.5          # ukuran chunk buffer (detik)
SILENCE_SECS = 1.5          # diam sekian detik → kirim ke Whisper
SILENCE_THRS = 0.01         # threshold RMS untuk deteksi hening
LANGUAGES    = {
    "Auto-detect": None,
    "Indonesia": "id",
    "English": "en",
    "Melayu": "ms",
    "Jawa": "jv",
}
MODELS = ["tiny", "base", "small", "medium", "large-v3"]


# ─────────────────────────────────────────────────────────────────────────────
class AudioCapture:
    """Rekam audio dari device tertentu secara streaming."""

    def __init__(self, device_index, callback):
        self.device_index = device_index
        self.callback     = callback
        self._stream      = None

    def start(self):
        self._stream = sd.InputStream(
            device=self.device_index,
            samplerate=SAMPLERATE,
            channels=1,
            dtype="float32",
            blocksize=int(SAMPLERATE * CHUNK_SECS),
            callback=self._sd_callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _sd_callback(self, indata, frames, time_info, status):
        self.callback(indata[:, 0].copy())


# ─────────────────────────────────────────────────────────────────────────────
class WhisperTranscriber:
    """Antrian audio → Whisper → teks."""

    def __init__(self, model_name, language, result_callback):
        self.language        = language
        self.result_callback = result_callback
        self._audio_q        = queue.Queue()
        self._buffer         = []
        self._silence_count  = 0
        self._running        = False
        self._model          = None
        self._model_name     = model_name
        self._thread         = None

    def load_model(self, progress_cb=None):
        if progress_cb:
            progress_cb("Memuat model Whisper…")
        if BACKEND == "faster-whisper":
            self._model = WhisperModel(self._model_name, device="cpu",
                                       compute_type="int8")
        elif BACKEND == "whisper":
            self._model = whisper.load_model(self._model_name)
        else:
            raise RuntimeError("Whisper tidak terinstall. "
                               "Jalankan: pip install faster-whisper")

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._audio_q.put(None)  # sentinal

    def feed(self, chunk: np.ndarray):
        self._audio_q.put(chunk)

    # ── worker thread ─────────────────────────────────────────────────────────
    def _worker(self):
        chunks_per_silence = int(SILENCE_SECS / CHUNK_SECS)

        while self._running:
            try:
                chunk = self._audio_q.get(timeout=0.2)
            except queue.Empty:
                continue

            if chunk is None:
                break

            rms = float(np.sqrt(np.mean(chunk ** 2)))
            self._buffer.append(chunk)

            if rms < SILENCE_THRS:
                self._silence_count += 1
            else:
                self._silence_count = 0

            # Kirim ke Whisper saat ada jeda hening
            if self._silence_count >= chunks_per_silence and len(self._buffer) > chunks_per_silence:
                audio_data = np.concatenate(self._buffer[:-chunks_per_silence])
                self._buffer = []
                self._silence_count = 0
                if len(audio_data) / SAMPLERATE > 0.3:   # minimal 0.3 detik
                    self._transcribe(audio_data)

    def _transcribe(self, audio: np.ndarray):
        try:
            if BACKEND == "faster-whisper":
                segments, _ = self._model.transcribe(
                    audio,
                    language=self.language,
                    beam_size=5,
                    vad_filter=True,
                )
                text = " ".join(s.text for s in segments).strip()
            else:
                result = self._model.transcribe(
                    audio,
                    language=self.language or "id",
                )
                text = result["text"].strip()

            if text:
                self.result_callback(text)
        except Exception as e:
            self.result_callback(f"[Error: {e}]")


# ─────────────────────────────────────────────────────────────────────────────
class OutputHandler:
    """Kirim teks ke Notepad / Word / aplikasi apapun yang sedang aktif."""

    def __init__(self, mode="clipboard", delay=0.3):
        self.mode  = mode   # "clipboard" | "autotype"
        self.delay = delay  # detik sebelum output (beri waktu user fokus ke target)

    def send(self, text: str, add_space=True):
        if add_space:
            text = text + " "

        time.sleep(self.delay)

        if self.mode == "clipboard":
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        else:
            # Auto-type — lebih andal pakai clipboard untuk karakter non-ASCII
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            # Fallback pure autotype jika clipboard bermasalah:
            # pyautogui.write(text, interval=0.02)


# ─────────────────────────────────────────────────────────────────────────────
def get_audio_devices():
    """Kembalikan daftar device input + loopback WASAPI."""
    devices = sd.query_devices()
    result  = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            name = d["name"]
            tag  = " 🔁 [Loopback]" if "loopback" in name.lower() else ""
            result.append({"index": i, "name": name + tag, "raw": d})
    return result


# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WhisperType 🎙")
        self.geometry("640x620")
        self.resizable(True, True)
        self.configure(bg="#1a1a2e")

        self._capture     = None
        self._transcriber = None
        self._running     = False
        self._output      = OutputHandler()

        self._build_ui()
        self._refresh_devices()

        # Pastikan model tidak diload di main thread
        self._model_loaded = False

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        BG   = "#1a1a2e"
        CARD = "#16213e"
        ACC  = "#0f3460"
        HL   = "#e94560"
        FG   = "#eaeaea"
        GRAY = "#8892a4"

        self.configure(bg=BG)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame",        background=CARD)
        style.configure("TLabel",        background=CARD,   foreground=FG,   font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=BG,     foreground=FG,   font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel",    background=BG,     foreground=GRAY, font=("Segoe UI", 9))
        style.configure("TCombobox",     fieldbackground=ACC, foreground=FG, background=ACC)
        style.configure("TCheckbutton",  background=CARD,   foreground=FG)
        style.map("TCombobox", fieldbackground=[("readonly", ACC)])

        # Header
        hdr = tk.Frame(self, bg=BG, pady=12)
        hdr.pack(fill="x", padx=20)
        tk.Label(hdr, text="🎙 WhisperType", bg=BG, fg=FG,
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(hdr, text="powered by OpenAI Whisper", bg=BG, fg=GRAY,
                 font=("Segoe UI", 9)).pack(side="left", padx=10, pady=6)

        # Settings card
        card = tk.Frame(self, bg=CARD, padx=16, pady=14,
                        highlightthickness=1, highlightbackground=ACC)
        card.pack(fill="x", padx=20, pady=(0, 10))

        def row(parent, label, widget_fn, col2_span=1):
            r = tk.Frame(parent, bg=CARD)
            r.pack(fill="x", pady=4)
            tk.Label(r, text=label, bg=CARD, fg=GRAY,
                     font=("Segoe UI", 9), width=18, anchor="w").pack(side="left")
            widget_fn(r)

        # Device
        def dev_widget(r):
            self._dev_var = tk.StringVar()
            self._dev_cb  = ttk.Combobox(r, textvariable=self._dev_var,
                                          state="readonly", width=44)
            self._dev_cb.pack(side="left")
            tk.Button(r, text="↻", bg=ACC, fg=FG, relief="flat",
                      command=self._refresh_devices,
                      font=("Segoe UI", 10)).pack(side="left", padx=6)
        row(card, "Sumber Audio", dev_widget)

        # Model
        def model_widget(r):
            self._model_var = tk.StringVar(value="base")
            ttk.Combobox(r, textvariable=self._model_var,
                         values=MODELS, state="readonly", width=14).pack(side="left")
            tk.Label(r, text="  (base = cepat & hemat RAM)", bg=CARD, fg=GRAY,
                     font=("Segoe UI", 8)).pack(side="left")
        row(card, "Model Whisper", model_widget)

        # Language
        def lang_widget(r):
            self._lang_var = tk.StringVar(value="Indonesia")
            ttk.Combobox(r, textvariable=self._lang_var,
                         values=list(LANGUAGES.keys()), state="readonly",
                         width=16).pack(side="left")
        row(card, "Bahasa", lang_widget)

        # Output mode
        def out_widget(r):
            self._out_var = tk.StringVar(value="clipboard")
            tk.Radiobutton(r, text="Clipboard (Ctrl+V)", variable=self._out_var,
                           value="clipboard", bg=CARD, fg=FG,
                           selectcolor=ACC, activebackground=CARD).pack(side="left")
            tk.Radiobutton(r, text="Auto-type", variable=self._out_var,
                           value="autotype", bg=CARD, fg=FG,
                           selectcolor=ACC, activebackground=CARD).pack(side="left", padx=20)
        row(card, "Mode Output", out_widget)

        # Delay
        def delay_widget(r):
            self._delay_var = tk.DoubleVar(value=0.5)
            tk.Scale(r, variable=self._delay_var, from_=0.0, to=3.0,
                     resolution=0.1, orient="horizontal", length=160,
                     bg=CARD, fg=FG, troughcolor=ACC, highlightthickness=0,
                     showvalue=True).pack(side="left")
            tk.Label(r, text="detik delay sebelum output", bg=CARD, fg=GRAY,
                     font=("Segoe UI", 8)).pack(side="left", padx=6)
        row(card, "Output Delay", delay_widget)

        # Add space after transkripsi
        self._space_var = tk.BooleanVar(value=True)
        spf = tk.Frame(card, bg=CARD)
        spf.pack(fill="x", pady=2)
        tk.Label(spf, text="", bg=CARD, width=18).pack(side="left")
        tk.Checkbutton(spf, text="Tambah spasi setelah tiap kalimat",
                       variable=self._space_var, bg=CARD, fg=FG,
                       selectcolor=ACC, activebackground=CARD).pack(side="left")

        # Status bar
        self._status_var = tk.StringVar(value="Siap — klik Mulai Rekam")
        self._status_lbl = tk.Label(self, textvariable=self._status_var,
                                     bg=BG, fg=GRAY, font=("Segoe UI", 9))
        self._status_lbl.pack(fill="x", padx=22)

        # Tombol Mulai/Stop
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=10)

        self._start_btn = tk.Button(
            btn_frame, text="▶  Mulai Rekam", width=18, height=2,
            bg=HL, fg="white", font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", command=self._toggle
        )
        self._start_btn.pack(side="left", padx=8)

        tk.Button(
            btn_frame, text="🗑  Hapus Teks", width=14, height=2,
            bg=ACC, fg=FG, font=("Segoe UI", 10),
            relief="flat", cursor="hand2",
            command=self._clear_text
        ).pack(side="left", padx=8)

        tk.Button(
            btn_frame, text="📋  Copy Semua", width=14, height=2,
            bg=ACC, fg=FG, font=("Segoe UI", 10),
            relief="flat", cursor="hand2",
            command=self._copy_all
        ).pack(side="left", padx=8)

        # Hasil transkripsi
        tk.Label(self, text="Hasil Transkripsi", bg=BG, fg=GRAY,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=22)
        self._text = scrolledtext.ScrolledText(
            self, wrap="word", height=12,
            bg="#0d1117", fg="#c9d1d9", insertbackground="white",
            font=("Segoe UI", 11), relief="flat",
            padx=10, pady=10
        )
        self._text.pack(fill="both", expand=True, padx=20, pady=(4, 16))

        # Tip
        tk.Label(self, text="💡 Tip: Klik di Notepad/Word, lalu tekan Mulai Rekam. "
                             "Teks akan langsung masuk ke sana.",
                 bg=BG, fg=GRAY, font=("Segoe UI", 8),
                 wraplength=600, justify="left").pack(anchor="w", padx=22, pady=(0, 10))

    # ── Device ────────────────────────────────────────────────────────────────
    def _refresh_devices(self):
        self._devices = get_audio_devices()
        names = [d["name"] for d in self._devices]
        self._dev_cb["values"] = names
        if names:
            # Pilih mic default pertama
            self._dev_var.set(names[0])

    def _selected_device_index(self):
        name = self._dev_var.get()
        for d in self._devices:
            if d["name"] == name:
                return d["index"]
        return None

    # ── Toggle rekam ──────────────────────────────────────────────────────────
    def _toggle(self):
        if not self._running:
            self._start()
        else:
            self._stop()

    def _start(self):
        if BACKEND is None:
            messagebox.showerror("Error",
                "Whisper belum terinstall.\n\n"
                "Jalankan di terminal:\n"
                "  pip install faster-whisper\natau\n"
                "  pip install openai-whisper")
            return

        dev_idx = self._selected_device_index()
        if dev_idx is None:
            messagebox.showwarning("Peringatan", "Pilih device audio terlebih dahulu.")
            return

        self._status("Memuat model, harap tunggu…", color="#f0a500")
        self._start_btn.config(state="disabled")
        self.update()

        lang_key = self._lang_var.get()
        language = LANGUAGES.get(lang_key)

        self._output = OutputHandler(
            mode=self._out_var.get(),
            delay=self._delay_var.get()
        )

        def load_and_run():
            try:
                self._transcriber = WhisperTranscriber(
                    model_name=self._model_var.get(),
                    language=language,
                    result_callback=self._on_result,
                )
                self._transcriber.load_model()
                self._transcriber.start()

                self._capture = AudioCapture(
                    device_index=dev_idx,
                    callback=self._transcriber.feed,
                )
                self._capture.start()

                self._running = True
                self.after(0, lambda: (
                    self._start_btn.config(
                        text="⏹  Stop Rekam", bg="#333366", state="normal"),
                    self._status("● Merekam… bicara sekarang", color="#2ecc71"),
                ))
            except Exception as e:
                self.after(0, lambda: (
                    messagebox.showerror("Error", str(e)),
                    self._start_btn.config(state="normal"),
                    self._status("Gagal memulai rekaman"),
                ))

        threading.Thread(target=load_and_run, daemon=True).start()

    def _stop(self):
        self._running = False
        if self._capture:
            self._capture.stop()
            self._capture = None
        if self._transcriber:
            self._transcriber.stop()
            self._transcriber = None
        self._start_btn.config(text="▶  Mulai Rekam", bg="#e94560", state="normal")
        self._status("Dihentikan — klik Mulai Rekam untuk lanjut")

    # ── Callback hasil ────────────────────────────────────────────────────────
    def _on_result(self, text: str):
        # Update UI di main thread
        self.after(0, lambda: self._append_text(text))
        # Kirim ke target window
        threading.Thread(
            target=self._output.send,
            args=(text, self._space_var.get()),
            daemon=True
        ).start()

    def _append_text(self, text: str):
        self._text.insert("end", text + " ")
        self._text.see("end")

    # ── Helper ────────────────────────────────────────────────────────────────
    def _clear_text(self):
        self._text.delete("1.0", "end")

    def _copy_all(self):
        content = self._text.get("1.0", "end").strip()
        if content:
            pyperclip.copy(content)
            self._status("Semua teks disalin ke clipboard ✓", color="#2ecc71")

    def _status(self, msg, color="#8892a4"):
        self._status_var.set(msg)
        self._status_lbl.config(fg=color)

    def on_close(self):
        self._stop()
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
