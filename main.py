import json
import os
import queue
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path
import sys

import keyboard
import mss
import numpy as np
import pystray
import sounddevice as sd
import tkinter as tk
from PIL import Image, ImageTk
from faster_whisper import WhisperModel

__version__ = "1.0.0"

# При запуске как .exe (PyInstaller) __file__ указывает во временный каталог;
# конфиг должен лежать рядом с exe, а не там.
if getattr(sys, "frozen", False):
    _BASE   = Path(sys.executable).parent  # рядом с .exe — для конфига
    _BUNDLE = Path(sys._MEIPASS)           # временный каталог PyInstaller — для ассетов
else:
    _BASE   = Path(__file__).parent
    _BUNDLE = _BASE

CONFIG_PATH = _BASE / "config.json"

DEFAULT_CONFIG = {
    "hotkey": "f9",
    "screenshot_hotkey": "f10",
    "session_id": None,
    "whisper_model": "small",
    "sample_rate": 16000,
    "overlay_opacity": 0.85,
    "auto_hide_seconds": 15,
    "claude_path": "",
}


def _find_claude() -> str:
    import shutil
    found = shutil.which("claude")
    if found:
        return found
    npm_path = Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"
    if npm_path.exists():
        return str(npm_path)
    return "claude"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()


ASSETS = _BUNDLE / "assets"

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW

MOOD_TAG_MAP = {
    "happy":  "claudeHappy",
    "sad":    "claudeSad",
    "angry":  "claudeAngry",
    "shy":    "claudeShy",
    "flirty": "claudeFlirty",
    "lovely": "claudeLovely",
}

VOICE_PREFIX = "[VA] "

def parse_mood(response: str) -> tuple[str, str]:
    """Возвращает (mood_icon_name, text_без_тега)."""
    import re
    m = re.match(r"^\[(\w+)\]\s*", response)
    if m and m.group(1).lower() in MOOD_TAG_MAP:
        mood = MOOD_TAG_MAP[m.group(1).lower()]
        text = response[m.end():]
        return mood, text
    return "claudeHappy", response


