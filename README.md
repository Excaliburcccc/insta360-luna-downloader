# Insta360 Luna Downloader / Insta360 Luna 下载器

Unofficial Windows desktop downloader for Insta360 Luna Ultra cameras on the
camera's local Wi-Fi network.

非官方 Windows 桌面下载器，用于在电脑连接 Insta360 Luna Ultra 相机 Wi-Fi
后下载相机内的媒体文件。

[中文说明](#中文说明) | [English](#english)

## 中文说明

### 项目说明

Insta360 Luna 下载器是一个面向 Windows 的桌面工具。电脑连接 Luna Ultra
相机的本地 Wi-Fi 后，可以通过图形界面查看相机文件列表，选择文件并下载到
本地文件夹。

本项目与 Insta360 官方无关，也未获得 Insta360 官方背书或支持。请仅用于下载
你自己相机中的个人媒体文件。

### 当前功能

- 检测位于 `192.168.42.1` 的 Luna 相机
- 建立相机所需的本地控制会话
- 从 `/storage_internal/DCIM/Camera01/` 读取文件列表
- 在中文桌面界面中选择要下载的文件
- 支持 MP4 / LRV 文件筛选
- 支持断点续传式下载
- 支持选择本地下载路径并显示下载状态

### 使用方式

1. 打开 [Releases](https://github.com/Excaliburcccc/insta360-luna-downloader/releases)
   页面，下载最新的 Windows x64 压缩包。
2. 解压压缩包，运行 `Insta360LunaDownloader.exe`。
3. 让电脑连接 Luna Ultra 的 Wi-Fi。
4. 在程序中点击“刷新文件”。
5. 选择需要下载的文件和保存路径，然后点击“开始下载”。

### 安全说明

仓库会刻意排除抓包文件、Wi-Fi 密码、APK、个人媒体文件和构建产物。相关规则
见 `.gitignore`。请不要把自己的相机文件、网络凭据或私密抓包提交到仓库。

### 开发

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

运行应用：

```powershell
.\.venv\Scripts\python.exe -m luna_downloader
```

构建 Windows 可执行程序：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

更多协议记录见 [docs/protocol-notes.md](docs/protocol-notes.md)。

## English

### About

Insta360 Luna Downloader is a Windows desktop tool for downloading media from an
Insta360 Luna Ultra camera over the camera's local Wi-Fi network. After the PC
is connected to the Luna Wi-Fi, the app can list camera files, let you choose
what to download, and save the selected files to a local folder.

This project is not affiliated with, endorsed by, or supported by Insta360. It
is intended only for downloading your own media from your own camera.

### Current Scope

- Detect a Luna camera at `192.168.42.1`
- Open the local control session required by the camera
- List files from `/storage_internal/DCIM/Camera01/`
- Select files in a Chinese desktop UI
- Filter MP4 / LRV files
- Download files with resume support
- Choose a local download folder and show download status

### Usage

1. Open the [Releases](https://github.com/Excaliburcccc/insta360-luna-downloader/releases)
   page and download the latest Windows x64 archive.
2. Extract the archive and run `Insta360LunaDownloader.exe`.
3. Connect the PC to the Luna Ultra Wi-Fi network.
4. Click "刷新文件" in the app.
5. Select files and a destination folder, then click "开始下载".

### Safety Notes

The repository intentionally excludes packet captures, Wi-Fi credentials, APKs,
personal media files, and build artifacts. See `.gitignore`. Do not commit your
own camera files, network credentials, or private packet captures.

### Development

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

Run the app:

```powershell
.\.venv\Scripts\python.exe -m luna_downloader
```

Build a Windows executable:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

See [docs/protocol-notes.md](docs/protocol-notes.md) for protocol notes.
