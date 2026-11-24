# 第三方组件与来源

Windows 安装包在 `Video2Pictures/_internal/third-party` 保存此说明。macOS 安装包内的路径为 `Video2Pictures.app/Contents/Resources/third-party`。`wheel-notices` 保留安装时所用 wheel 声明的许可和版权文本，`licenses` 收录可独立查阅的上游原文。构建时发现的解释器许可，以及使用 Conda 打包时从已有包缓存找到的运行库许可，放在 `runtime-notices`。

## Python 库与运行时

| 组件 | 锁定来源与随包文本 |
| --- | --- |
| PyAV 17.0.1 | [源码](https://github.com/PyAV-Org/PyAV/tree/v17.0.1) · [发布的 wheel 和 sdist](https://pypi.org/project/av/17.0.1/#files) · `wheel-notices/av-17.0.1` |
| NumPy 2.4.4 | [源码](https://github.com/numpy/numpy/tree/v2.4.4) · [wheel 和 sdist](https://pypi.org/project/numpy/2.4.4/#files) · `wheel-notices/numpy-2.4.4` 包含 wheel 汇总的 BLAS、LAPACK 及运行库通知。实测 Windows wheel 使用 [scipy-openblas64 0.3.31.188.0](https://pypi.org/project/scipy-openblas64/0.3.31.188.0/) · [OpenBLAS 0.3.31 源码](https://github.com/OpenMathLib/OpenBLAS/tree/v0.3.31) |
| Pillow 12.2.0 | [源码](https://github.com/python-pillow/Pillow/tree/12.2.0) · [构建流程](https://github.com/python-pillow/Pillow/blob/12.2.0/.github/workflows/wheels.yml) · [Windows 依赖获取脚本](https://github.com/python-pillow/Pillow/blob/12.2.0/winbuild/build_prepare.py) · `wheel-notices/Pillow-12.2.0/LICENSE` 包含 wheel 附带的图像编解码器等依赖声明 |
| pydicom 3.0.2 | [源码](https://github.com/pydicom/pydicom/tree/v3.0.2) · [wheel 和 sdist](https://pypi.org/project/pydicom/3.0.2/#files) · `wheel-notices/pydicom-3.0.2` |
| PyInstaller 6.22.3 | [源码及 bootloader](https://github.com/pyinstaller/pyinstaller/tree/v6.22.3) · [wheel 和 sdist](https://pypi.org/project/pyinstaller/6.22.3/#files) · `wheel-notices/PyInstaller-6.22.3/COPYING.txt` 含 bootloader 例外条款 |
| CPython 3.14.6 | [官方发行及源码](https://www.python.org/downloads/release/python-3146/) · [Windows 运行时依赖获取脚本](https://github.com/python/cpython/blob/v3.14.6/PCbuild/get_external.py) · [macOS 运行时依赖构建配方](https://github.com/python/cpython/blob/v3.14.6/Mac/BuildScript/build-installer.py) · `licenses/CPython-3.14.6` 含 PSF 许可、第三方版权和 Windows 分发条款 |
| Tcl、Tk | `licenses/Tcl-Tk` 含 Windows 的 8.6.15 和 macOS 配方的 9.0.3 上游许可原文。8.6.15 源码 [Tcl](https://github.com/tcltk/tcl/tree/core-8-6-15) · [Tk](https://github.com/tcltk/tk/tree/core-8-6-15)；9.0.3 源码 [Tcl](https://github.com/tcltk/tcl/tree/core-9-0-3) · [Tk](https://github.com/tcltk/tk/tree/core-9-0-3) |

## PyAV 所带的 FFmpeg 8.0.1

[PyAV v17.0.1 的供应配置](https://github.com/PyAV-Org/PyAV/blob/v17.0.1/scripts/ffmpeg-latest.json) 指向 [pyav-ffmpeg 8.0.1-5](https://github.com/PyAV-Org/pyav-ffmpeg/releases/tag/8.0.1-5)。该发行提供 `ffmpeg-windows-x86_64.tar.gz`、`ffmpeg-macos-arm64.tar.gz` 和 `ffmpeg-macos-x86_64.tar.gz` 构建归档。对应的[构建仓库源码归档](https://github.com/PyAV-Org/pyav-ffmpeg/archive/refs/tags/8.0.1-5.tar.gz)包含[构建脚本及各输入的 SHA-256](https://github.com/PyAV-Org/pyav-ffmpeg/blob/8.0.1-5/scripts/build-ffmpeg.py)、[平台构建流程](https://github.com/PyAV-Org/pyav-ffmpeg/tree/8.0.1-5/.github/workflows)和[补丁目录](https://github.com/PyAV-Org/pyav-ffmpeg/tree/8.0.1-5/patches)。

Windows x64 随包 DLL 的实测记录如下。

- FFmpeg 基线为 8.0.1，`libavcodec` 版本为 `62.11.100`。
- `avcodec_license()` 返回 `LGPL version 3 or later`。
- `avcodec_configuration()` 包含 `--enable-version3`、`--enable-libx264`、`--enable-libx265`。上游 [`ffmpeg.patch`](https://github.com/PyAV-Org/pyav-ffmpeg/blob/8.0.1-5/patches/ffmpeg.patch) 将 x264 和 x265 从 FFmpeg 配置脚本的 GPL 依赖列表移至 version3 依赖列表。FFmpeg、x264、x265 原文分别收入 `licenses/FFmpeg` 和 `licenses/FFmpeg-dependencies`。

| 构建输入 | 锁定源码与 SHA-256 |
| --- | --- |
| FFmpeg 8.0.1 | [官方源码归档](https://ffmpeg.org/releases/ffmpeg-8.0.1.tar.xz) · `05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41` |
| x264 | [构建脚本指定的提交归档](https://code.videolan.org/videolan/x264/-/archive/b35605ace3ddf7c1a5d67a2eb553f034aef41d55/x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55.tar.bz2) · `6eeb82934e69fd51e043bd8c5b0d152839638d1ce7aa4eea65a3fedcf83ff224` |
| x265 4.1 | [官方源码归档](https://bitbucket.org/multicoreware/x265_git/downloads/x265_4.1.tar.gz) · `a31699c6a89806b74b0151e5e6a7df65de4b49050482fe5ebf8a4379d7af8f29` |

同一锁定脚本的 `codec_group` 列出了 LAME、Ogg、Opus、Speex、Vorbis、dav1d、SVT-AV1、libvpx、libpng、libwebp、OpenH264、OpenCORE AMR 等组件的来源和校验值。其许可文本位于 `licenses/FFmpeg-dependencies`。Windows x64 还使用脚本所列的 Intel VPL、NV Codec Headers、AMF Headers。

FFmpeg 在 Windows 上带有来自 [MSYS2 MinGW-w64 包仓库](https://repo.msys2.org/mingw/mingw64/)的 GCC 运行库、libiconv、winpthreads 和 zlib。实测捆绑的 DLL 报告 [libiconv 1.18](https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.18.tar.gz) 和 [zlib 1.3.1](https://github.com/madler/zlib/tree/v1.3.1)。构建配方未分别锁定 GCC 和 winpthreads 的 MSYS2 包版本。`licenses/Windows-FFmpeg-runtime` 收录 [GCC 运行库例外条款](https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html)、[winpthreads 版权文本](https://github.com/mingw-w64/mingw-w64/blob/v13.0.0/mingw-w64-libraries/winpthreads/COPYING)及 libiconv、zlib 许可。