class Overlay:
    BG        = "#1e1e1e"
    TRANSP    = "#000001"   # цвет-ключ прозрачности (почти чёрный)
    BORDER    = "#3a3a3a"   # обводка кружков
    RADIUS    = 18          # закругление основного блока
    CIRCLE_R  = 18          # радиус кружков иконки / крестика
    PAD_SIDE  = 14          # отступ кружков от краёв
    WIDTH     = 900

    def __init__(self, root: tk.Tk, config: dict):
        self.root = root
        self.config = config

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", config["overlay_opacity"])
        self.root.configure(bg=self.TRANSP)
        self.root.attributes("-transparentcolor", self.TRANSP)
        self.root.withdraw()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.x = (sw - self.WIDTH) // 2
        self.base_y = sh - 170

        self.canvas = tk.Canvas(
            self.root, bg=self.TRANSP, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        # иконка настроения
        self._icons: dict[str, ImageTk.PhotoImage] = {}
        self._preload_icons()
        self.icon_img_id = None

        # текст
        self.label = tk.Label(
            self.canvas,
            text="",
            bg=self.BG,
            fg="white",
            font=("Segoe UI", 13),
            wraplength=self.WIDTH - (self.PAD_SIDE + self.CIRCLE_R) * 2 - 80,
            justify="center",
            padx=8,
            pady=0,
        )

        # поле ручного ввода
        self.INPUT_H = 38
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            self.canvas,
            textvariable=self.entry_var,
            bg="#2a2a2a",
            fg="white",
            insertbackground="white",
            font=("Segoe UI", 12),
            bd=0,
            highlightthickness=0,
            width=1,
        )
        self.entry.bind("<Return>", self._on_entry_submit)

        self._hide_job = None
        self._on_manual_submit = None

    def _make_circle_img(self, diameter: int, hover: bool = False) -> ImageTk.PhotoImage:
        from PIL import ImageDraw
        scale = 4
        d = diameter * scale
        img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        bg_hex = "#2e2e2e" if hover else self.BG
        bg_c  = tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        brd_c = tuple(int(self.BORDER.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        draw.ellipse([0, 0, d-1, d-1], fill=bg_c, outline=brd_c, width=scale*2)
        img = img.resize((diameter, diameter), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    def _preload_icons(self):
        d = self.CIRCLE_R * 2 - 12
        for path in ASSETS.glob("claude*.png"):
            img = Image.open(path).convert("RGBA").resize((d, d), Image.LANCZOS)
            self._icons[path.stem] = ImageTk.PhotoImage(img)

    def _draw(self, text: str, mood: str):
        from PIL import ImageDraw
        self.canvas.delete("all")
        self._cached_imgs = []

        self.label.config(text=text)
        self.root.update_idletasks()

        text_h = max(self.label.winfo_reqheight(), 20)
        h = text_h + 28
        w = self.WIDTH
        r = self.RADIUS
        cr = self.CIRCLE_R
        ps = self.PAD_SIDE
        cy = h // 2

        ih = self.INPUT_H
        total_h = h + ih + 6  # +6 gap между плашками

        # --- основная плашка с обводкой ---
        bg_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bg_img)
        bg_c  = tuple(int(self.BG.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        brd_c = tuple(int(self.BORDER.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        draw.rounded_rectangle([0, 0, w-1, h-1], radius=r, fill=bg_c, outline=brd_c, width=2)
        bg_tk = ImageTk.PhotoImage(bg_img)
        self._cached_imgs.append(bg_tk)
        self.canvas.create_image(0, 0, anchor="nw", image=bg_tk)

        # --- плашка ввода снизу ---
        inp_img = Image.new("RGBA", (w, ih), (0, 0, 0, 0))
        inp_draw = ImageDraw.Draw(inp_img)
        inp_c = tuple(int("#2a2a2a".lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        inp_draw.rounded_rectangle([0, 0, w-1, ih-1], radius=r, fill=inp_c, outline=brd_c, width=2)
        inp_tk = ImageTk.PhotoImage(inp_img)
        self._cached_imgs.append(inp_tk)
        self.canvas.create_image(0, h + 6, anchor="nw", image=inp_tk)

        # поле ввода внутри плашки
        entry_w = w - 24
        self.canvas.create_window(w // 2, h + 6 + ih // 2, anchor="center",
                                  window=self.entry, width=entry_w)

        # --- кружок иконки (слева) ---
        diam = cr * 2
        ix = ps + cr
        circ = self._make_circle_img(diam)
        self._cached_imgs.append(circ)
        self.canvas.create_image(ix, cy, anchor="center", image=circ)

        icon = self._icons.get(mood) or self._icons.get("claudeHappy")
        if icon:
            self._cached_imgs.append(icon)
            self.canvas.create_image(ix, cy, anchor="center", image=icon)

        # --- текст по центру ---
        self.canvas.create_window(w // 2, cy, anchor="center", window=self.label)

        # --- кружок закрытия (справа) ---
        bx = w - ps - cr
        bcirc_normal = self._make_circle_img(diam, hover=False)
        bcirc_hover  = self._make_circle_img(diam, hover=True)
        self._cached_imgs += [bcirc_normal, bcirc_hover]
        close_bg_id = self.canvas.create_image(bx, cy, anchor="center", image=bcirc_normal, tags="close_circle")

        close_icon = self._icons.get("claudeClose")
        if close_icon:
            self._cached_imgs.append(close_icon)
            self.canvas.create_image(bx, cy, anchor="center", image=close_icon, tags="close_x")
        else:
            self.canvas.create_text(bx, cy, text="×", fill="#888888",
                                    font=("Segoe UI", 14, "bold"), anchor="center", tags="close_x")

        def on_enter(_):
            self.canvas.itemconfig(close_bg_id, image=bcirc_hover)
        def on_leave(_):
            self.canvas.itemconfig(close_bg_id, image=bcirc_normal)

        for tag in ("close_circle", "close_x"):
            self.canvas.tag_bind(tag, "<Button-1>", lambda _: self.hide())
            self.canvas.tag_bind(tag, "<Enter>", on_enter)
            self.canvas.tag_bind(tag, "<Leave>", on_leave)

        return h, total_h

    def show(self, text: str, auto_hide: float = 0.0, mood: str = "claudeHappy"):
        if self._hide_job:
            self.root.after_cancel(self._hide_job)
            self._hide_job = None

        h, total_h = self._draw(text, mood)
        self.root.geometry(f"{self.WIDTH}x{total_h}+{self.x}+{self.base_y - total_h}")
        self.canvas.config(width=self.WIDTH, height=total_h)
        self.root.deiconify()

        if auto_hide > 0:
            self._hide_job = self.root.after(int(auto_hide * 1000), self.hide)

    def _on_entry_submit(self, _=None):
        text = self.entry_var.get().strip()
        if not text or self._on_manual_submit is None:
            return
        self.entry_var.set("")
        self._on_manual_submit(text)

    def set_manual_submit_callback(self, cb):
        self._on_manual_submit = cb

    def hide(self):
        self.root.withdraw()
        self._hide_job = None


class HotkeyCapture(tk.Frame):
    """Кликабельный виджет — нажми чтобы захватить клавишу."""

    def __init__(self, parent, initial: str, **kwargs):
        super().__init__(parent, bg="#2a2a2a",
                         highlightthickness=1, highlightbackground="#3a3a3a", **kwargs)
        self._var = tk.StringVar(value=initial)
        self._capturing = False

        self._lbl = tk.Label(
            self, textvariable=self._var,
            bg="#2a2a2a", fg="white",
            font=("Segoe UI", 11), width=28, anchor="center", cursor="hand2",
        )
        self._lbl.pack(fill="both", expand=True, padx=6, pady=4)
        self._lbl.bind("<Button-1>", self._start)
        self.bind("<Button-1>", self._start)

    def _start(self, _=None):
        if self._capturing:
            return
        self._capturing = True
        self._var.set("нажмите клавишу...")
        self._lbl.config(fg="#F59E0B")
        threading.Thread(target=self._capture, daemon=True).start()

    def _capture(self):
        try:
            key = keyboard.read_key(suppress=False)
            self.after(0, lambda k=key: self._finish(k))
        finally:
            self._capturing = False

    def _finish(self, key: str):
        self._var.set(key)
        self._lbl.config(fg="white")

    def get(self) -> str:
        return self._var.get()


class SettingsWindow:
    FIELDS = [
        ("hotkey",            "Клавиша записи",          "hotkey"),
        ("screenshot_hotkey", "Клавиша скриншота",       "hotkey"),
        ("session_id",        "Session ID",               "text"),
        ("overlay_opacity",   "Прозрачность (0.1–1.0)",  "text"),
        ("auto_hide_seconds", "Авто-скрытие (сек)",      "text"),
        ("claude_path",       "Путь к claude (авто=пусто)", "text"),
        ("whisper_model",     "Модель Whisper",            "text"),
        ("sample_rate",       "Sample rate",              "text"),
    ]

    def __init__(self, parent: tk.Tk, config: dict, on_save):
        self.parent = parent
        self.config = config
        self.on_save = on_save

        self.win = tk.Toplevel(parent)
        self.win.title("Настройки Claude Assistant")
        self.win.resizable(False, False)
        self.win.configure(bg="#1e1e1e")
        self.win.attributes("-topmost", True)

        self._widgets: dict[str, HotkeyCapture | tk.Entry] = {}
        self._vars: dict[str, tk.StringVar] = {}

        for i, (key, label, kind) in enumerate(self.FIELDS):
            tk.Label(
                self.win, text=label, bg="#1e1e1e", fg="white",
                font=("Segoe UI", 11), anchor="w",
            ).grid(row=i, column=0, sticky="w", padx=16, pady=6)

            val = "" if config.get(key) is None else str(config.get(key, ""))

            if kind == "hotkey":
                w = HotkeyCapture(self.win, initial=val)
                w.grid(row=i, column=1, padx=16, pady=6, sticky="ew")
                self._widgets[key] = w
            else:
                var = tk.StringVar(value=val)
                self._vars[key] = var
                tk.Entry(
                    self.win, textvariable=var, bg="#2a2a2a", fg="white",
                    insertbackground="white", font=("Segoe UI", 11),
                    bd=0, highlightthickness=1, highlightbackground="#3a3a3a", width=30,
                ).grid(row=i, column=1, padx=16, pady=6)

        n = len(self.FIELDS)
        tk.Label(
            self.win,
            text="Для вступления изменений в силу перезапустите приложение",
            bg="#1e1e1e", fg="#888",
            font=("Segoe UI", 9),
        ).grid(row=n, column=0, columnspan=2, padx=16, pady=(2, 4))

        btn = tk.Frame(self.win, bg="#1e1e1e")
        btn.grid(row=n + 1, column=0, columnspan=2, pady=(4, 16))
        tk.Button(btn, text="Сохранить", command=self._save,
                  bg="#3a3a3a", fg="white", font=("Segoe UI", 11),
                  bd=0, padx=16, pady=6, cursor="hand2",
                  activebackground="#4a4a4a", activeforeground="white",
                  ).pack(side="left", padx=8)
        tk.Button(btn, text="Отмена", command=self.win.destroy,
                  bg="#2a2a2a", fg="#aaa", font=("Segoe UI", 11),
                  bd=0, padx=16, pady=6, cursor="hand2",
                  activebackground="#3a3a3a", activeforeground="white",
                  ).pack(side="left", padx=8)

        self.win.update_idletasks()
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        w = self.win.winfo_reqwidth()
        h = self.win.winfo_reqheight()
        self.win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _get_raw(self, key: str) -> str:
        if key in self._widgets:
            return self._widgets[key].get().strip()
        return self._vars[key].get().strip()

    def _save(self):
        new_config = {}
        for key, _, kind in self.FIELDS:
            raw = self._get_raw(key)
            orig = self.config.get(key)
            if key == "session_id":
                new_config[key] = raw if raw else None
            elif isinstance(orig, float):
                try:
                    new_config[key] = float(raw)
                except ValueError:
                    new_config[key] = orig
            elif isinstance(orig, int):
                try:
                    new_config[key] = int(raw)
                except ValueError:
                    new_config[key] = orig
            else:
                new_config[key] = raw
        self.on_save(new_config)
        self.win.destroy()


class VoiceAssistant:
    def __init__(self):
        self.config = load_config()
        self.recording = False
        self.audio_chunks: list[np.ndarray] = []
        self.with_screenshot = False
        self._lock = threading.Lock()
        self._ui_queue: queue.Queue = queue.Queue()
        self._current_mood = "claudeHappy"
        self._tray: pystray.Icon | None = None

        print("Загружаю Whisper...")
        self.whisper = WhisperModel(
            self.config["whisper_model"],
            device="cpu",
            compute_type="int8",
        )
        print(f"Готово. F{self.config['hotkey'].upper()} — говорить, "
              f"{self.config['screenshot_hotkey'].upper()} — говорить + скриншот")

        self.root = tk.Tk()
        self.overlay = Overlay(self.root, self.config)
        self.overlay.set_manual_submit_callback(self._on_manual_text)
        self._setup_hotkeys()
        self._setup_tray()

    def _setup_tray(self):
        def get_icon_img():
            from PIL import ImageDraw
            path = ASSETS / f"{self._current_mood}.png"
            if not path.exists():
                path = ASSETS / "claudeHappy.png"
            img = Image.open(path).convert("RGBA").resize((56, 56), Image.LANCZOS)
            canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            # круглая маска чтобы не клипало
            mask = Image.new("L", (64, 64), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 63, 63], fill=255)
            canvas.paste(img, (4, 4), mask=img)
            return canvas

        menu = pystray.Menu(
            pystray.MenuItem("Показать/Скрыть", self._toggle_overlay, default=True),
            pystray.MenuItem("Настройки", self._open_settings),
            pystray.MenuItem("Выход", self._quit),
        )
        self._tray = pystray.Icon("claude.assistant", get_icon_img(), "Claude Assistant", menu)
        self._get_tray_icon = get_icon_img
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _update_tray_icon(self, mood: str):
        self._current_mood = mood
        if self._tray:
            self._tray.icon = self._get_tray_icon()

    def _toggle_overlay(self):
        def _do():
            if self.overlay.root.winfo_viewable():
                self.overlay.hide()
            else:
                self._ui_queue.put(("show", "", 0, "claudeHappy"))
        self.root.after(0, _do)

    def _open_settings(self):
        self.root.after(0, lambda: SettingsWindow(self.root, self.config, self._apply_config))

    def _apply_config(self, new_config: dict):
        old_hotkey = self.config.get("hotkey")
        old_ss_hotkey = self.config.get("screenshot_hotkey")
        self.config.update(new_config)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        if (new_config.get("hotkey") != old_hotkey or
                new_config.get("screenshot_hotkey") != old_ss_hotkey):
            self._rebind_hotkeys()
        self.overlay.root.attributes("-alpha", self.config["overlay_opacity"])

    def _quit(self):
        if self._tray:
            self._tray.stop()
        os._exit(0)

    def _cancel(self):
        with self._lock:
            if not self.recording:
                return
            self.recording = False
        self.audio_chunks = []
        self._ui_queue.put(("show", "отменено", 1.5, "claudeSad"))

    def _on_manual_text(self, text: str):
        self._ui_queue.put(("show", "думаю...", 0, "claudeThinking"))
        threading.Thread(
            target=self._process_text,
            args=(text,),
            daemon=True,
        ).start()

    def _process_text(self, text: str):
        claude_path = self.config.get("claude_path") or _find_claude()
        session_id = self.config.get("session_id")
        prompt = VOICE_PREFIX + text
        cmd = ["cmd", "/c", claude_path, "--dangerously-skip-permissions"]
        if session_id:
            cmd += ["--resume", session_id]
        else:
            cmd += ["--continue"]
        cmd += ["--print", prompt]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", stdin=subprocess.DEVNULL,
                cwd=os.path.expanduser("~"),
                creationflags=_CREATE_NO_WINDOW,
                timeout=120,
            )
            response = result.stdout.strip() or result.stderr.strip() or "Нет ответа"
        except subprocess.TimeoutExpired:
            response = "время ожидания вышло :c"
        mood, response = parse_mood(response)
        self._ui_queue.put(("show", response, 0, mood))

    def _setup_hotkeys(self):
        self._hotkey_hooks = [
            keyboard.on_press_key(self.config["hotkey"],
                                  lambda _: self._start(screenshot=False)),
            keyboard.on_release_key(self.config["hotkey"],
                                    lambda _: self._stop()),
            keyboard.on_press_key(self.config["screenshot_hotkey"],
                                  lambda _: self._start(screenshot=True)),
            keyboard.on_release_key(self.config["screenshot_hotkey"],
                                    lambda _: self._stop()),
            keyboard.on_press_key("escape", lambda _: self._cancel()),
        ]

    def _rebind_hotkeys(self):
        for hook in getattr(self, "_hotkey_hooks", []):
            keyboard.unhook(hook)
        self._setup_hotkeys()

    def _start(self, screenshot: bool):
        with self._lock:
            if self.recording:
                return
            self.recording = True
            self.audio_chunks = []
            self.with_screenshot = screenshot

        self._ui_queue.put(("show", "слушаю...", 0, "claudeListening"))

        def record():
            with sd.InputStream(
                samplerate=self.config["sample_rate"],
                channels=1,
                dtype="float32",
            ) as stream:
                while self.recording:
                    chunk, _ = stream.read(1024)
                    self.audio_chunks.append(chunk.copy())

        self._rec_thread = threading.Thread(target=record, daemon=True)
        self._rec_thread.start()

    def _stop(self):
        with self._lock:
            if not self.recording:
                return
            self.recording = False
            with_screenshot = self.with_screenshot

        self._rec_thread.join()
        chunks = list(self.audio_chunks)
        threading.Thread(
            target=self._process,
            args=(chunks, with_screenshot),
            daemon=True,
        ).start()

    def _take_screenshot(self) -> str:
        path = tempfile.mktemp(suffix=".png")
        with mss.MSS() as sct:
            img = sct.grab(sct.monitors[1])
            mss.tools.to_png(img.rgb, img.size, output=path)
        return path

    def _process(self, chunks: list[np.ndarray], with_screenshot: bool):
        if not chunks:
            self._ui_queue.put(("show", "не расслышала", 2.0, "claudeSad"))
            return

        audio = np.concatenate(chunks).flatten()

        # слишком короткая запись — скорее всего случайное нажатие
        min_samples = int(self.config["sample_rate"] * 0.5)
        if len(audio) < min_samples:
            return

        self._ui_queue.put(("show", "думаю...", 0, "claudeThinking"))
        audio_path = tempfile.mktemp(suffix=".wav")
        with wave.open(audio_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.config["sample_rate"])
            wf.writeframes((audio * 32767).astype(np.int16).tobytes())

        # транскрибирую
        segments, _ = self.whisper.transcribe(audio_path, language="ru")
        text = " ".join(s.text for s in segments).strip()
        os.unlink(audio_path)

        # фильтр галлюцинаций Whisper (пустые, точки, служебные фразы)
        _hallucinations = {"...", "…", ".", ",", "Субтитры", "Продолжение следует"}
        if not text or text in _hallucinations or len(text) < 3:
            print(f"[whisper] пропущено (галлюцинация?): {repr(text)}")
            self._ui_queue.put(("show", "не расслышала", 2.0, "claudeSad"))
            return

        print(f"[whisper] расслышала: {text}")

        # скриншот если нужен
        screenshot_path = None
        if with_screenshot:
            screenshot_path = self._take_screenshot()

        prompt = VOICE_PREFIX + text
        if screenshot_path:
            # форвард-слэши обязательны — обратные ломают @ синтаксис
            prompt += " @" + screenshot_path.replace("\\", "/")

        # вызываю claude
        claude_path = self.config.get("claude_path") or _find_claude()
        session_id = self.config.get("session_id")

        cmd = ["cmd", "/c", claude_path, "--dangerously-skip-permissions"]
        if session_id:
            cmd += ["--resume", session_id]
        else:
            cmd += ["--continue"]
        cmd += ["--print", prompt]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                stdin=subprocess.DEVNULL,
                cwd=os.path.expanduser("~"),
                creationflags=_CREATE_NO_WINDOW,
                timeout=120,
            )
            response = result.stdout.strip() or result.stderr.strip() or "Нет ответа"
        except subprocess.TimeoutExpired:
            response = "время ожидания вышло :c"
        finally:
            if screenshot_path and os.path.exists(screenshot_path):
                os.unlink(screenshot_path)

        mood, response = parse_mood(response)
        self._ui_queue.put(("show", response, 0, mood))

    def run(self):
        def poll():
            while not self._ui_queue.empty():
                item = self._ui_queue.get_nowait()
                action, text, auto_hide, *rest = item
                mood = rest[0] if rest else "claudeHappy"
                if action == "show":
                    self.overlay.show(text, auto_hide, mood)
                    self._update_tray_icon(mood)
            self.root.after(30, poll)

        self.root.after(30, poll)
        self.root.mainloop()


if __name__ == "__main__":
    app = VoiceAssistant()
    app.run()
