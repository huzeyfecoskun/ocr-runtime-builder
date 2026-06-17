#!/usr/bin/env python3
"""Persistent MMOCR SVTR-small OCR worker.

Protocol: JSON lines on stdin/stdout.
Request:  {"id": 1, "imageBase64": "...", "outputFormat": "raw"|"digits", "whitelist": "..."}
Response: {"id": 1, "text": "...", "rawText": "...", "score": 0.99}
"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image


MODEL_NAME = "svtr-small"
MODEL_FILENAME = "svtr-small_20e_st_mj-35d800d6.pth"


def patch_mmocr_runtime() -> None:
    import torch
    import mmengine.model.utils as model_utils
    import mmocr.apis.inferencers.base_mmocr_inferencer as base_inferencer

    # CPU text-recognition inference does not need mmcv SyncBatchNorm conversion.
    # Avoid importing mmcv native ops on macOS builds where they may fail to load.
    model_utils.revert_sync_batchnorm = lambda model: model
    base_inferencer.revert_sync_batchnorm = lambda model: model

    original_torch_load = torch.load

    def torch_load_with_legacy_checkpoint(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    torch.load = torch_load_with_legacy_checkpoint


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        for parent in executable.parents:
            if parent.name == "ocr-runtime":
                return parent.parent
        return executable.parent.parent
    return Path(__file__).resolve().parents[2]


def resolve_weights() -> str | None:
    override = os.environ.get("NINES_SVTR_WEIGHTS")
    if override:
        return override
    candidates = [
        resource_root() / "ocr-models" / MODEL_FILENAME,
        Path.cwd() / "resources" / "ocr-models" / MODEL_FILENAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def strip_unknown_tokens(text: str) -> str:
    return text.replace("<UKN>", "").replace("<UNK>", "")


def normalize_digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def apply_whitelist(text: str, whitelist: str) -> str:
    if not whitelist:
        return text
    allowed = set(whitelist)
    return "".join(ch for ch in text if ch in allowed)


def load_inferencer():
    patch_mmocr_runtime()
    from mmocr.apis import TextRecInferencer

    return TextRecInferencer(MODEL_NAME, weights=resolve_weights(), device="cpu")


def recognize(inferencer, image_base64: str, output_format: str, whitelist: str) -> dict[str, object]:
    image_bytes = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    result = inferencer(np.array(image), return_vis=False)
    prediction = result["predictions"][0] if result.get("predictions") else {}
    raw_text = strip_unknown_tokens(str(prediction.get("text", "")).strip())
    text = normalize_digits(raw_text) if output_format == "digits" else raw_text
    text = apply_whitelist(text, whitelist)
    return {
        "text": text,
        "rawText": raw_text,
        "score": prediction.get("scores"),
    }


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def main() -> None:
    try:
        with contextlib.redirect_stdout(sys.stderr):
            inferencer = load_inferencer()
        emit({"type": "ready"})
    except Exception as exc:
        emit({"type": "fatal", "error": str(exc)})
        return

    for line in sys.stdin:
        try:
            request = json.loads(line)
            request_id = request.get("id")
            with contextlib.redirect_stdout(sys.stderr):
                result = recognize(
                    inferencer,
                    str(request.get("imageBase64", "")),
                    str(request.get("outputFormat", "raw")),
                    str(request.get("whitelist", "")),
                )
            emit({"id": request_id, **result})
        except Exception as exc:
            emit({"id": request.get("id") if "request" in locals() else None, "error": str(exc)})


if __name__ == "__main__":
    main()
