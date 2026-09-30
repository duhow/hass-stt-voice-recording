"""Private local recording storage helpers."""

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import UTC, datetime


def write_recording(
    config_root: Path, directory: str, audio: bytes, metadata: Any
) -> Path:
    """Write one opaque audio payload and its decoding metadata privately."""
    configured_path = Path(directory)
    if configured_path.is_absolute() or ".." in configured_path.parts:
        raise ValueError("Recording directory must be relative to HA config")
    config_root = config_root.resolve()
    output_dir = (config_root / configured_path).resolve()
    if not output_dir.is_relative_to(config_root):
        raise ValueError("Recording directory must remain within HA config")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    recording_path = output_dir / f"recording_{stamp}_{uuid4().hex}.audio"
    metadata_path = recording_path.with_suffix(".json")
    descriptor = os.open(recording_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as recording_file:
        recording_file.write(audio)
    metadata_dict = {
        "language": metadata.language,
        "format": metadata.format.value,
        "codec": metadata.codec.value,
        "bit_rate": int(metadata.bit_rate),
        "sample_rate": int(metadata.sample_rate),
        "channel": int(metadata.channel),
    }
    metadata_descriptor = os.open(
        metadata_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(metadata_descriptor, "w", encoding="utf-8") as metadata_file:
        json.dump(metadata_dict, metadata_file, indent=2)
    return recording_path
