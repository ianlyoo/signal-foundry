from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from .models import InputSnapshot, RecommendationBatch, RunManifest


def load_snapshot(path: Path) -> InputSnapshot:
    return InputSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, object] | list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def write_batch(path: Path, batch: RecommendationBatch) -> None:
    write_json(path, batch.model_dump(mode="json"))


def write_manifest(path: Path, manifest: RunManifest) -> None:
    write_json(path, manifest.model_dump(mode="json"))


def write_snapshot(path: Path, snapshot: InputSnapshot) -> None:
    write_json(path, snapshot.model_dump(mode="json"))
