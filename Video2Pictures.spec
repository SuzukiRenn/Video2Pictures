import sys
from pathlib import Path

root = Path(SPECPATH)
analysis = Analysis(
    [str(root / "video2pictures" / "__main__.py")],
    pathex=[str(root)],
)
name = "Video2Pictures"
executable = EXE(
    PYZ(analysis.pure),
    analysis.scripts,
    exclude_binaries=True,
    name=name,
    console=False,
    upx=False,
)
directory = COLLECT(executable, analysis.binaries, analysis.datas, name=name, upx=False)
if sys.platform == "darwin":
    bundle = BUNDLE(
        directory,
        name=f"{name}.app",
        bundle_identifier="io.github.suzukirenn.video2pictures",
        info_plist={"NSHighResolutionCapable": True},
    )
