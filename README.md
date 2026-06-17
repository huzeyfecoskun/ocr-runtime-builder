# OCR Runtime Builder

Builds the **Windows x64** OCR runtime (`mmocr-svtr-worker.exe`) for the Nines Flow
app on GitHub-hosted Windows runners. The main application stays off GitHub —
this repo contains only the OCR worker script, the build script, and the workflow.

## Why a separate repo

PyInstaller is **not** a cross-compiler: it always emits a binary for the OS/arch
it runs on. A Windows `.exe` can only be produced inside Windows. GitHub Actions
`windows-latest` runners provide that environment on demand, so we trigger this
workflow manually whenever the OCR worker or its dependencies change, then copy
the resulting executable into the app.

## Contents

- `resources/ocr/mmocr-svtr-worker.py` — the OCR inference worker (self-contained).
- `scripts/build-mmocr-runtime.mjs` — cross-platform PyInstaller build script.
- `.github/workflows/build-ocr-runtime.yml` — manual-trigger build workflow.
- `requirements.txt` — dependency manifest / pip-cache key.

## Build & ship

1. **Trigger the build** (Actions tab → *Build OCR Runtime* → Run workflow), or with `gh`:
   ```sh
   gh workflow run build-ocr-runtime.yml
   gh run watch
   ```

2. **Download the artifact** (`ocr-runtime-win32-x64`, containing
   `resources/ocr-runtime/win32-x64/mmocr-svtr-worker.exe`) into the **app repo root**:
   ```sh
   # run from the Nines Flow app root (node_work/)
   gh run download -n ocr-runtime-win32-x64 -D .
   #   -> lands at resources/ocr-runtime/win32-x64/mmocr-svtr-worker.exe
   ```
   Without `gh`: download the artifact zip from the Actions tab and extract its
   `resources/ocr-runtime/win32-x64/mmocr-svtr-worker.exe` into the app's
   `resources/ocr-runtime/win32-x64/`.

3. **Commit the binary** into the app's `resources/ocr-runtime/win32-x64/`, then run
   the Windows packaging build (`electron-builder --win`). `electron-builder.yml`
   maps `resources/ocr-runtime` → `ocr-runtime` via `extraResources`, so the
   prebuilt executable is bundled automatically — no Windows host needed.

## Runtime model

The SVTR model (`svtr-small_20e_st_mj-35d800d6.pth`) is **not** bundled by
PyInstaller — the worker loads it by path from `resources/ocr-models/` at runtime
(see `resolve_weights()` in the worker). The app ships that model separately; CI
downloads it only to build against it.