import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from unittest.mock import patch

from tests.fixtures import make_video
from video2pictures.ui import Application, create_root


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        try:
            self.root = create_root()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.app = Application(self.root)
        self.addCleanup(self.app._close)

    def wait_for_job(self):
        deadline = monotonic() + 10
        while self.app.job is not None and monotonic() < deadline:
            self.root.update()
            sleep(0.01)
        self.assertIsNone(self.app.job)

    def choose_radio(self, value):
        next(radio for radio in self.app.radios if radio.cget("value") == value).invoke()

    def test_recover_from_bad_source_and_invalid_range_then_export(self):
        invalid = self.directory / "broken.mp4"
        invalid.write_bytes(b"broken")
        valid = make_video(self.directory / "valid.mkv")
        for path in (invalid, valid):
            with patch("video2pictures.ui.filedialog.askopenfilename", return_value=str(path)):
                self.app.choose_input.invoke()
            self.assertTrue(self.app.choose_input.instate(["disabled"]))
            self.wait_for_job()
            self.assertTrue(self.app.choose_input.instate(["!disabled"]))
            if path == invalid:
                self.assertEqual(self.app.status.get(), "读取失败")
                self.assertTrue(self.app.action.instate(["disabled"]))
        self.assertIn("5 帧", self.app.frame_info.get())

        with patch("video2pictures.ui.filedialog.askdirectory", return_value=str(self.directory)):
            self.app.choose_output.invoke()
        self.choose_radio("ranges")
        self.app.value.set("7")
        self.app.action.invoke()
        self.assertEqual(self.app.status.get(), "请检查帧选择")
        self.app.value.set("1,4-5")
        self.choose_radio("JPEG")
        self.app.action.invoke()
        self.wait_for_job()
        self.assertEqual(self.app.status.get(), "已导出 3 张图片")
        self.assertEqual(sorted(path.name for path in self.directory.glob("frame_*.jpg")),
                         ["frame_000001.jpg", "frame_000004.jpg", "frame_000005.jpg"])

    def test_stride_previews_count_and_recovers_from_invalid_input(self):
        self.app.load(make_video(self.directory / "video.mkv"))
        self.wait_for_job()
        self.choose_radio("stride")
        self.assertEqual(self.app.value_label.cget("text"), "N（帧）")

        self.app.value.set("1")
        self.assertEqual(self.app.selection_info.get(), "将导出 5 张")
        self.app.value.set("6")
        self.assertEqual(self.app.selection_info.get(), "将导出 1 张")
        self.app.value.set("0")
        self.assertEqual(self.app.selection_info.get(), "")
        self.app.action.invoke()
        self.assertEqual(self.app.status.get(), "请检查帧选择")
        self.assertIn("N 必须是正整数", self.app.detail.get())

        self.app.value.set("3")
        self.assertEqual(self.app.selection_info.get(), "将导出 2 张")
        self.app.action.invoke()
        self.wait_for_job()
        self.assertEqual(self.app.status.get(), "已导出 2 张图片")
        output = self.directory / "video_frames"
        self.assertEqual(sorted(path.name for path in output.iterdir()), ["frame_000001.png", "frame_000004.png"])
