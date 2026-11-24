import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np
from PIL import Image

from tests.fixtures import COLORS, VIDEO_SIZE, make_dicom, make_video


def verify_archive(archive: Path) -> None:
    environment = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY", "DYLD_LIBRARY_PATH"):
        environment.pop(key, None)
    if sys.platform == "win32":
        system = Path(environment["SystemRoot"])
        environment["PATH"] = os.pathsep.join(map(str, (system / "System32", system)))
    else:
        environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    with TemporaryDirectory(prefix="Video2Pictures 验证 ") as directory:
        work = Path(directory)
        if sys.platform == "darwin":
            subprocess.run(["ditto", "-x", "-k", str(archive), str(work)], check=True)
            executable = work / "Video2Pictures.app" / "Contents" / "MacOS" / "Video2Pictures"
        else:
            with ZipFile(archive) as package:
                package.extractall(work)
            executable = work / "Video2Pictures" / "Video2Pictures.exe"

        video = make_video(work / "合成视频.mkv")
        gray = np.full((2, 16, 16), 45, dtype=np.uint8)
        gray[1].fill(201)
        dicom = make_dicom(work / "合成影像.dcm", gray, jpeg=True)
        for source, expected, expected_size, value in (
            (video, len(COLORS), VIDEO_SIZE, COLORS[-1]),
            (dicom, 2, (16, 16), 201),
        ):
            output = work / (source.stem + "_结果")
            subprocess.run([str(executable), "--smoke-test", str(source), str(output)],
                           cwd=work, env=environment, timeout=45, check=True)
            names = sorted(path.name for path in output.iterdir())
            if names != [f"frame_{number:06d}.png" for number in range(1, expected + 1)]:
                raise AssertionError(f"Unexpected output names: {names}")
            with Image.open(output / names[-1]) as image:
                actual = (image.size, image.getpixel((5, 5)))
                if actual != (expected_size, value):
                    raise AssertionError(f"Unexpected decoded image: {actual}")
            print(f"{source.suffix}: {expected} PNGs verified from the extracted app")


if __name__ == "__main__":
    verify_archive(Path(sys.argv[1]).resolve())
