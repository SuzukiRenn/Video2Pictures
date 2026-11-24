# Video2Pictures

离线桌面工具，按帧将视频或单帧、多帧 DICOM 导出为 PNG 或 JPEG。

## 下载与使用

从 [GitHub Releases](https://github.com/SuzukiRenn/Video2Pictures/releases) 下载并解压对应的 ZIP。Windows x64 打开 `Video2Pictures.exe`，并将 `_internal` 留在同一个文件夹内。macOS 选 `macos-arm64`（Apple Silicon）或 `macos-x64`（Intel），打开 `Video2Pictures.app`。macOS 构建使用临时签名，尚未做 Apple 公证，首次打开时系统可能拦截。

安装包随附许可文本和[第三方组件来源说明](third-party/README.md)。

选择源文件后等待帧数出现。默认输出到源文件旁的 `<文件名>_frames`，也可选其他目录。帧号从 1 开始。

- **全部帧**导出所有帧。
- **均匀抽取**覆盖首尾帧，只抽 1 张时取首帧。
- **指定帧号 / 范围**接受 `1,3-5` 这样的输入，按原始帧号升序导出，每个帧号只导出一次。

默认 PNG，JPEG 为有损压缩。输出按原始帧号命名，如 `frame_000005.png`。文件名冲突时追加 `_2` 等后缀。取消或出错后，已经写完的图片会保留。

视频按播放顺序计数，长视频需要先解码一遍。导出保留像素分辨率，并应用视频的直角旋转元数据。DICOM 读取文件内的帧，灰阶输出为 8 位显示图，优先使用 VOI LUT 或第一组窗宽窗位，处理 MONOCHROME1 反相。支持常见未压缩灰阶、RGB 和 YBR 图像，以及解码器可读的压缩格式。遇到无法解码的文件时，窗口会显示原因。请保留原始 DICOM 以保留原始像素值及元数据。

## 从源码运行和打包

使用带 Tk 的 Python 3.14。在项目目录执行以下命令。Windows 可用 `py -3.14` 创建环境，之后用 `.venv\Scripts\python.exe`。macOS 用 `.venv/bin/python`。

```sh
python3.14 -m venv .venv
```

以下命令中的 `python` 指该环境中的 Python。

```sh
python -m pip install --only-binary=:all: -r requirements.txt
python -m video2pictures
python -m unittest discover -v
```

在目标系统与架构上使用 CI 锁定的 Python 3.14.6 安装打包依赖，再构建并验证 ZIP。

```sh
python -m pip install --only-binary=:all: -r requirements-build.txt
python scripts/package.py
python -m tests.smoke release/Video2Pictures-windows-x64.zip
```

最后一条命令按平台更换 ZIP 文件名。GitHub Actions 在 Windows x64、macOS Apple Silicon 和 Intel 上分别测试、构建，并从解压后的应用导出合成视频和 DICOM。`main` 的构建结果在 Actions 中下载，`v*` 标签通过三项构建后生成 Release 附件。
