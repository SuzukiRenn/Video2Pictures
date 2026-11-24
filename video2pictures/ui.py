import ctypes
import sys
import tkinter as tk
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Event, Thread
from time import monotonic
from tkinter import filedialog, font, ttk

from .media import Cancelled, SourceInfo, export_frames, inspect_source
from .selection import select_frames


BACKGROUND = "#f1f5fa"
SURFACE = "#ffffff"
TEXT = "#15243b"
MUTED = "#465a74"
LINE = "#ced9e6"
ACCENT = "#2258bc"
ERROR = "#a52736"

SOURCE_TYPES = [
    ("视频和 DICOM", "*.mp4 *.mov *.mkv *.avi *.m4v *.webm *.wmv *.mpeg *.mpg *.ts *.mts *.m2ts *.dcm *.dicom *.ima"),
    ("所有文件", "*"),
]


def create_root() -> tk.Tk:
    if sys.platform == "win32":
        ctypes.windll.user32.SetProcessDPIAware()
    return tk.Tk()


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.source: SourceInfo | None = None
        self.custom_destination = False
        self.job: str | None = None
        self.cancel = Event()
        self.closing = False
        self.events = SimpleQueue()
        self.path = tk.StringVar(root)
        self.destination = tk.StringVar(root)
        self.mode = tk.StringVar(root, "all")
        self.value = tk.StringVar(root)
        self.format = tk.StringVar(root, "PNG")
        self.frame_info = tk.StringVar(root)
        self.selection_info = tk.StringVar(root)
        self.status = tk.StringVar(root, "请选择源文件")
        self.detail = tk.StringVar(root)

        root.title("Video2Pictures")
        root.configure(background=BACKGROUND)
        self.scale = max(0.8, font.nametofont("TkDefaultFont").metrics("linespace") / 16)
        self._apply_style()
        self._layout()
        self.value.trace_add("write", self._count_selection)
        self._update_controls()
        root.update_idletasks()
        height = root.winfo_reqheight() + self._px(20)
        root.minsize(max(root.winfo_reqwidth(), self._px(620)), height)
        root.geometry(f"{max(root.winfo_reqwidth(), self._px(720))}x{height}")
        root.protocol("WM_DELETE_WINDOW", self._close)
        self.poll_handle = root.after(50, self._poll)
        self.choose_input.focus_set()

    def _px(self, amount: int) -> int:
        return round(amount * self.scale)

    def _apply_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        default = font.nametofont("TkDefaultFont")
        available = set(font.families(self.root))
        for family in ("Microsoft YaHei UI", "PingFang SC"):
            if family in available:
                default.configure(family=family)
                break
        default.configure(size=11)
        family = default.actual("family")
        body = (family, 11)
        strong = (family, 11, "bold")

        style.configure("TFrame", background=BACKGROUND)
        style.configure("Surface.TFrame", background=SURFACE, bordercolor=LINE, borderwidth=1, relief="solid")
        style.configure("Plain.TFrame", background=SURFACE)
        style.configure("TLabel", background=SURFACE, foreground=TEXT, font=body)
        style.configure("Title.TLabel", background=BACKGROUND, foreground=TEXT, font=(family, 25, "bold"))
        style.configure("Section.TLabel", font=(family, 12, "bold"))
        style.configure("Count.TLabel", foreground=MUTED, font=(family, 10))
        style.configure("Status.TLabel", background=BACKGROUND, font=strong)
        style.configure("Detail.TLabel", background=BACKGROUND, foreground=MUTED, font=(family, 10))
        style.configure("Error.TLabel", background=BACKGROUND, foreground=ERROR, font=(family, 10))

        style.configure("TEntry", font=body, foreground=TEXT, fieldbackground=SURFACE, bordercolor=LINE,
                        lightcolor=SURFACE, darkcolor=SURFACE, padding=(self._px(9), self._px(6)))
        style.map("TEntry", fieldbackground=[("readonly", "#f6f8fc")], bordercolor=[("focus", ACCENT)])
        style.configure("TRadiobutton", background=SURFACE, foreground=TEXT, font=body, indicatorbackground=SURFACE,
                        indicatorcolor=ACCENT, padding=(0, self._px(4)), focuscolor=ACCENT)
        style.map("TRadiobutton", background=[("active", SURFACE)], foreground=[("disabled", "#68788c")],
                  indicatorbackground=[("selected", ACCENT), ("!selected", SURFACE)],
                  indicatorforeground=[("selected", SURFACE), ("!selected", MUTED)])

        style.configure("TButton", background=SURFACE, foreground=TEXT, bordercolor=LINE, focuscolor=ACCENT,
                        lightcolor=SURFACE, darkcolor=SURFACE, font=body, padding=(self._px(13), self._px(6)))
        style.map("TButton", background=[("pressed", "#e5edf9"), ("active", "#f0f5fc")],
                  bordercolor=[("focus", ACCENT)], foreground=[("disabled", "#68788c")])
        style.configure("Action.TButton", background=ACCENT, foreground=SURFACE, bordercolor=ACCENT,
                        lightcolor=ACCENT, darkcolor=ACCENT, font=strong, focuscolor=SURFACE,
                        padding=(self._px(18), self._px(9)))
        style.map("Action.TButton", background=[("disabled", "#e0e7f1"), ("pressed", "#183f89"), ("active", "#1c4eaa")],
                  foreground=[("disabled", "#536680")], bordercolor=[("disabled", "#e0e7f1"), ("focus", TEXT)],
                  lightcolor=[("disabled", "#e0e7f1")], darkcolor=[("disabled", "#e0e7f1")])
        style.configure("Horizontal.TProgressbar", troughcolor="#dce5f0", background=ACCENT, borderwidth=0,
                        bordercolor="#dce5f0", lightcolor=ACCENT, darkcolor=ACCENT, thickness=self._px(5))

    def _layout(self) -> None:
        pad = self._px
        body = ttk.Frame(self.root, padding=(pad(26), pad(21), pad(26), pad(20)))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)
        ttk.Label(body, text="Video2Pictures", style="Title.TLabel").grid(row=0, sticky="w", pady=(0, pad(15)))

        files = ttk.Frame(body, style="Surface.TFrame", padding=(pad(17), pad(12)))
        files.grid(row=1, sticky="ew", pady=(0, pad(13)))
        files.columnconfigure(1, weight=1)
        ttk.Label(files, text="文件", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, pad(8)))
        ttk.Label(files, textvariable=self.frame_info, style="Count.TLabel").grid(row=0, column=1, columnspan=2, sticky="e")
        self.choose_input = ttk.Button(files, text="选择文件…", command=self._choose_input)
        self.choose_output = ttk.Button(files, text="选择目录…", command=self._choose_output)
        for row, label, variable, button in (
            (1, "源文件", self.path, self.choose_input),
            (2, "输出目录", self.destination, self.choose_output),
        ):
            ttk.Label(files, text=label).grid(row=row, column=0, sticky="w", padx=(0, pad(13)), pady=pad(4))
            ttk.Entry(files, textvariable=variable, state="readonly", width=20).grid(
                row=row, column=1, sticky="ew", padx=(0, pad(10)), pady=pad(4))
            button.grid(row=row, column=2, sticky="ew", pady=pad(4))

        options = ttk.Frame(body, style="Surface.TFrame", padding=(pad(17), pad(12)))
        options.grid(row=2, sticky="ew")
        options.columnconfigure(0, weight=1)
        ttk.Label(options, text="帧选择", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(options, textvariable=self.selection_info, style="Count.TLabel").grid(row=0, column=1, sticky="e")

        modes = ttk.Frame(options, style="Plain.TFrame")
        modes.grid(row=1, column=0, columnspan=2, sticky="w", pady=(pad(6), pad(7)))
        self.radios = []
        for column, (label, value) in enumerate((("全部帧", "all"), ("均匀抽取", "uniform"), ("指定帧号 / 范围", "ranges"))):
            radio = ttk.Radiobutton(modes, text=label, value=value, variable=self.mode, command=self._change_mode)
            radio.grid(row=0, column=column, sticky="w", padx=(0, pad(17)))
            self.radios.append(radio)

        value_row = ttk.Frame(options, style="Plain.TFrame", height=pad(38))
        value_row.grid(row=2, column=0, sticky="ew", padx=(0, pad(16)))
        value_row.columnconfigure(1, weight=1)
        value_row.rowconfigure(0, weight=1)
        value_row.grid_propagate(False)
        self.value_label = ttk.Label(value_row, text="张数")
        self.value_label.grid(row=0, column=0, sticky="w", padx=(0, pad(9)))
        self.value_entry = ttk.Entry(value_row, textvariable=self.value, width=13)
        self.value_entry.grid(row=0, column=1, sticky="ew")

        formats = ttk.Frame(options, style="Plain.TFrame")
        formats.grid(row=2, column=1, sticky="e")
        ttk.Label(formats, text="格式").grid(row=0, column=0, padx=(0, pad(11)))
        for column, value in enumerate(("PNG", "JPEG"), 1):
            radio = ttk.Radiobutton(formats, text=value, value=value, variable=self.format)
            radio.grid(row=0, column=column, padx=(0, pad(10) if column == 1 else 0))
            self.radios.append(radio)

        footer = ttk.Frame(body)
        footer.grid(row=4, sticky="sew", pady=(pad(18), 0))
        footer.columnconfigure(0, weight=1)
        status_block = ttk.Frame(footer, height=pad(47))
        status_block.grid(row=0, column=0, sticky="ew", padx=(0, pad(14)))
        ttk.Label(status_block, textvariable=self.status, style="Status.TLabel").pack(anchor="w")
        self.status_detail = ttk.Label(status_block, textvariable=self.detail, style="Detail.TLabel", wraplength=pad(400))
        self.status_detail.pack(anchor="w")
        status_block.bind("<Configure>", self._wrap_status)
        self.action = ttk.Button(footer, text="导出图片", style="Action.TButton", command=self._action, width=12)
        self.action.grid(row=0, column=1, sticky="se")
        self.progress = ttk.Progressbar(footer, style="Horizontal.TProgressbar", takefocus=False)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(pad(10), 0))

    def _wrap_status(self, event) -> None:
        self.status_detail.configure(wraplength=max(self._px(80), event.width))

    def _show_status(self, title: str, detail: str = "", error: bool = False) -> None:
        self.status.set(title)
        self.detail.set(detail)
        self.status_detail.configure(style="Error.TLabel" if error else "Detail.TLabel")

    def _choose_input(self) -> None:
        options = {"initialdir": str(Path(self.path.get()).parent)} if self.path.get() else {}
        value = filedialog.askopenfilename(parent=self.root, title="选择视频或 DICOM", filetypes=SOURCE_TYPES, **options)
        if value:
            self.load(Path(value))

    def load(self, path: Path) -> None:
        self.source = None
        self.path.set(str(path))
        self.frame_info.set("")
        if not self.custom_destination:
            self.destination.set(str(path.parent / f"{path.stem}_frames"))
        self._count_selection()
        self._show_status("正在读取帧数…")
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(16)
        self._start("inspect", lambda report: inspect_source(path, cancel=self.cancel, progress=report))

    def _choose_output(self) -> None:
        current = Path(self.destination.get())
        if not current.is_dir():
            current = current.parent
        value = filedialog.askdirectory(parent=self.root, title="选择输出目录", initialdir=current, mustexist=True)
        if value:
            self.custom_destination = True
            self.destination.set(value)

    def _change_mode(self) -> None:
        self.value.set("")
        self._update_controls()
        if self.mode.get() != "all":
            self.value_entry.focus_set()

    def _count_selection(self, *_args) -> None:
        self.selection_info.set("")
        if self.source is not None and self.mode.get() != "all":
            try:
                plan = select_frames(self.source.total, self.mode.get(), self.value.get())
            except ValueError:
                return
            self.selection_info.set(f"将导出 {plan.count:,} 张")

    def _update_controls(self) -> None:
        busy = self.job is not None
        state = ["disabled" if busy else "!disabled"]
        for widget in [self.choose_input, self.choose_output, *self.radios, self.value_entry]:
            widget.state(state)
        mode = self.mode.get()
        if mode == "all":
            self.value_label.grid_remove()
            self.value_entry.grid_remove()
        else:
            self.value_label.configure(text="张数" if mode == "uniform" else "如 1,3-5")
            self.value_label.grid()
            self.value_entry.grid()
        self.action.configure(text="取消" if busy else "导出图片", style="TButton" if busy else "Action.TButton")
        self.action.state(["!disabled" if busy or self.source is not None else "disabled"])

    def _action(self) -> None:
        if self.job is not None:
            self._request_cancel()
            return
        if self.source is None:
            return
        source = self.source
        try:
            plan = select_frames(source.total, self.mode.get(), self.value.get())
        except ValueError as exc:
            self._show_status("请检查帧选择", str(exc), error=True)
            self.value_entry.focus_set()
            return
        directory, fmt = Path(self.destination.get()), self.format.get()
        self._show_status("正在导出…", f"0 / {plan.count:,} 张")
        self.progress.configure(mode="determinate", maximum=plan.count, value=0)
        self._start("export", lambda report: export_frames(
            source, directory, plan, fmt, cancel=self.cancel, progress=report))

    def _start(self, job: str, operation) -> None:
        self.job = job
        self.cancel.clear()
        self._update_controls()

        def work():
            last_report = 0.0

            def report(count):
                nonlocal last_report
                now = monotonic()
                if now - last_report >= 0.1:
                    last_report = now
                    self.events.put(("progress", count))

            try:
                self.events.put(("done", operation(report)))
            except Cancelled as exc:
                self.events.put(("cancelled", exc.saved))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        Thread(target=work, name=f"video2pictures-{job}").start()

    def _poll(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except Empty:
                break
            if event == "progress":
                if not self.cancel.is_set():
                    if self.job == "inspect":
                        self.detail.set(f"已读取 {payload:,} 帧")
                    else:
                        self.progress.configure(value=payload)
                        maximum = int(float(self.progress.cget("maximum")))
                        self.detail.set(f"{payload:,} / {maximum:,} 张")
                continue
            self._finish(event, payload)
            if self.closing:
                self.root.destroy()
                return
        self.poll_handle = self.root.after(50, self._poll)

    def _finish(self, event, payload) -> None:
        job, self.job = self.job, None
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0, maximum=100)
        if event == "done" and job == "inspect":
            self.source = payload
            self.frame_info.set(f"{payload.kind}  ·  {payload.total:,} 帧")
            self._show_status("可以导出")
        elif event == "done":
            self.progress.configure(value=100)
            self._show_status(f"已导出 {payload:,} 张图片")
        elif event == "cancelled":
            state = "已取消读取" if job == "inspect" else "已取消导出"
            self._show_status(state, f"已保留 {payload:,} 张图片" if payload else "")
        else:
            self._show_status("读取失败" if job == "inspect" else "导出失败", payload, error=True)
        self._count_selection()
        self._update_controls()

    def _request_cancel(self) -> None:
        self.cancel.set()
        self.action.state(["disabled"])
        self._show_status("正在取消…")

    def _close(self) -> None:
        if self.job is None:
            self.root.after_cancel(self.poll_handle)
            self.root.destroy()
        else:
            self.closing = True
            self._request_cancel()
