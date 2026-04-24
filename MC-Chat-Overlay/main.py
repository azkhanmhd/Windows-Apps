import tkinter as tk
from tkinter import ttk, colorchooser, filedialog
import os, sys, time, threading, json
import win32gui, win32con
import pystray
from PIL import Image, ImageDraw, ImageTk

# ---------------------------------------------------------------------------
#  Constants & Config
# ---------------------------------------------------------------------------
_DEFAULT_LOG = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")),
    r"AppData\Roaming\.minecraft\logs\latest.log"
)
OVL_TITLE   = "MC_Chat_Overlay"
TRANSPARENT = "#010101"

# Always store config.json next to the .exe (or script when running raw)
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "log_path":       _DEFAULT_LOG,
    "x":             None,
    "y":             None,
    "width":         400,
    "height":        200,
    "font_size":     12,
    "text_color":    "#00FF00",
    "outline_color": "#000000",
    "alpha":         0.85,
    "max_messages":  10,
    "locked":        False,
    "overlay_visible": True,
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
#  Tray icon image (16x16 green chat bubble)
# ---------------------------------------------------------------------------
def make_tray_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 50], fill=(0, 200, 80))
    d.polygon([(16, 48), (8, 62), (30, 50)], fill=(0, 200, 80))
    d.rectangle([14, 18, 50, 24], fill="white")
    d.rectangle([14, 30, 42, 36], fill="white")
    return img

# ---------------------------------------------------------------------------
#  Chat Overlay  (borderless transparent window)
# ---------------------------------------------------------------------------
class ChatOverlay:
    OFFSETS = [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]

    def __init__(self, root, cfg):
        self.root       = root
        self.cfg        = cfg
        self._shadow_ids = []
        self._text_id    = None
        self._drag_x = self._drag_y = 0
        self.on_position_change = None

        self.win = tk.Toplevel(root)
        self.win.title(OVL_TITLE)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.config(bg=TRANSPARENT)
        self.win.attributes("-transparentcolor", TRANSPARENT)
        self.win.attributes("-alpha", cfg["alpha"])

        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        oc = cfg.get("outline_color", "#000000")
        for dx, dy in self.OFFSETS:
            sid = self.canvas.create_text(
                8+dx, 0+dy, text="", anchor="sw",
                font=("Consolas", cfg["font_size"], "bold"),
                fill=oc, width=cfg["width"]-16)
            self._shadow_ids.append(sid)

        self._text_id = self.canvas.create_text(
            8, 0, text="Waiting for MC logs...", anchor="sw",
            font=("Consolas", cfg["font_size"], "bold"),
            fill=cfg["text_color"], width=cfg["width"]-16)

        self.canvas.bind("<ButtonPress-1>",  self._drag_start)
        self.canvas.bind("<B1-Motion>",      self._drag_motion)

        self.win.after(0, self._apply_geometry)
        if cfg.get("locked"):
            self.win.after(100, lambda: self._set_click_through(True))

    # ── geometry ──────────────────────────────────────────────────────────
    def _calc_pos(self):
        cfg  = self.cfg
        w, h = cfg["width"], cfg["height"]
        if cfg.get("x") is not None:
            return cfg["x"], cfg["y"]
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        return sw - w - 10, sh - h - 10

    def _apply_geometry(self):
        cfg  = self.cfg
        w, h = cfg["width"], cfg["height"]
        x, y = self._calc_pos()
        self.win.geometry(f"{w}x{h}+{x}+{y}")

    # ── update from settings ──────────────────────────────────────────────
    def apply_config(self, cfg):
        self.cfg = cfg
        w, h     = cfg["width"], cfg["height"]
        x, y     = self._calc_pos()
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.attributes("-alpha", cfg["alpha"])
        self.canvas.config(width=w, height=h)

        oc = cfg.get("outline_color", "#000000")
        font = ("Consolas", cfg["font_size"], "bold")
        for i, (dx, dy) in enumerate(self.OFFSETS):
            self.canvas.coords(self._shadow_ids[i], 8+dx, h+dy)
            self.canvas.itemconfig(self._shadow_ids[i], font=font, fill=oc, width=w-16)
        self.canvas.coords(self._text_id, 8, h)
        self.canvas.itemconfig(self._text_id, font=font, fill=cfg["text_color"], width=w-16)

        self._set_click_through(cfg.get("locked", False))

    def show(self):
        self.win.deiconify()

    def hide(self):
        self.win.withdraw()

    # ── click-through ─────────────────────────────────────────────────────
    def _set_click_through(self, enabled):
        hwnd = win32gui.FindWindow(None, OVL_TITLE)
        if not hwnd:
            return
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if enabled:
            style |=  win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
        else:
            style &= ~win32con.WS_EX_TRANSPARENT
            style |=  win32con.WS_EX_LAYERED
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

    # ── drag ──────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_x = e.x_root - self.win.winfo_x()
        self._drag_y = e.y_root - self.win.winfo_y()

    def _drag_motion(self, e):
        x = e.x_root - self._drag_x
        y = e.y_root - self._drag_y
        self.win.geometry(f"+{x}+{y}")
        self.cfg["x"] = x
        self.cfg["y"] = y
        save_config(self.cfg)
        if self.on_position_change:
            self.on_position_change(x, y)

    # ── text update ───────────────────────────────────────────────────────
    def set_text(self, text):
        def _do():
            for sid in self._shadow_ids:
                self.canvas.itemconfig(sid, text=text)
            self.canvas.itemconfig(self._text_id, text=text)
        self.win.after(0, _do)


