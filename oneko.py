from __future__ import annotations

import json
import math
import os
import random
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

try:
    from PIL import Image, ImageGrab, ImageSequence, ImageTk
except ImportError:  # Optional: used only for resting on screen progress lines.
    Image = None
    ImageGrab = None
    ImageSequence = None
    ImageTk = None


APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ASSET_DIR = APP_DIR / "oneko_assets"
PET_DIR = ASSET_DIR / "oneko"
PREVIEW_DIR = ASSET_DIR / "preview"
ICON_PATH = APP_DIR / "oneko_icon.png"
SAVE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Oneko"
SAVE_FILE = SAVE_DIR / "partner_progress.json"

FRAME_SIZE = 32
TICK_MS = 90
LEVEL_UP_TICKS = max(1, round(10 * 60 * 1000 / TICK_MS))
TRANSPARENT_COLOR = "#ff00ff"
DEFAULT_CURSOR_GAP = 76
MOUSE_STILL_PIXELS = 3
MOUSE_REST_TICKS = 32
LINE_SCAN_INTERVAL = 8
LINE_SCAN_RADIUS_X = 340
LINE_SCAN_RADIUS_Y = 210
FREE_MODE_MIN_TICKS = max(1, round(5000 / TICK_MS))
FREE_MODE_MAX_TICKS = max(FREE_MODE_MIN_TICKS, round(10000 / TICK_MS))
TOPMOST_REFRESH_TICKS = max(1, round(1200 / TICK_MS))
FOOD_SIZE = 34
TOY_SIZE = 24

PREVIEW_GIFS = {
    "Overview": "preview.gif",
    "Picker": "picker.gif",
    "Classic": "kuroneko.gif",
    "Drag 1": "drag-1.gif",
    "Drag 2": "drag-2.gif",
    "Double click": "double-click.gif",
}

SPRITES = {
    "idle": [(-3, -3)],
    "alert": [(-7, -3)],
    "sleeping": [(-2, 0), (-2, -1)],
    "N": [(-1, -2), (-1, -3)],
    "NE": [(0, -2), (0, -3)],
    "E": [(-3, 0), (-3, -1)],
    "SE": [(-5, -1), (-5, -2)],
    "S": [(-6, -3), (-7, -2)],
    "SW": [(-5, -3), (-6, -1)],
    "W": [(-4, -2), (-4, -3)],
    "NW": [(-1, 0), (-1, -1)],
}


@dataclass(frozen=True)
class PetAsset:
    name: str
    path: Path


@dataclass(frozen=True)
class RestLine:
    x1: int
    x2: int
    y: int


