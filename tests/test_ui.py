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
        self.app.radios[2].invoke()
        self.app.value.set("7")
        self.app.action.invoke()
        self.assertEqual(self.app.status.get(), "请检查帧选择")
        self.app.value.set("1,4-5")
        self.app.radios[4].invoke()
        self.app.action.invoke()
        self.wait_for_job()
        self.assertEqual(self.app.status.get(), "已导出 3 张图片")
        self.assertEqual(sorted(path.name for path in self.directory.glob("frame_*.jpg")),
                         ["frame_000001.jpg", "frame_000004.jpg", "frame_000005.jpg"])
