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
        system = Path(os.environ["SystemRoot"])
        environment["PATH"] = os.pathsep.join(map(str, (system / "System32", system)))
    else:
        environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    with TemporaryDirectory(prefix="Video2Pictures 验证 ") as directory:
        work = Path(directory)
        if sys.platform == "darwin":
            subprocess.run(["ditto", "-x", "-k", str(archive), str(work)], check=True)
            executable = work / "Video2Pictures.app" / "Contents" / "MacOS" / "Video2Pictures"
            notices = executable.parents[1] / "Resources" / "third-party"
        else:
            with ZipFile(archive) as package:
                package.extractall(work)
            executable = work / "Video2Pictures" / "Video2Pictures.exe"
            notices = executable.parent / "_internal" / "third-party"

        for document in (
            "README.md",
            "licenses/CPython-3.14.6/LICENSE",
            "licenses/Tcl-Tk/tcl-8.6.15.terms" if sys.platform == "win32" else "licenses/Tcl-Tk/tcl-9.0.3.terms",
            "licenses/Tcl-Tk/tk-8.6.15.terms" if sys.platform == "win32" else "licenses/Tcl-Tk/tk-9.0.3.terms",
            "licenses/FFmpeg/COPYING.LGPLv3",
            "licenses/FFmpeg-dependencies/x264.txt",
            "licenses/FFmpeg-dependencies/x265.txt",
            "wheel-notices/av-17.0.1/LICENSE.txt",
            "wheel-notices/numpy-2.4.4/LICENSE.txt",
            "wheel-notices/Pillow-12.2.0/LICENSE",
            "wheel-notices/pydicom-3.0.2/LICENSE",
            "wheel-notices/PyInstaller-6.22.3/COPYING.txt",
        ):
            if not (notices / document).is_file() or (notices / document).stat().st_size < 200:
                raise AssertionError(f"Missing third-party notice: {document}")
        print("Third-party notices verified in the extracted package")

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
