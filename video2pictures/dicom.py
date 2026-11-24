from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

import numpy as np
from PIL import Image
from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.pixels import apply_modality_lut, apply_voi, get_decoder, iter_pixels


DICOM_EXTENSIONS = {".dcm", ".dicom", ".ima"}
MONOCHROME = {"MONOCHROME1", "MONOCHROME2"}


def read_metadata(path: Path) -> Dataset:
    ds = dcmread(path, stop_before_pixels=True, force=path.suffix.lower() in DICOM_EXTENSIONS)
    if not all(tag in ds for tag in ("Rows", "Columns", "PhotometricInterpretation")):
        raise ValueError("DICOM 缺少图像像素元数据。")
    if int(ds.get("NumberOfFrames", 1)) < 1 or min(ds.Rows, ds.Columns) < 1:
        raise ValueError("DICOM 帧数或像素尺寸无效。")
    syntax = ds.file_meta.get("TransferSyntaxUID")
    if not syntax:
        raise ValueError("DICOM 缺少传输语法，无法确定像素编码。")
    # Pillow is bundled for common JPEG/JPEG 2000 syntaxes. RLE also has a native decoder.
    try:
        decoder = get_decoder(syntax)
    except (NotImplementedError, ValueError) as exc:
        raise ValueError(f"不支持此 DICOM 传输语法（{syntax.name}）。") from exc
    if not decoder.is_available:
        raise ValueError(f"当前无法解码此 DICOM 传输语法（{syntax.name}）。")
    if ds.PhotometricInterpretation not in MONOCHROME | {"RGB", "YBR_FULL", "YBR_FULL_422"}:
        raise ValueError(f"不支持此 DICOM 色彩类型（{ds.PhotometricInterpretation}）。")
    return ds


def dicom_frames(path, ds, numbers):
    with path.open("rb") as stream:
        with closing(iter_pixels(stream, indices=(number - 1 for number in numbers))) as decoded:
            for number, pixels in zip(numbers, decoded, strict=True):
                yield number, render_frame(pixels, ds, number - 1)


def _gray_attributes(ds: Dataset, frame_index: int) -> Dataset:
    shared = ds.get("SharedFunctionalGroupsSequence", [])
    frames = ds.get("PerFrameFunctionalGroupsSequence", [])
    groups = ([frames[frame_index]] if frame_index < len(frames) else []) + list(shared[:1])
    attributes = ds
    for sequence, tags in (
        ("PixelValueTransformationSequence", ("ModalityLUTSequence", "RescaleSlope", "RescaleIntercept")),
        ("FrameVOILUTSequence", ("VOILUTSequence", "WindowCenter", "WindowWidth", "VOILUTFunction")),
    ):
        for group in groups:
            if not group.get(sequence):
                continue
            if attributes is ds:
                attributes = Dataset(dict(ds.items()), file_meta=ds.file_meta)
            item = group.get(sequence)[0]
            for tag in tags:
                if tag in attributes:
                    del attributes[tag]
                if tag in item:
                    attributes.add(item[tag])
            break
    return attributes


def _first(value) -> float:
    return float(value[0] if isinstance(value, Sequence) and not isinstance(value, str) else value)


def _window(values: np.ndarray, ds: Dataset) -> np.ndarray:
    center = _first(ds.WindowCenter)
    width = _first(ds.WindowWidth)
    function = ds.get("VOILUTFunction", "LINEAR").upper()
    if not np.isfinite([center, width]).all():
        raise ValueError("DICOM 窗宽或窗位无效。")
    if function == "LINEAR" and width >= 1:
        if width == 1:
            return (values > center - 0.5).astype(float)
        return (values - (center - 0.5)) / (width - 1) + 0.5
    if function == "LINEAR_EXACT" and width > 0:
        return (values - center) / width + 0.5
    if function == "SIGMOID" and width > 0:
        with np.errstate(over="ignore"):
            return 1 / (1 + np.exp(-4 * (values - center) / width))
    raise ValueError(f"DICOM 窗宽或窗位函数无效（{function}）。")


def _stored_bounds(ds: Dataset) -> tuple[int, int]:
    bits = int(ds.BitsStored)
    if not 1 <= bits <= 32:
        raise ValueError("DICOM 像素位深无效。")
    if ds.PixelRepresentation == 1:
        half = 1 << (bits - 1)
        return -half, half - 1
    return 0, (1 << bits) - 1


def _gray(pixels: np.ndarray, ds: Dataset) -> np.ndarray:
    values = apply_modality_lut(pixels, ds)
    if ds.get("VOILUTSequence"):
        values = apply_voi(values, ds)
        levels = (1 << int(ds.VOILUTSequence[0].LUTDescriptor[2])) - 1
        return values / levels

    values = values.astype(np.float64, copy=False)
    if "WindowCenter" in ds and "WindowWidth" in ds:
        return _window(values, ds)

    if ds.get("ModalityLUTSequence"):
        low, high = 0, (1 << int(ds.ModalityLUTSequence[0].LUTDescriptor[2])) - 1
    elif "BitsStored" in ds:
        low, high = _stored_bounds(ds)
        if "RescaleSlope" in ds and "RescaleIntercept" in ds:
            slope, intercept = float(ds.RescaleSlope), float(ds.RescaleIntercept)
            low, high = sorted((low * slope + intercept, high * slope + intercept))
    else:
        low, high = float(values.min()), float(values.max())
    return (values - low) / (high - low) if high > low else np.zeros_like(values)


def _uint8(values: np.ndarray) -> np.ndarray:
    if np.isnan(values).any():
        raise ValueError("DICOM 像素或灰阶转换结果包含无效数值。")
    return np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)


def render_frame(pixels: np.ndarray, ds: Dataset, frame_index: int) -> Image.Image:
    photo = ds.PhotometricInterpretation
    if photo in MONOCHROME:
        if pixels.shape != (ds.Rows, ds.Columns):
            raise ValueError("DICOM 灰阶像素尺寸与元数据不一致。")
        values = _gray(pixels, _gray_attributes(ds, frame_index))
        if photo == "MONOCHROME1":
            values = 1 - values
        return Image.fromarray(_uint8(values))

    if pixels.shape != (ds.Rows, ds.Columns, 3):
        raise ValueError("DICOM 彩色像素尺寸与元数据不一致。")
    if pixels.dtype == np.uint8 and ds.BitsStored == 8:
        return Image.fromarray(pixels)
    low, high = _stored_bounds(ds)
    return Image.fromarray(_uint8((pixels.astype(np.float64) - low) / (high - low)))
