"""Private local recording storage helpers."""

import json
import os
from pathlib import Path
import subprocess
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


def convert_recording_to_flac(recording_path: Path, ffmpeg_binary: str) -> Path:
    """Create a private FLAC sibling with every sidecar field as a Vorbis comment."""
    metadata_path = recording_path.with_suffix(".json")
    with metadata_path.open(encoding="utf-8") as metadata_file:
        metadata_dict = json.load(metadata_file)

    flac_path = recording_path.with_suffix(".flac")
    temporary_path = recording_path.with_name(f".{recording_path.stem}.tmp.flac")
    command = [ffmpeg_binary, "-nostdin", "-v", "error", "-y", "-i", str(recording_path), "-map", "0:a:0", "-c:a", "flac"]
    for key, value in metadata_dict.items():
        command.extend(("-metadata", f"{key}={value}"))
    command.extend(("-f", "flac", str(temporary_path)))
    try:
        subprocess.run(command, check=True, capture_output=True)
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(flac_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return flac_path


def write_transcription(
    recording_path: Path, transcription: str, ffmpeg_binary: str = "ffmpeg"
) -> None:
    """Append the successful transcription to a recording's JSON metadata."""
    metadata_path = recording_path.with_suffix(".json")
    with metadata_path.open(encoding="utf-8") as metadata_file:
        metadata_dict = json.load(metadata_file)
    metadata_dict["transcribed"] = transcription

    temporary_path = metadata_path.with_suffix(".json.tmp")
    descriptor = os.open(
        temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as metadata_file:
        json.dump(metadata_dict, metadata_file, indent=2)
        metadata_file.write("\n")
    temporary_path.replace(metadata_path)

    flac_path = recording_path.with_suffix(".flac")
    if flac_path.exists():
        _update_flac_metadata(flac_path, metadata_dict, ffmpeg_binary)


def _update_flac_metadata(
    flac_path: Path, metadata: dict[str, Any], ffmpeg_binary: str
) -> None:
    """Losslessly remux a FLAC to refresh its Vorbis comments atomically."""
    temporary_path = flac_path.with_name(f".{flac_path.stem}.tmp.flac")
    command = [ffmpeg_binary, "-nostdin", "-v", "error", "-y", "-i", str(flac_path), "-map", "0:a:0", "-c:a", "copy"]
    for key, value in metadata.items():
        command.extend(("-metadata", f"{key}={value}"))
    command.extend(("-f", "flac", str(temporary_path)))
    try:
        subprocess.run(command, check=True, capture_output=True)
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(flac_path)
    finally:
        temporary_path.unlink(missing_ok=True)
