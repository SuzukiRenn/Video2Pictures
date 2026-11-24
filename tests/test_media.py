import gc
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from tests.fixtures import COLORS, VIDEO_SIZE, make_dicom, make_video
from video2pictures.media import Cancelled, MediaError, export_frames, inspect_source
from video2pictures.selection import select_frames


class MediaTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="视频与医学影像 ")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.output = self.root / "导出"

    def test_video_png_numbers_dimensions_and_exact_colors(self):
        source = inspect_source(make_video(self.root / "合成.mkv"))
        self.assertEqual((source.kind, source.total), ("视频", len(COLORS)))
        plan = select_frames(source.total, "uniform", "3")
        self.assertEqual(export_frames(source, self.output, plan), 3)
        self.assertEqual(sorted(path.name for path in self.output.iterdir()),
                         ["frame_000001.png", "frame_000003.png", "frame_000005.png"])
        for number in (1, 3, 5):
            with Image.open(self.output / f"frame_{number:06d}.png") as image:
                self.assertEqual((image.format, image.mode, image.size), ("PNG", "RGB", VIDEO_SIZE))
                self.assertEqual(image.getpixel((15, 16)), COLORS[number - 1])

    def test_jpeg_and_concurrent_exports_keep_existing_files(self):
        source = inspect_source(make_video(self.root / "video.mkv"))
        plan = select_frames(source.total, "ranges", "2")
        self.output.mkdir()
        existing = self.output / "frame_000002.jpg"
        existing.write_bytes(b"keep")
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(export_frames, source, self.output, plan, "JPEG") for _ in range(2)]
            self.assertEqual([task.result() for task in tasks], [1, 1])
        self.assertEqual(existing.read_bytes(), b"keep")
        for suffix in (2, 3):
            with Image.open(self.output / f"frame_000002_{suffix}.jpg") as image:
                self.assertEqual((image.format, image.size), ("JPEG", VIDEO_SIZE))
                self.assertTrue(all(abs(a - b) <= 3 for a, b in zip(image.getpixel((10, 10)), COLORS[1])))

    def test_multiframe_dicom_window_rescale_polarity_and_selected_index(self):
        frames = np.array([[[-1] * 3] * 2, [[-50, -25, 0], [25, 50, 75]], [[2] * 3] * 2], dtype="<i2")
        path = make_dicom(self.root / "灰阶.dcm", frames, "MONOCHROME1", RescaleSlope=2, RescaleIntercept=10,
                          WindowCenter=[10, 200], WindowWidth=[200, 1], VOILUTFunction="LINEAR_EXACT")
        source = inspect_source(path)
        self.assertEqual((source.kind, source.total), ("DICOM", 3))
        self.assertEqual(export_frames(source, self.output, select_frames(3, "ranges", "2")), 1)
        with Image.open(self.output / "frame_000002.png") as image:
            self.assertEqual((image.mode, image.size), ("L", (3, 2)))
            np.testing.assert_array_equal(image, [[255, 191, 128], [64, 0, 0]])

    def test_dicom_frame_specific_window_falls_back_to_shared_values(self):
        shared_voi = Dataset()
        shared_voi.WindowCenter = 128
        shared_voi.WindowWidth = 256
        shared = Dataset()
        shared.FrameVOILUTSequence = [shared_voi]
        second_voi = Dataset()
        second_voi.WindowCenter = 64
        second_voi.WindowWidth = 1
        second = Dataset()
        second.FrameVOILUTSequence = [second_voi]
        path = make_dicom(self.root / "group.dcm", np.array([[[32, 128]], [[32, 128]]], dtype=np.uint8),
                          SharedFunctionalGroupsSequence=[shared], PerFrameFunctionalGroupsSequence=[Dataset(), second])
        source = inspect_source(path)
        export_frames(source, self.output, select_frames(2, "all"))
        with Image.open(self.output / "frame_000001.png") as first, Image.open(self.output / "frame_000002.png") as second:
            np.testing.assert_array_equal(first, [[32, 128]])
            np.testing.assert_array_equal(second, [[0, 255]])

    def test_dicom_planar_rgb_with_magic_and_no_extension(self):
        frames = np.array([[[[250, 1, 13], [10, 42, 222]]]], dtype=np.uint8)
        source = inspect_source(make_dicom(self.root / "颜色", frames, "RGB", planar=True))
        self.assertEqual(source.total, 1)
        export_frames(source, self.output, select_frames(1, "all"))
        with Image.open(self.output / "frame_000001.png") as image:
            self.assertEqual(image.mode, "RGB")
            np.testing.assert_array_equal(image, frames[0])

    def test_inspection_and_cancellation_close_dicom_decoder_before_file(self):
        path = make_dicom(self.root / "cancel.dcm", np.arange(8, dtype=np.uint8).reshape(2, 2, 2))
        cancel = Event()
        with patch.object(sys, "unraisablehook") as unraisable:
            source = inspect_source(path)
            with self.assertRaises(Cancelled) as failure:
                export_frames(source, self.output, select_frames(2, "all"), cancel=cancel,
                              progress=lambda count: cancel.set())
            gc.collect()
        self.assertEqual(failure.exception.saved, 1)
        self.assertEqual([path.name for path in self.output.iterdir()], ["frame_000001.png"])
        unraisable.assert_not_called()
        path.rename(path.with_name("renamed.dcm"))

    def test_invalid_input_and_existing_file_as_output(self):
        bad_video = self.root / "damaged.mp4"
        bad_video.write_bytes(b"not a video")
        with self.assertRaisesRegex(MediaError, "无法读取视频"):
            inspect_source(bad_video)
        bad_dicom = self.root / "damaged.dcm"
        bad_dicom.write_bytes(b"not a DICOM")
        with self.assertRaisesRegex(MediaError, "无法读取DICOM"):
            inspect_source(bad_dicom)
        source = inspect_source(make_video(self.root / "video.mkv"))
        with self.assertRaisesRegex(MediaError, "导出失败"):
            export_frames(source, bad_video, select_frames(source.total, "all"))
        with self.assertRaisesRegex(MediaError, "帧选择"):
            export_frames(source, self.output, select_frames(source.total + 1, "all"))

    def test_source_changed_after_inspection(self):
        path = make_video(self.root / "video.mkv")
        source = inspect_source(path)
        with path.open("ab") as original:
            original.write(b"mutated")
        with self.assertRaisesRegex(MediaError, "源文件已更改"):
            export_frames(source, self.output, select_frames(source.total, "all"))
        self.assertFalse(self.output.exists())