class PartnerProgress:
    def __init__(self) -> None:
        self.level = 1
        self.ticks_until_level = LEVEL_UP_TICKS
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.level = max(1, int(data.get("level", 1)))
        self.ticks_until_level = max(1, int(data.get("ticks_until_level", LEVEL_UP_TICKS)))

    def tick(self) -> bool:
        self.ticks_until_level -= 1
        if self.ticks_until_level > 0:
            return False
        self.level += 1
        self.ticks_until_level = LEVEL_UP_TICKS
        self.save()
        return True

    def save(self) -> None:
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            SAVE_FILE.write_text(
                json.dumps(
                    {
                        "level": self.level,
                        "ticks_until_level": self.ticks_until_level,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def label(self) -> str:
        minutes = max(1, round(self.ticks_until_level * TICK_MS / 60000))
        return f"Partner's level: {self.level} | next in ~{minutes}m"


class SpriteSheet:
    def __init__(self, root: tk.Misc, path: Path, scale: int) -> None:
        self.root = root
        self.path = path
        self.scale = scale
        self.source = tk.PhotoImage(master=root, file=str(path))
        self.frames = self._build_frames()

    @property
    def size(self) -> int:
        return FRAME_SIZE * self.scale

    def get(self, action: str, index: int) -> tk.PhotoImage:
        frames = self.frames[action]
        return frames[index % len(frames)]

    def _build_frames(self) -> dict[str, list[tk.PhotoImage]]:
        frames: dict[str, list[tk.PhotoImage]] = {}
        for action, positions in SPRITES.items():
            frames[action] = []
            for col_offset, row_offset in positions:
                frame = tk.PhotoImage(
                    master=self.root,
                    width=FRAME_SIZE,
                    height=FRAME_SIZE,
                )
                x = abs(col_offset) * FRAME_SIZE
                y = abs(row_offset) * FRAME_SIZE
                frame.tk.call(
                    frame,
                    "copy",
                    self.source,
                    "-from",
                    x,
                    y,
                    x + FRAME_SIZE,
                    y + FRAME_SIZE,
                    "-to",
                    0,
                    0,
                )
                if self.scale > 1:
                    frame = frame.zoom(self.scale, self.scale)
                frames[action].append(frame)
        return frames


class AnimatedGif(ttk.Label):
    def __init__(self, parent: tk.Misc, gif_path: Path, delay_ms: int = 75, max_size: tuple[int, int] | None = None) -> None:
        super().__init__(parent)
        self.delay_ms = delay_ms
        self.max_size = max_size
        self.frames = self._load_frames(gif_path)
        self.index = 0
        self.after_id: str | None = None
        if self.frames:
            self.configure(image=self.frames[0])
            self.after_id = self.after(self.delay_ms, self._advance)

    def _load_frames(self, gif_path: Path) -> list[tk.PhotoImage]:
        if Image is not None and ImageSequence is not None and ImageTk is not None:
            return self._load_frames_with_pillow(gif_path)

        frames: list[tk.PhotoImage] = []
        index = 0
        while True:
            try:
                frames.append(
                    tk.PhotoImage(
                        master=self,
                        file=str(gif_path),
                        format=f"gif -index {index}",
                    )
                )
            except tk.TclError:
                break
            index += 1
        return frames

    def _load_frames_with_pillow(self, gif_path: Path) -> list[tk.PhotoImage]:
        frames: list[tk.PhotoImage] = []
        source = Image.open(gif_path)
        max_size = getattr(self, "max_size", None)
        for frame in ImageSequence.Iterator(source):
            image = frame.convert("RGBA")
            if max_size is not None:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            frames.append(ImageTk.PhotoImage(image, master=self))
        duration = source.info.get("duration")
        if isinstance(duration, int) and duration > 0:
            self.delay_ms = max(35, duration)
        return frames

    def _advance(self) -> None:
        if not self.frames:
            return
        self.index = (self.index + 1) % len(self.frames)
        self.configure(image=self.frames[self.index])
        self.after_id = self.after(self.delay_ms, self._advance)

    def destroy(self) -> None:
        if self.after_id is not None:
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
        super().destroy()


class OnekoApp:
    def __init__(self) -> None:
        self.assets = self._discover_assets()
        self.progress = PartnerProgress()
        self.root = tk.Tk()
        self.root.title("Oneko App")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self._set_window_icon()

        self.pet_choice = tk.StringVar(value=self.assets[0].name)
        self.speed = tk.DoubleVar(value=10.0)
        self.scale = tk.IntVar(value=2)
        self.mode = tk.StringVar(value="follow")
        self.cursor_gap = tk.IntVar(value=DEFAULT_CURSOR_GAP)
        self.cursor_gap_label = tk.StringVar()
        self.line_resting = tk.BooleanVar(value=True)
        self.keep_above_games = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Ready")
        self.partner_level = tk.StringVar(value=self.progress.label())
        self.preview_choice = tk.StringVar(value="Overview")

        self.sheet = SpriteSheet(self.root, self.assets[0].path, self.scale.get())
        self.pet_x = float(self.root.winfo_screenwidth() // 2)
        self.pet_y = float(self.root.winfo_screenheight() // 2)
        self.dragging = False
        self.drag_offset = (0, 0)
        self.action = "idle"
        self.frame_index = 0
        self.idle_ticks = 0
        self.mouse_still_ticks = 0
        self.last_cursor: tuple[int, int] | None = None
        self.line_scan_ticks = 0
        self.rest_line: RestLine | None = None
        self.force_action_ticks = 0
        self.force_action: str | None = None
        self.play_ticks = 0
        self.interaction: str | None = None
        self.food_target: tuple[float, float] | None = None
        self.food_ticks = 0
        self.effect_ticks = 0
        self.previous_mode: str | None = None
        self.free_ticks = 0
        self.free_activity = "rest"
        self.free_target: tuple[float, float] | None = None
        self.topmost_ticks = 0
        self.partner_save_ticks = 0

        self.pet = tk.Toplevel(self.root)
        self.pet.overrideredirect(True)
        self.pet.attributes("-topmost", True)
        self.pet.configure(bg=TRANSPARENT_COLOR)
        try:
            self.pet.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass

        self.pet_label = tk.Label(
            self.pet,
            bg=TRANSPARENT_COLOR,
            bd=0,
            highlightthickness=0,
        )
        self.pet_label.pack()
        self.pet_label.bind("<ButtonPress-1>", self._start_drag)
        self.pet_label.bind("<B1-Motion>", self._drag)
        self.pet_label.bind("<ButtonRelease-1>", self._end_drag)
        self.pet_label.bind("<Double-Button-1>", self._show_controls)
        self.pet_label.bind("<Button-3>", self._show_pet_menu)

        self._configure_style()
        self._build_props()
        self._build_pet_menu()
        self._build_controls()
        self._update_cursor_gap_label()
        self._apply_pet_image()
        self._tick()

    def run(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        self.progress.save()
        self.root.destroy()

    def _discover_assets(self) -> list[PetAsset]:
        assets = [
            PetAsset(path.stem.removeprefix("oneko-").title(), path)
            for path in sorted(PET_DIR.glob("*.gif"))
        ]
        if not assets:
            raise FileNotFoundError(f"No pet GIFs found in {PET_DIR}")
        return assets

    def _set_window_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        try:
            icon = tk.PhotoImage(master=self.root, file=str(ICON_PATH))
            self.root.iconphoto(True, icon)
            self.root._oneko_icon = icon
        except tk.TclError:
            pass

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(bg="#f7f8fb")
        style.configure("Panel.TFrame", background="#f7f8fb")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Preview.TFrame", background="#111827", relief="flat")
        style.configure("Title.TLabel", background="#f7f8fb", foreground="#111827", font=("Segoe UI", 19, "bold"))
        style.configure("Subtitle.TLabel", background="#f7f8fb", foreground="#667085", font=("Segoe UI", 9))
        style.configure("Section.TLabel", background="#f7f8fb", foreground="#344054", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#f7f8fb", foreground="#344054")
        style.configure("Card.TLabel", background="#ffffff", foreground="#344054")
        style.configure("TCheckbutton", background="#f7f8fb")
        style.configure("TRadiobutton", background="#f7f8fb")
        style.configure("TButton", padding=(10, 6))

    def _build_props(self) -> None:
        self.food = tk.Toplevel(self.root)
        self.food.overrideredirect(True)
        self.food.attributes("-topmost", True)
        self.food.configure(bg=TRANSPARENT_COLOR)
        try:
            self.food.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.food_canvas = tk.Canvas(
            self.food,
            width=FOOD_SIZE,
            height=FOOD_SIZE,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.food_canvas.pack()
        self.food_canvas.create_oval(4, 17, 30, 29, fill="#f4d35e", outline="#a86f00", width=2)
        self.food_canvas.create_arc(5, 8, 29, 30, start=0, extent=180, fill="#fff4c2", outline="#a86f00", width=2)
        self.food.withdraw()

        self.toy = tk.Toplevel(self.root)
        self.toy.overrideredirect(True)
        self.toy.attributes("-topmost", True)
        self.toy.configure(bg=TRANSPARENT_COLOR)
        try:
            self.toy.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.toy_canvas = tk.Canvas(
            self.toy,
            width=TOY_SIZE,
            height=TOY_SIZE,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.toy_canvas.pack()
        self.toy_canvas.create_oval(4, 4, 20, 20, fill="#e5484d", outline="#8a1c21", width=2)
        self.toy_canvas.create_line(7, 17, 18, 6, fill="#ffd166", width=2)
        self.toy.withdraw()

        self.effect = tk.Toplevel(self.root)
        self.effect.overrideredirect(True)
        self.effect.attributes("-topmost", True)
        self.effect.configure(bg=TRANSPARENT_COLOR)
        try:
            self.effect.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.effect_label = tk.Label(
            self.effect,
            text="purr",
            bg=TRANSPARENT_COLOR,
            fg="#d6336c",
            font=("Segoe UI", 11, "bold"),
            bd=0,
        )
        self.effect_label.pack()
        self.effect.withdraw()

    def _build_controls(self) -> None:
        container = ttk.Frame(self.root, padding=18, style="Panel.TFrame")
        container.grid(row=0, column=0, sticky="nsew")

        preview_card = ttk.Frame(container, padding=10, style="Preview.TFrame")
        preview_card.grid(row=0, column=0, rowspan=14, padx=(0, 18), sticky="n")
        self.preview_holder = ttk.Frame(preview_card, style="Preview.TFrame")
        self.preview_holder.grid(row=0, column=0, sticky="n")
        self.preview_widget: AnimatedGif | None = None
        self._load_preview()
        preview_select = ttk.Combobox(
            preview_card,
            textvariable=self.preview_choice,
            values=list(PREVIEW_GIFS),
            state="readonly",
            width=18,
        )
        preview_select.grid(row=1, column=0, pady=(10, 0), sticky="ew")
        preview_select.bind("<<ComboboxSelected>>", lambda _event: self._load_preview())

        ttk.Label(container, text="Oneko", style="Title.TLabel").grid(
            row=0,
            column=1,
            sticky="w",
        )
        ttk.Label(container, textvariable=self.status, style="Subtitle.TLabel").grid(
            row=1,
            column=1,
            pady=(2, 0),
            sticky="w",
        )
        ttk.Label(container, textvariable=self.partner_level, style="Subtitle.TLabel").grid(
            row=2,
            column=1,
            pady=(2, 0),
            sticky="w",
        )
        pet_select = ttk.Combobox(
            container,
            textvariable=self.pet_choice,
            values=[asset.name for asset in self.assets],
            state="readonly",
            width=18,
        )
        pet_select.grid(row=3, column=1, pady=(14, 0), sticky="ew")
        pet_select.bind("<<ComboboxSelected>>", lambda _event: self._reload_sheet())

        ttk.Label(container, text="Mode", style="Section.TLabel").grid(row=4, column=1, pady=(14, 0), sticky="w")
        mode_buttons = ttk.Frame(container, style="Panel.TFrame")
        mode_buttons.grid(row=5, column=1, sticky="ew")
        for column, (label, value) in enumerate((("Follow", "follow"), ("Free", "free"), ("Rest", "rest"))):
            ttk.Radiobutton(
                mode_buttons,
                text=label,
                value=value,
                variable=self.mode,
                command=self._mode_changed,
            ).grid(row=0, column=column, padx=(0, 10), sticky="w")

        ttk.Label(container, text="Speed", style="Section.TLabel").grid(row=6, column=1, pady=(14, 0), sticky="w")
        ttk.Scale(
            container,
            from_=4,
            to=22,
            variable=self.speed,
            orient="horizontal",
        ).grid(row=7, column=1, sticky="ew")

        ttk.Label(container, text="Mouse space", style="Section.TLabel").grid(row=8, column=1, pady=(14, 0), sticky="w")
        space_controls = ttk.Frame(container, style="Panel.TFrame")
        space_controls.grid(row=9, column=1, sticky="ew")
        space_scale = ttk.Scale(
            space_controls,
            from_=8,
            to=220,
            variable=self.cursor_gap,
            orient="horizontal",
            command=lambda _value: self._update_cursor_gap_label(),
        )
        space_scale.grid(row=0, column=0, sticky="ew")
        tk.Spinbox(
            space_controls,
            from_=8,
            to=220,
            increment=1,
            width=5,
            textvariable=self.cursor_gap,
            command=self._update_cursor_gap_label,
            justify="center",
            relief="flat",
        ).grid(row=0, column=1, padx=(10, 0), sticky="e")
        ttk.Label(space_controls, textvariable=self.cursor_gap_label).grid(row=1, column=0, columnspan=2, pady=(4, 0), sticky="w")
        space_controls.columnconfigure(0, weight=1)
        self.cursor_gap.trace_add("write", lambda *_args: self._update_cursor_gap_label())

        ttk.Checkbutton(
            container,
            text="Stay above fullscreen apps",
            variable=self.keep_above_games,
        ).grid(row=10, column=1, pady=(12, 0), sticky="w")

        ttk.Label(container, text="Size", style="Section.TLabel").grid(row=11, column=1, pady=(14, 0), sticky="w")
        size_buttons = ttk.Frame(container, style="Panel.TFrame")
        size_buttons.grid(row=12, column=1, sticky="ew")
        for column, value in enumerate((1, 2, 3)):
            ttk.Radiobutton(
                size_buttons,
                text=f"{value}x",
                value=value,
                variable=self.scale,
                command=self._reload_sheet,
            ).grid(row=0, column=column, padx=(0, 8), sticky="w")

        ttk.Checkbutton(
            container,
            text="Rest on progress lines",
            variable=self.line_resting,
            command=self._line_rest_changed,
        ).grid(row=13, column=1, pady=(14, 0), sticky="w")

        ttk.Label(container, text="Care", style="Section.TLabel").grid(row=14, column=1, pady=(14, 0), sticky="w")
        care_buttons = ttk.Frame(container, style="Panel.TFrame")
        care_buttons.grid(row=15, column=1, sticky="ew")
        ttk.Button(care_buttons, text="Feed", command=self._feed_pet).grid(row=0, column=0, sticky="ew")
        ttk.Button(care_buttons, text="Play", command=self._play_with_pet).grid(row=0, column=1, padx=(8, 0), sticky="ew")
        ttk.Button(care_buttons, text="Pet", command=self._pet_pet).grid(row=0, column=2, padx=(8, 0), sticky="ew")
        care_buttons.columnconfigure((0, 1, 2), weight=1)

        buttons = ttk.Frame(container, style="Panel.TFrame")
        buttons.grid(row=16, column=1, pady=(16, 0), sticky="ew")
        ttk.Button(buttons, text="Normal", command=self._normal_mode).grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ttk.Button(buttons, text="Hide", command=self.root.withdraw).grid(
            row=0,
            column=1,
            padx=(8, 0),
            sticky="ew",
        )
        ttk.Button(buttons, text="Quit", command=self.quit).grid(
            row=0,
            column=2,
            padx=(8, 0),
            sticky="ew",
        )
        buttons.columnconfigure((0, 1, 2), weight=1)

        container.columnconfigure(1, weight=1)

    def _build_pet_menu(self) -> None:
        self.pet_menu = tk.Menu(self.pet, tearoff=0)
        self.pet_menu.add_command(label="Normal mode", command=self._normal_mode)
        self.pet_menu.add_separator()
        self.pet_menu.add_command(label="Feed", command=self._feed_pet)
        self.pet_menu.add_command(label="Play with mouse", command=self._play_with_pet)
        self.pet_menu.add_command(label="Pet", command=self._pet_pet)
        self.pet_menu.add_command(label="Rest here", command=self._rest_here)
        self.pet_menu.add_separator()
        self.pet_menu.add_command(label="Show panel", command=self._show_controls)
        self.pet_menu.add_command(label="Quit", command=self.quit)

    def _load_preview(self) -> None:
        if self.preview_widget is not None:
            self.preview_widget.destroy()
        filename = PREVIEW_GIFS.get(self.preview_choice.get(), "preview.gif")
        preview_path = PREVIEW_DIR / filename
        if preview_path.exists():
            self.preview_widget = AnimatedGif(self.preview_holder, preview_path, max_size=(245, 235))
            self.preview_widget.grid(row=0, column=0, sticky="n")
        else:
            self.preview_widget = None

    def _update_cursor_gap_label(self) -> None:
        try:
            pixels = int(self.cursor_gap.get())
        except (tk.TclError, ValueError):
            return
        centimeters = pixels / 38
        self.cursor_gap_label.set(f"{pixels}px  /  about {centimeters:.1f}cm")

    def _cursor_gap_pixels(self) -> int:
        try:
            return max(8, min(220, int(self.cursor_gap.get())))
        except (tk.TclError, ValueError):
            return DEFAULT_CURSOR_GAP

    def _selected_asset(self) -> PetAsset:
        selected = self.pet_choice.get()
        return next(asset for asset in self.assets if asset.name == selected)

    def _reload_sheet(self) -> None:
        self.sheet = SpriteSheet(self.root, self._selected_asset().path, self.scale.get())
        self._apply_pet_image()

    def _apply_pet_image(self) -> None:
        image = self.sheet.get(self.action, self.frame_index)
        self.pet_label.configure(image=image)
        self.pet_label.image = image
        self.pet.geometry(f"{self.sheet.size}x{self.sheet.size}+{int(self.pet_x)}+{int(self.pet_y)}")

    def _tick(self) -> None:
        cursor_x, cursor_y = self.root.winfo_pointerxy()
        self._update_cursor_stillness(cursor_x, cursor_y)
        self._keep_windows_topmost()

        if not self.dragging:
            if self.interaction == "feeding":
                self._run_feeding()
            elif self.interaction == "playing":
                self._run_playing(cursor_x, cursor_y)
            elif self.effect_ticks > 0:
                self._run_effect()
            elif self.force_action_ticks > 0:
                self.force_action_ticks -= 1
                self.action = self.force_action or "idle"
            elif self.mode.get() == "rest":
                self._set_rest_action()
            elif self.play_ticks > 0:
                self.play_ticks -= 1
                self._move_toward_cursor(cursor_x, cursor_y, playful=True)
                if self.play_ticks == 0:
                    self.status.set("Ready")
            elif self.mode.get() == "follow":
                self._follow_or_rest(cursor_x, cursor_y)
            else:
                self._run_free_mode(cursor_x, cursor_y)

        self._tick_partner_progress()

        self.frame_index += 1
        self._apply_pet_image()
        self.root.after(TICK_MS, self._tick)

    def _tick_partner_progress(self) -> None:
        leveled_up = self.progress.tick()
        self.partner_save_ticks += 1
        if leveled_up:
            self.status.set(f"Partner level {self.progress.level}")
            self.force_action = "alert"
            self.force_action_ticks = 22
        if leveled_up or self.partner_save_ticks >= max(1, round(60 * 1000 / TICK_MS)):
            self.partner_save_ticks = 0
            self.progress.save()
            self.partner_level.set(self.progress.label())

    def _run_feeding(self) -> None:
        if self.food_target is None:
            self._finish_interaction("Ready")
            return
        target_x, target_y = self.food_target
        if self._move_toward_center(target_x, target_y, arrival=18):
            self.food_ticks += 1
            self.action = "alert" if self.food_ticks < 12 else "idle"
            self.status.set("Eating")
            if self.food_ticks > 28:
                self.food.withdraw()
                self._finish_interaction("Fed")

    def _run_playing(self, cursor_x: int, cursor_y: int) -> None:
        self.play_ticks -= 1
        toy_x, toy_y = self._toy_position(cursor_x, cursor_y)
        self.toy.geometry(f"{TOY_SIZE}x{TOY_SIZE}+{toy_x}+{toy_y}")
        self.toy.deiconify()
        target_x = toy_x + TOY_SIZE / 2
        target_y = toy_y + TOY_SIZE / 2
        arrived = self._move_toward_center(target_x, target_y, arrival=max(18, self.sheet.size * 0.45), speed_boost=1.45)
        if arrived:
            self.action = "alert"
        self.status.set("Playing")
        if self.play_ticks <= 0:
            self.toy.withdraw()
            self._finish_interaction("Ready")

    def _run_effect(self) -> None:
        self.effect_ticks -= 1
        self.force_action_ticks = 0
        self.action = "alert" if self.effect_ticks > 12 else "idle"
        self._place_effect()
        if self.effect_ticks <= 0:
            self.effect.withdraw()
            self.status.set("Ready")

    def _move_toward_center(self, target_x: float, target_y: float, arrival: float, speed_boost: float = 1.0) -> bool:
        center_offset = self.sheet.size / 2
        pet_center_x = self.pet_x + center_offset
        pet_center_y = self.pet_y + center_offset
        dx = target_x - pet_center_x
        dy = target_y - pet_center_y
        distance = math.hypot(dx, dy)
        if distance <= arrival:
            return True
        self.idle_ticks = 0
        step = min(self.speed.get() * speed_boost, distance)
        self.pet_x += dx / distance * step
        self.pet_y += dy / distance * step
        self.action = self._direction(dx, dy)
        return False

    def _run_free_mode(self, cursor_x: int, cursor_y: int) -> None:
        self.free_ticks -= 1
        if self.free_ticks <= 0:
            self._choose_free_activity()

        if self.free_activity == "roam":
            self._run_free_roam()
            self.status.set("Free: wandering")
        elif self.free_activity == "sleep":
            self._set_rest_action()
            self.status.set("Free: sleeping")
        elif self.free_activity == "play":
            self._run_free_play(cursor_x, cursor_y)
            self.status.set("Free: playing")
        elif self.free_activity == "snack":
            self._run_free_snack()
            self.status.set("Free: snacking")
        else:
            if self.effect_ticks <= 0:
                self.effect_ticks = min(38, max(1, self.free_ticks))
                self.effect.deiconify()
            self._run_effect()
            self.status.set("Free: purring")

    def _choose_free_activity(self) -> None:
        self.toy.withdraw()
        self.food.withdraw()
        self.effect.withdraw()
        self.food_target = None
        self.free_target = None
        self.effect_ticks = 0
        self.food_ticks = 0
        self.free_ticks = random.randint(FREE_MODE_MIN_TICKS, FREE_MODE_MAX_TICKS)
        self.free_activity = random.choice(("roam", "sleep", "play", "snack", "purr"))
        if self.free_activity == "roam":
            self.free_target = self._random_screen_point(margin=max(80, self.sheet.size))
        elif self.free_activity == "play":
            self.free_target = self._random_near_pet(150)
        elif self.free_activity == "snack":
            self._place_free_food()

    def _run_free_roam(self) -> None:
        if self.free_target is None:
            self.free_target = self._random_screen_point(margin=max(80, self.sheet.size))
        if self._move_toward_center(*self.free_target, arrival=18, speed_boost=0.82):
            self._set_idle_action()

    def _run_free_play(self, cursor_x: int, cursor_y: int) -> None:
        if self.free_target is None or self.free_ticks % 12 == 0:
            self.free_target = self._random_near_pet(160)
        target_x, target_y = self.free_target
        toy_x = int(min(max(0, target_x - TOY_SIZE / 2), self.root.winfo_screenwidth() - TOY_SIZE))
        toy_y = int(min(max(0, target_y - TOY_SIZE / 2), self.root.winfo_screenheight() - TOY_SIZE))
        self.toy.geometry(f"{TOY_SIZE}x{TOY_SIZE}+{toy_x}+{toy_y}")
        self.toy.deiconify()
        if self._move_toward_center(target_x, target_y, arrival=20, speed_boost=1.25):
            self.action = "alert"
            if self.free_ticks % 8 == 0:
                self.free_target = self._random_near_pet(170)
        if math.hypot(cursor_x - target_x, cursor_y - target_y) < self._cursor_gap_pixels() * 0.7:
            self.free_target = self._random_near_pet(170)

    def _run_free_snack(self) -> None:
        if self.food_target is None:
            self._place_free_food()
        if self.food_target is None:
            self._set_idle_action()
            return
        if self._move_toward_center(*self.food_target, arrival=18, speed_boost=0.95):
            self.food_ticks += 1
            self.action = "alert" if self.food_ticks < 12 else "idle"

    def _place_free_food(self) -> None:
        center_x, center_y = self._random_near_pet(95)
        food_x = int(min(max(0, center_x - FOOD_SIZE / 2), self.root.winfo_screenwidth() - FOOD_SIZE))
        food_y = int(min(max(0, center_y - FOOD_SIZE / 2), self.root.winfo_screenheight() - FOOD_SIZE))
        self.food.geometry(f"{FOOD_SIZE}x{FOOD_SIZE}+{food_x}+{food_y}")
        self.food.deiconify()
        self.food_target = (food_x + FOOD_SIZE / 2, food_y + FOOD_SIZE / 2)

    def _random_screen_point(self, margin: int) -> tuple[float, float]:
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()
        x = random.randint(margin, max(margin, width - margin))
        y = random.randint(margin, max(margin, height - margin))
        return float(x), float(y)

    def _random_near_pet(self, radius: int) -> tuple[float, float]:
        angle = random.uniform(0, math.tau)
        distance = random.randint(max(42, radius // 3), radius)
        center_x = self.pet_x + self.sheet.size / 2
        center_y = self.pet_y + self.sheet.size / 2
        x = min(max(20, center_x + math.cos(angle) * distance), self.root.winfo_screenwidth() - 20)
        y = min(max(20, center_y + math.sin(angle) * distance), self.root.winfo_screenheight() - 20)
        return x, y

    def _keep_windows_topmost(self) -> None:
        self.topmost_ticks -= 1
        if self.topmost_ticks > 0:
            return
        self.topmost_ticks = TOPMOST_REFRESH_TICKS
        if not self.keep_above_games.get():
            return
        for window in (self.pet, self.food, self.toy, self.effect):
            try:
                window.attributes("-topmost", False)
                window.attributes("-topmost", True)
                if window.state() != "withdrawn":
                    window.lift()
            except tk.TclError:
                pass

    def _update_cursor_stillness(self, cursor_x: int, cursor_y: int) -> None:
        if self.last_cursor is None:
            self.last_cursor = (cursor_x, cursor_y)
            return
        last_x, last_y = self.last_cursor
        if math.hypot(cursor_x - last_x, cursor_y - last_y) <= MOUSE_STILL_PIXELS:
            self.mouse_still_ticks += 1
        else:
            self.mouse_still_ticks = 0
            self.rest_line = None
            if self.status.get() == "Resting on a line":
                self.status.set("Following")
        self.last_cursor = (cursor_x, cursor_y)

    def _follow_or_rest(self, cursor_x: int, cursor_y: int) -> None:
        if self._try_rest_on_line(cursor_x, cursor_y):
            return
        arrived = self._move_toward_cursor(cursor_x, cursor_y)
        if self.mouse_still_ticks > MOUSE_REST_TICKS and arrived:
            self._set_rest_action()

    def _move_toward_cursor(self, cursor_x: int, cursor_y: int, playful: bool = False) -> bool:
        center_offset = self.sheet.size / 2
        pet_center_x = self.pet_x + center_offset
        pet_center_y = self.pet_y + center_offset
        away_x = pet_center_x - cursor_x
        away_y = pet_center_y - cursor_y
        away_distance = math.hypot(away_x, away_y)
        if away_distance < 1:
            away_x, away_y, away_distance = 1.0, 0.0, 1.0

        gap = max(8, self._cursor_gap_pixels())
        if playful:
            gap = max(8, gap * 0.72)

        target_x = cursor_x + away_x / away_distance * gap
        target_y = cursor_y + away_y / away_distance * gap
        dx = target_x - pet_center_x
        dy = target_y - pet_center_y
        distance = math.hypot(dx, dy)

        if distance < 12:
            self._set_idle_action()
            return True

        self.idle_ticks = 0
        step = min(self.speed.get(), distance)
        self.pet_x += dx / distance * step
        self.pet_y += dy / distance * step
        self.action = self._direction(dx, dy)
        return False

    def _move_toward_rest_line(self, line: RestLine, cursor_x: int) -> None:
        center_offset = self.sheet.size / 2
        target_center_x = min(max(cursor_x, line.x1 + center_offset), line.x2 - center_offset)
        target_y = line.y - self.sheet.size + 4
        target_x = target_center_x - center_offset
        dx = target_x - self.pet_x
        dy = target_y - self.pet_y
        distance = math.hypot(dx, dy)
        if distance < 7:
            self.pet_x = target_x
            self.pet_y = target_y
            self._set_rest_action()
            return
        self.idle_ticks = 0
        step = min(self.speed.get(), distance)
        self.pet_x += dx / distance * step
        self.pet_y += dy / distance * step
        self.action = self._direction(dx, dy)

    def _set_idle_action(self) -> None:
        self.idle_ticks += 1
        self.action = "sleeping" if self.idle_ticks > 45 else "idle"

    def _set_rest_action(self) -> None:
        self.idle_ticks = max(self.idle_ticks + 1, 46)
        self.action = "sleeping"

    def _try_rest_on_line(self, cursor_x: int, cursor_y: int) -> bool:
        if not self.line_resting.get() or ImageGrab is None:
            return False
        if self.mouse_still_ticks < MOUSE_REST_TICKS // 2:
            return False

        self.line_scan_ticks -= 1
        if self.rest_line is None or self.line_scan_ticks <= 0:
            self.line_scan_ticks = LINE_SCAN_INTERVAL
            self.rest_line = self._find_rest_line(cursor_x, cursor_y)

        if self.rest_line is None:
            return False
        self.status.set("Resting on a line")
        self._move_toward_rest_line(self.rest_line, cursor_x)
        return True

    def _find_rest_line(self, cursor_x: int, cursor_y: int) -> RestLine | None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        left = max(0, cursor_x - LINE_SCAN_RADIUS_X)
        top = max(0, cursor_y - LINE_SCAN_RADIUS_Y)
        right = min(screen_width, cursor_x + LINE_SCAN_RADIUS_X)
        bottom = min(screen_height, cursor_y + LINE_SCAN_RADIUS_Y)
        if right - left < self.sheet.size * 2 or bottom - top < 16:
            return None

        try:
            image = ImageGrab.grab(bbox=(left, top, right, bottom)).convert("RGB")
        except Exception:
            return None

        pixels = image.load()
        width, height = image.size
        min_width = max(86, self.sheet.size * 2)
        best: tuple[float, RestLine] | None = None

        for y in range(4, height - 4, 2):
            run_start: int | None = None
            last_x = 0
            for x in range(2, width - 2, 2):
                if self._looks_like_horizontal_line_pixel(pixels, x, y):
                    if run_start is None:
                        run_start = x
                    last_x = x
                    continue
                if run_start is not None:
                    best = self._score_line_candidate(best, left, top, run_start, last_x, y, min_width, cursor_x, cursor_y)
                    run_start = None
            if run_start is not None:
                best = self._score_line_candidate(best, left, top, run_start, last_x, y, min_width, cursor_x, cursor_y)

        return best[1] if best else None

    def _looks_like_horizontal_line_pixel(self, pixels: object, x: int, y: int) -> bool:
        color = pixels[x, y]
        above = pixels[x, y - 3]
        below = pixels[x, y + 3]
        left = pixels[x - 2, y]
        right = pixels[x + 2, y]
        vertical_edge = max(self._color_distance(color, above), self._color_distance(color, below))
        horizontal_smooth = max(self._color_distance(color, left), self._color_distance(color, right))
        return vertical_edge > 24 and horizontal_smooth < 46 and self._brightness(color) > 18

    def _score_line_candidate(
        self,
        best: tuple[float, RestLine] | None,
        left: int,
        top: int,
        run_start: int,
        last_x: int,
        y: int,
        min_width: int,
        cursor_x: int,
        cursor_y: int,
    ) -> tuple[float, RestLine] | None:
        width = last_x - run_start
        if width < min_width:
            return best
        line = RestLine(left + run_start, left + last_x, top + y)
        if line.x2 - line.x1 < self.sheet.size:
            return best
        closest_x = min(max(cursor_x, line.x1), line.x2)
        score = abs(line.y - cursor_y) * 0.75 + abs(closest_x - cursor_x) * 0.25 - width * 0.04
        if best is None or score < best[0]:
            return (score, line)
        return best

    def _brightness(self, color: tuple[int, int, int]) -> float:
        red, green, blue = color
        return red * 0.299 + green * 0.587 + blue * 0.114

    def _color_distance(self, first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))

    def _direction(self, dx: float, dy: float) -> str:
        angle = math.degrees(math.atan2(dy, dx))
        if -22.5 <= angle < 22.5:
            return "E"
        if 22.5 <= angle < 67.5:
            return "SE"
        if 67.5 <= angle < 112.5:
            return "S"
        if 112.5 <= angle < 157.5:
            return "SW"
        if angle >= 157.5 or angle < -157.5:
            return "W"
        if -157.5 <= angle < -112.5:
            return "NW"
        if -112.5 <= angle < -67.5:
            return "N"
        return "NE"

    def _start_drag(self, event: tk.Event) -> None:
        self.dragging = True
        self.drag_offset = (event.x_root - int(self.pet_x), event.y_root - int(self.pet_y))
        self.action = "alert"
        self.frame_index = 0
        self.status.set("Dragging")

    def _drag(self, event: tk.Event) -> None:
        offset_x, offset_y = self.drag_offset
        self.pet_x = float(event.x_root - offset_x)
        self.pet_y = float(event.y_root - offset_y)
        self._apply_pet_image()

    def _end_drag(self, _event: tk.Event) -> None:
        self.dragging = False
        self.idle_ticks = 0
        self.rest_line = None
        self.status.set("Ready")

    def _show_controls(self, _event: tk.Event | None = None) -> None:
        self.root.deiconify()
        self.root.lift()

    def _show_pet_menu(self, event: tk.Event) -> None:
        try:
            self.pet_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.pet_menu.grab_release()

    def _feed_pet(self) -> None:
        self._finish_interaction("Ready")
        food_x = int(min(self.root.winfo_screenwidth() - FOOD_SIZE, self.pet_x + self.sheet.size + 22))
        food_y = int(min(self.root.winfo_screenheight() - FOOD_SIZE, self.pet_y + self.sheet.size - FOOD_SIZE + 6))
        food_x = max(0, food_x)
        food_y = max(0, food_y)
        self.food.geometry(f"{FOOD_SIZE}x{FOOD_SIZE}+{food_x}+{food_y}")
        self.food.deiconify()
        self.food_target = (food_x + FOOD_SIZE / 2, food_y + FOOD_SIZE / 2)
        self.food_ticks = 0
        self.previous_mode = self.mode.get()
        self.interaction = "feeding"
        self.mode.set("free")
        self.status.set("Food is out")

    def _play_with_pet(self) -> None:
        self._finish_interaction("Ready")
        self.interaction = "playing"
        self.play_ticks = 230
        self.previous_mode = self.mode.get()
        self.force_action_ticks = 0
        self.status.set("Playing")

    def _pet_pet(self) -> None:
        self._finish_interaction("Ready")
        self.effect_ticks = 38
        self.force_action_ticks = 0
        self.status.set("Purring")
        self._place_effect()
        self.effect.deiconify()

    def _rest_here(self) -> None:
        self._finish_interaction("Ready")
        self.mode.set("rest")
        self.force_action_ticks = 0
        self._set_rest_action()
        self.status.set("Resting")

    def _normal_mode(self) -> None:
        self._finish_interaction("Ready")
        self.mode.set("follow")
        self.free_ticks = 0
        self.free_target = None
        self.force_action_ticks = 0
        self.status.set("Normal mode")

    def _mode_changed(self) -> None:
        self.idle_ticks = 0
        self.rest_line = None
        self.force_action_ticks = 0
        self.free_ticks = 0
        self.free_target = None
        self.food.withdraw()
        self.toy.withdraw()
        self.effect.withdraw()
        labels = {"follow": "Following", "free": "Free mode", "rest": "Resting"}
        self.status.set(labels.get(self.mode.get(), "Ready"))

    def _line_rest_changed(self) -> None:
        self.rest_line = None
        if ImageGrab is None and self.line_resting.get():
            self.status.set("Install Pillow for line resting")
        else:
            self.status.set("Ready")

    def _finish_interaction(self, status: str) -> None:
        self.interaction = None
        self.food_target = None
        self.food_ticks = 0
        self.play_ticks = 0
        self.food.withdraw()
        self.toy.withdraw()
        self.effect.withdraw()
        if self.previous_mode is not None:
            self.mode.set(self.previous_mode)
            self.previous_mode = None
        self.status.set(status)

    def _toy_position(self, cursor_x: int, cursor_y: int) -> tuple[int, int]:
        gap = max(38, int(self._cursor_gap_pixels() * 0.65))
        x = min(max(0, cursor_x + gap), self.root.winfo_screenwidth() - TOY_SIZE)
        y = min(max(0, cursor_y + gap // 3), self.root.winfo_screenheight() - TOY_SIZE)
        return x, y

    def _place_effect(self) -> None:
        x = int(self.pet_x + self.sheet.size * 0.55)
        y = int(max(0, self.pet_y - 24))
        self.effect.geometry(f"+{x}+{y}")


def main() -> int:
    try:
        OnekoApp().run()
    except Exception as error:
        print(f"Oneko could not start: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
