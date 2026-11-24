from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Event

import av
from PIL import Image
from av.video.reformatter import ColorRange
from pydicom.misc import is_dicom

from .dicom import DICOM_EXTENSIONS, dicom_frames, read_metadata
from .selection import FramePlan


class MediaError(Exception):
    pass


class Cancelled(Exception):
    def __init__(self, saved: int = 0):
        self.saved = saved


@dataclass(frozen=True)
class SourceInfo:
    path: Path
    kind: str
    total: int
    signature: tuple[int, int, int, int]


def _signature(path: Path) -> tuple[int, int, int, int]:
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _check_source(path: Path, expected: tuple[int, int, int, int]) -> None:
    if _signature(path) != expected:
        raise MediaError("源文件已更改，请重新选择后再导出。")


def _check_cancel(cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _video_frames(path: Path, cancel: Event | None) -> Iterator[av.VideoFrame]:
    # Pass in an open local file and disable network protocols in FFmpeg demuxers.
    with path.open("rb") as stream, av.open(stream, options={"protocol_whitelist": "file"}) as container:
        video = next(
            (track for track in container.streams.video if not track.disposition & av.stream.Disposition.attached_pic),
            None,
        )
        if video is None:
            raise MediaError("文件中没有视频轨道。")
        for frame in container.decode(video):
            _check_cancel(cancel)
            if frame.is_corrupt:
                raise MediaError("视频包含损坏的帧。")
            yield frame


def _video_image(frame: av.VideoFrame) -> Image.Image:
    image = frame.to_image(src_color_range=ColorRange(frame.color_range), dst_color_range=ColorRange.JPEG)
    turns = {
        90: Image.Transpose.ROTATE_90,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_270,
    }
    rotation = turns.get(frame.rotation % 360)
    return image.transpose(rotation) if rotation is not None else image


def _detail(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    return (message[:197] + "…") if len(message) > 198 else message or type(exc).__name__


def inspect_source(
    path: Path,
    *,
    cancel: Event | None = None,
    progress: Callable[[int], None] | None = None,
) -> SourceInfo:
    kind = "源文件"
    try:
        _check_cancel(cancel)
        if not path.is_file():
            raise MediaError("请选择一个存在的本地文件。")
        signature = _signature(path)
        if path.suffix.lower() in DICOM_EXTENSIONS or is_dicom(path):
            kind = "DICOM"
            ds = read_metadata(path)
            total = int(ds.get("NumberOfFrames", 1))
            with closing(dicom_frames(path, ds, (1,))) as frames:
                next(frames)
        else:
            kind = "视频"
            total = 0
            with closing(_video_frames(path, cancel)) as frames:
                for total, _ in enumerate(frames, 1):
                    if progress is not None:
                        progress(total)
            if total == 0:
                raise MediaError("视频没有可解码的帧。")
        _check_cancel(cancel)
        _check_source(path, signature)
        return SourceInfo(path, kind, total, signature)
    except (MediaError, Cancelled):
        raise
    except Exception as exc:
        raise MediaError(f"无法读取{kind}。{_detail(exc)}") from exc


def _selected_video_frames(path: Path, plan: FramePlan, cancel: Event | None):
    wanted = iter(plan)
    target = next(wanted, None)
    with closing(_video_frames(path, cancel)) as frames:
        for number, frame in enumerate(frames, 1):
            if number == target:
                yield number, _video_image(frame)
                target = next(wanted, None)
                if target is None:
                    return
    raise MediaError("视频已结束，未能读到所有选定的帧。")


def _write_image(directory: Path, stem: str, image: Image.Image, fmt: str) -> None:
    data = BytesIO()
    extension = ".png" if fmt == "PNG" else ".jpg"
    options = {} if fmt == "PNG" else {"quality": 95, "subsampling": 0}
    image.save(data, format=fmt, **options)

    attempt = 1
    while True:
        basename = stem if attempt == 1 else f"{stem}_{attempt}"
        path = directory / (basename + extension)
        try:
            output = path.open("xb")
            break
        except FileExistsError:
            attempt += 1

    try:
        with output, data.getbuffer() as contents:
            output.write(contents)
    except OSError:
        path.unlink(missing_ok=True)
        raise


def export_frames(
    source: SourceInfo,
    directory: Path,
    plan: FramePlan,
    fmt: str = "PNG",
    *,
    cancel: Event | None = None,
    progress: Callable[[int], None] | None = None,
) -> int:
    if plan.total != source.total or plan.count < 1:
        raise MediaError("帧选择与当前源文件不一致。")
    if fmt not in {"PNG", "JPEG"}:
        raise MediaError("请选择 PNG 或 JPEG。")

    saved = 0
    try:
        _check_cancel(cancel)
        _check_source(source.path, source.signature)
        directory.mkdir(parents=True, exist_ok=True)
        if source.kind == "DICOM":
            frames = dicom_frames(source.path, read_metadata(source.path), plan)
        else:
            frames = _selected_video_frames(source.path, plan, cancel)
        width = max(6, len(str(source.total)))
        with closing(frames):
            for number, image in frames:
                _check_cancel(cancel)
                _write_image(directory, f"frame_{number:0{width}d}", image, fmt)
                saved += 1
                if progress is not None:
                    progress(saved)
        _check_source(source.path, source.signature)
        return saved
    except Cancelled:
        raise Cancelled(saved) from None
    except Exception as exc:
        detail = _detail(exc)
        if saved:
            raise MediaError(f"已保留成功导出的 {saved} 张图片。{detail}") from exc
        if isinstance(exc, MediaError):
            raise
        raise MediaError(f"导出失败。{detail}") from exc
