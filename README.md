# Insta360 Luna Downloader

Unofficial Windows desktop downloader for Insta360 Luna Ultra cameras on the
camera's local Wi-Fi network.

This project is not affiliated with, endorsed by, or supported by Insta360. It
is intended for downloading your own media from your own camera.

## Current Scope

- Detect a Luna camera at `192.168.42.1`
- Open the local control session required by the camera
- List files from `/storage_internal/DCIM/Camera01/`
- Select files in a desktop UI
- Download files with resume support

## Safety Notes

The repository intentionally excludes packet captures, Wi-Fi credentials, APKs,
and personal media files. See `.gitignore`.

## Development

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

