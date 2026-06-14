# Insta360 Luna Downloader Design

## Goal

Build an open-source Windows desktop application named
`insta360-luna-downloader` that lets a user connect their PC to a Luna Ultra
Wi-Fi network, browse camera files, choose a download folder, and download
selected media with progress and resume support.

## Product Scope

The first version targets manual Wi-Fi connection. The app detects and uses a
camera at `192.168.42.1`; it does not switch Wi-Fi networks itself. It supports
listing `.mp4` and `.lrv` files from the internal storage camera folder and
downloads selected files sequentially.

The app does not include packet captures, personal media, Wi-Fi credentials, or
Insta360 APKs. It is explicitly documented as an unofficial project for users'
own cameras and media.

## Architecture

The app uses Python with PySide6 for the desktop UI. Protocol and download logic
live in pure-Python modules so they can be tested without a GUI. The UI calls
background workers for connection checks, file listing, and downloads so the
window remains responsive.

Core modules:

- `luna_client.py`: camera reachability, `UCD2` authorization session, HTTP
  directory listing.
- `downloader.py`: resumable HTTP file downloads with progress callbacks.
- `models.py`: typed file, connection, and download status models.
- `ui/main_window.py`: PySide6 controls and view state.
- `workers.py`: Qt worker objects wrapping blocking network operations.

## UI Design

The main window has four areas:

- Connection header: camera IP, HTTP state, control session state, and refresh
  button.
- File table: checkboxes, filename, type, date, size, and per-file status.
- Download settings: destination folder picker, filters for all/MP4/LRV, and
  overwrite/resume behavior.
- Download status: current file, total progress, speed, log messages, start and
  cancel buttons.

The UI is utilitarian and dense enough for repeated use. It avoids marketing
copy and keeps all important actions visible.

## Error Handling

Errors are shown in the status log and connection header. Specific messages
cover: not connected to Luna Wi-Fi, HTTP still unauthorized, port `6666`
unavailable, lost authorization session, no files found, disk write failures,
and cancelled downloads.

## Testing

Pure Python tests cover nginx index parsing, size parsing, control-session
handshake bytes, and resumable download behavior against local fake servers.
UI verification is manual for the first version, with import smoke tests to
catch packaging regressions.