# ---------------------------------------------------------------------------
#  Settings / Control GUI
# ---------------------------------------------------------------------------
class SettingsGUI:
    def __init__(self, root, cfg, overlay, log_watcher):
        self.root        = root
        self.cfg         = cfg
        self.overlay     = overlay
        self.log_watcher = log_watcher
        self._tray       = None

        root.title("MC Chat Overlay — Settings")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        root.bind("<Unmap>",              self._on_unmap)

        pad = {"padx": 10, "pady": 5}

        # ── Position ──────────────────────────────────────────────────────
        pf = ttk.LabelFrame(root, text="Position")
        pf.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(pf, text="X:").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        self.x_var = tk.IntVar(value=cfg.get("x") or 0)
        ttk.Entry(pf, textvariable=self.x_var, width=8).grid(row=0, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(pf, text="Y:").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        self.y_var = tk.IntVar(value=cfg.get("y") or 0)
        ttk.Entry(pf, textvariable=self.y_var, width=8).grid(row=1, column=1, sticky="w", padx=6, pady=2)

        # ── Size ──────────────────────────────────────────────────────────
        sf = ttk.LabelFrame(root, text="Size")
        sf.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(sf, text="Width:").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        self.width_var = tk.IntVar(value=cfg.get("width", 400))
        ttk.Entry(sf, textvariable=self.width_var, width=8).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(sf, text="Height:").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        self.height_var = tk.IntVar(value=cfg.get("height", 200))
        ttk.Entry(sf, textvariable=self.height_var, width=8).grid(row=1, column=1, sticky="w", padx=6)

        # ── Appearance ────────────────────────────────────────────────────
        af = ttk.LabelFrame(root, text="Appearance")
        af.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(af, text="Font Size:").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        self.font_size_var = tk.IntVar(value=cfg.get("font_size", 12))
        ttk.Spinbox(af, from_=8, to=32, textvariable=self.font_size_var, width=6).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(af, text="Text Color:").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        self.text_color_var = tk.StringVar(value=cfg.get("text_color", "#00FF00"))
        self.text_color_btn = tk.Button(af, bg=self.text_color_var.get(), width=6,
                                        command=self._pick_text_color, relief="raised")
        self.text_color_btn.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(af, text="Outline Color:").grid(row=2, column=0, sticky="w", padx=6, pady=2)
        self.outline_color_var = tk.StringVar(value=cfg.get("outline_color", "#000000"))
        self.outline_color_btn = tk.Button(af, bg=self.outline_color_var.get(), width=6,
                                           command=self._pick_outline_color, relief="raised")
        self.outline_color_btn.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(af, text="Opacity:").grid(row=3, column=0, sticky="w", padx=6, pady=2)
        self.alpha_var = tk.DoubleVar(value=cfg.get("alpha", 0.85))
        of = ttk.Frame(af)
        of.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Scale(of, from_=0.1, to=1.0, variable=self.alpha_var,
                  orient="horizontal", length=120).pack(side="left")
        self.alpha_lbl = ttk.Label(of, text=f"{self.alpha_var.get():.0%}", width=5)
        self.alpha_lbl.pack(side="left")
        self.alpha_var.trace_add("write", self._upd_alpha)

        # ── Chat ──────────────────────────────────────────────────────────
        cf = ttk.LabelFrame(root, text="Chat")
        cf.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(cf, text="Log File:").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        self.log_path_var = tk.StringVar(value=cfg.get("log_path", _DEFAULT_LOG))
        lf = ttk.Frame(cf)
        lf.grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        ttk.Entry(lf, textvariable=self.log_path_var, width=28).pack(side="left")
        ttk.Button(lf, text="...", width=3, command=self._browse_log).pack(side="left", padx=(2,0))

        ttk.Label(cf, text="Max Messages:").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        self.max_msg_var = tk.IntVar(value=cfg.get("max_messages", 10))
        ttk.Spinbox(cf, from_=1, to=50, textvariable=self.max_msg_var, width=6).grid(row=1, column=1, sticky="w", padx=6)

        # ── Overlay controls ──────────────────────────────────────────────
        ctl = ttk.LabelFrame(root, text="Overlay")
        ctl.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)

        self.locked_var = tk.BooleanVar(value=cfg.get("locked", False))
        ttk.Checkbutton(ctl, text="Lock (click-through)", variable=self.locked_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=6, pady=2)

        self.visible_var = tk.BooleanVar(value=cfg.get("overlay_visible", True))
        ttk.Checkbutton(ctl, text="Show overlay", variable=self.visible_var,
                        command=self._toggle_overlay_visible).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=6, pady=2)

        # ── Buttons ───────────────────────────────────────────────────────
        bf = ttk.Frame(root)
        bf.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="Apply",        command=self._apply).pack(side="left", padx=6)
        ttk.Button(bf, text="Hide to Tray", command=self._hide_to_tray).pack(side="left", padx=6)
        ttk.Button(bf, text="Exit",         command=self._exit).pack(side="left", padx=6)

        # Start tray in background thread
        threading.Thread(target=self._run_tray, daemon=True).start()

    # ── Tray ──────────────────────────────────────────────────────────────
    def _run_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Open Settings",        self._tray_open, default=True),
            pystray.MenuItem("Show / Hide Overlay",  self._tray_toggle_overlay),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit",                 self._tray_exit),
        )
        self._tray = pystray.Icon("MC Chat Overlay", make_tray_image(), "MC Chat Overlay", menu)
        self._tray.run()

    def _tray_open(self, icon, item):
        self.root.after(0, self._show_settings)

    def _tray_toggle_overlay(self, icon, item):
        self.root.after(0, self._toggle_overlay_visible)

    def _tray_exit(self, icon, item):
        self.root.after(0, self._exit)

    def _show_settings(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _hide_to_tray(self):
        self.root.withdraw()

    def _on_unmap(self, event):
        if event.widget is self.root:
            self.root.withdraw()

    # ── Overlay visibility ────────────────────────────────────────────────
    def _toggle_overlay_visible(self):
        if self.visible_var.get():
            self.overlay.show()
        else:
            self.overlay.hide()
        self.cfg["overlay_visible"] = self.visible_var.get()
        save_config(self.cfg)

    # ── Color pickers ─────────────────────────────────────────────────────
    def _pick_text_color(self):
        c = colorchooser.askcolor(color=self.text_color_var.get(), title="Text Color")[1]
        if c:
            self.text_color_var.set(c)
            self.text_color_btn.config(bg=c)

    def _pick_outline_color(self):
        c = colorchooser.askcolor(color=self.outline_color_var.get(), title="Outline Color")[1]
        if c:
            self.outline_color_var.set(c)
            self.outline_color_btn.config(bg=c)

    def _browse_log(self):
        p = filedialog.askopenfilename(
            title="Select Minecraft log file",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
            initialfile=self.log_path_var.get(),
        )
        if p:
            self.log_path_var.set(p)

    def _on_overlay_drag(self, x, y):
        self.x_var.set(x)
        self.y_var.set(y)

    def _upd_alpha(self, *_):
        self.alpha_lbl.config(text=f"{self.alpha_var.get():.0%}")

    # ── Apply ─────────────────────────────────────────────────────────────
    def _apply(self):
        self.cfg["x"]             = self.x_var.get()
        self.cfg["y"]             = self.y_var.get()
        self.cfg["width"]         = self.width_var.get()
        self.cfg["height"]        = self.height_var.get()
        self.cfg["font_size"]     = self.font_size_var.get()
        self.cfg["text_color"]    = self.text_color_var.get()
        self.cfg["outline_color"] = self.outline_color_var.get()
        self.cfg["alpha"]         = round(self.alpha_var.get(), 2)
        self.cfg["max_messages"]  = self.max_msg_var.get()
        self.cfg["locked"]        = self.locked_var.get()
        self.cfg["overlay_visible"] = self.visible_var.get()
        new_log_path = self.log_path_var.get()
        path_changed  = new_log_path != self.cfg.get("log_path")
        self.cfg["log_path"] = new_log_path
        self.log_watcher.max_messages = self.cfg["max_messages"]
        if path_changed:
            self.log_watcher.restart(new_log_path)
        self.overlay.apply_config(self.cfg)
        save_config(self.cfg)

    # ── Exit ──────────────────────────────────────────────────────────────
    def _exit(self):
        if self._tray:
            self._tray.stop()
        self.root.destroy()


# ---------------------------------------------------------------------------
#  Log Watcher
# ---------------------------------------------------------------------------
class LogWatcher:
    def __init__(self, overlay, cfg):
        self.overlay      = overlay
        self.max_messages = cfg["max_messages"]
        self._log_path    = cfg.get("log_path", _DEFAULT_LOG)
        self._history     = []
        self._stop        = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def restart(self, new_path):
        self._stop.set()
        self._log_path = new_path
        self._history  = []
        self._stop     = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        log_path = self._log_path
        if not os.path.exists(log_path):
            self.overlay.set_text(f"Error: log not found\n{log_path}")
            return
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            while not self._stop.is_set():
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                if "[Render thread/INFO]:" in line and "[CHAT]" in line:
                    msg = line.split("[CHAT]")[1].strip()
                    self._history.append(msg)
                    if len(self._history) > self.max_messages:
                        self._history.pop(0)
                    self.overlay.set_text("\n".join(self._history))


# ---------------------------------------------------------------------------
#  Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cfg = load_config()

    root = tk.Tk()

    # Set taskbar / titlebar icon from the generated tray image
    _icon_img = make_tray_image().resize((32, 32), Image.LANCZOS)
    _tk_icon  = ImageTk.PhotoImage(_icon_img)
    root.iconphoto(True, _tk_icon)

    overlay    = ChatOverlay(root, cfg)
    watcher    = LogWatcher(overlay, cfg)
    settings   = SettingsGUI(root, cfg, overlay, watcher)
    overlay.on_position_change = settings._on_overlay_drag

    if not cfg.get("overlay_visible", True):
        overlay.hide()

    root.mainloop()
