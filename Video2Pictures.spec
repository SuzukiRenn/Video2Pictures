import sys
from pathlib import Path

root = Path(SPECPATH)
sys.path.insert(0, str(root))
from scripts.notices import bundled_notices

analysis = Analysis(
    [str(root / "video2pictures" / "__main__.py")],
    pathex=[str(root)],
)
analysis.datas += Tree(str(root / "third-party"), prefix="third-party")
analysis.datas += bundled_notices(analysis.binaries)
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
