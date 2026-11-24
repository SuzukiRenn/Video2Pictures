import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "Video2Pictures"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a native Video2Pictures ZIP.")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--release-dir", type=Path, default=ROOT / "release")
    args = parser.parse_args()
    dist, work, release = (path.resolve() for path in (args.dist_dir, args.work_dir, args.release_dir))
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in {"x86_64", "amd64"}:
        target = "windows-x64"
    elif sys.platform == "darwin" and machine in {"arm64", "x86_64"}:
        target = "macos-arm64" if machine == "arm64" else "macos-x64"
    else:
        parser.error(f"Unsupported build host: {sys.platform} {machine}")

    environment = os.environ.copy()
    conda_libraries = Path(sys.base_prefix) / "Library" / "bin"
    if sys.platform == "win32" and conda_libraries.is_dir():
        environment["PATH"] = str(conda_libraries) + os.pathsep + environment.get("PATH", "")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(dist), "--workpath", str(work), str(ROOT / f"{NAME}.spec"),
    ], cwd=ROOT, env=environment, check=True)

    release.mkdir(parents=True, exist_ok=True)
    basename = release / f"{NAME}-{target}"
    if sys.platform == "darwin":
        subprocess.run([
            "ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
            str(dist / f"{NAME}.app"), str(basename.with_suffix(".zip")),
        ], check=True)
    else:
        shutil.make_archive(str(basename), "zip", root_dir=dist, base_dir=NAME)
    print(basename.with_suffix(".zip"))


if __name__ == "__main__":
    main()
