# Insta360 Luna Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local open-source Windows desktop downloader for Luna Ultra Wi-Fi media.

**Architecture:** Keep camera protocol and download logic in testable pure-Python modules, then wrap them in a PySide6 UI. The app opens a Luna control session on `192.168.42.1:6666`, keeps it alive, lists nginx directory entries, and downloads selected files sequentially with resume support.

**Tech Stack:** Python 3.11+, PySide6, pytest, PyInstaller, GitHub Actions for Windows builds.

---

### Task 1: Open-Source Project Skeleton

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `docs/protocol-notes.md`

- [ ] Add MIT licensing and project metadata.
- [ ] Exclude packet captures, media files, downloaded tests, and secrets.
- [ ] Document the non-affiliation disclaimer.

### Task 2: Core Protocol Tests and Implementation

**Files:**
- Create: `tests/test_luna_client.py`
- Create: `src/luna_downloader/models.py`
- Create: `src/luna_downloader/luna_client.py`

- [ ] Write failing tests for size parsing and nginx index parsing.
- [ ] Implement `parse_size`, `parse_luna_index`, and `LunaFile`.
- [ ] Write a failing fake TCP-server test for the two-message `UCD2` handshake.
- [ ] Implement `LunaAuthSession`.

### Task 3: Resumable Download Tests and Implementation

**Files:**
- Create: `tests/test_downloader.py`
- Create: `src/luna_downloader/downloader.py`

- [ ] Write a fake HTTP server test proving range resume starts at the local file size.
- [ ] Implement sequential resumable downloads with progress callbacks.
- [ ] Add cancellation support through `threading.Event`.

### Task 4: Desktop UI

**Files:**
- Create: `src/luna_downloader/main.py`
- Create: `src/luna_downloader/__main__.py`
- Create: `src/luna_downloader/workers.py`
- Create: `src/luna_downloader/ui/main_window.py`

- [ ] Build a PySide6 main window with connection status, file table, folder picker, download buttons, progress bars, and log area.
- [ ] Run network operations in background Qt threads.
- [ ] Keep one control authorization session open while listing and downloading.

### Task 5: Packaging and GitHub Metadata

**Files:**
- Create: `scripts/build.ps1`
- Create: `.github/workflows/build-windows.yml`

- [ ] Add a PyInstaller build script.
- [ ] Add a GitHub Actions workflow that builds on Windows.
- [ ] Verify the local app imports and core tests pass.

