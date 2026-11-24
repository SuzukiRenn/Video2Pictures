import sys
from pathlib import Path

from video2pictures.ui import Application, create_root


def _smoke_test(input_path: Path, directory: Path) -> int:
    root = create_root()
    root.withdraw()
    app = Application(root)
    app.custom_destination = True
    app.destination.set(str(directory))
    app.load(input_path)
    result = 1

    def check(exporting=False):
        nonlocal result
        if app.job is not None:
            root.after(50, check, exporting)
        elif exporting:
            if len(list(directory.glob("frame_*.png"))) == app.source.total:
                result = 0
            app._close()
        elif app.source is not None:
            app.action.invoke()
            root.after(50, check, True)
        else:
            app._close()

    root.after(50, check)
    root.after(30_000, app._close)
    root.mainloop()
    return result


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--smoke-test":
        return _smoke_test(Path(sys.argv[2]), Path(sys.argv[3]))
    root = create_root()
    Application(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
