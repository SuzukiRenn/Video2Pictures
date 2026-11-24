from io import BytesIO
from pathlib import Path

import av
import numpy as np
from PIL import Image
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.uid import ExplicitVRLittleEndian, JPEGBaseline8Bit, SecondaryCaptureImageStorage, generate_uid


VIDEO_SIZE = (48, 32)
COLORS = ((220, 30, 42), (14, 210, 44), (19, 35, 225), (215, 167, 30), (125, 72, 205))


def make_video(path: Path) -> Path:
    with av.open(str(path), "w") as container:
        stream = container.add_stream("ffv1", rate=25)
        stream.width, stream.height = VIDEO_SIZE
        stream.pix_fmt = "bgr0"
        for color in COLORS:
            frame = av.VideoFrame.from_image(Image.new("RGB", VIDEO_SIZE, color))
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return path


def make_dicom(path: Path, frames: np.ndarray, photo="MONOCHROME2", *, jpeg=False, planar=False, **metadata) -> Path:
    color = photo == "RGB"
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = JPEGBaseline8Bit if jpeg else ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(path, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.Rows, ds.Columns = frames.shape[1:3]
    ds.SamplesPerPixel = 3 if color else 1
    ds.PhotometricInterpretation = photo
    if len(frames) > 1:
        ds.NumberOfFrames = len(frames)
    if color:
        ds.PlanarConfiguration = int(planar)
    ds.BitsAllocated = frames.dtype.itemsize * 8
    ds.BitsStored = ds.BitsAllocated
    ds.HighBit = ds.BitsStored - 1
    ds.PixelRepresentation = int(frames.dtype.kind == "i")
    for key, value in metadata.items():
        setattr(ds, key, value)
    if jpeg:
        encoded = []
        for frame in frames:
            stream = BytesIO()
            Image.fromarray(frame).save(stream, "JPEG", quality=100, subsampling=0)
            encoded.append(stream.getvalue())
        ds.PixelData = encapsulate(encoded)
        ds["PixelData"].is_undefined_length = True
    else:
        ds.PixelData = (frames.transpose(0, 3, 1, 2) if planar else frames).tobytes()
        ds.PixelData += b"\0" * (len(ds.PixelData) % 2)
    ds.save_as(path, enforce_file_format=True)
    return path
