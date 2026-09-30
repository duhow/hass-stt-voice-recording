"""Tests for private local audio recording storage."""

from enum import Enum
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

_STORAGE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "stt_proxy" / "storage.py"
)
_STORAGE_SPEC = importlib.util.spec_from_file_location("stt_proxy_storage", _STORAGE_PATH)
assert _STORAGE_SPEC and _STORAGE_SPEC.loader
_STORAGE_MODULE = importlib.util.module_from_spec(_STORAGE_SPEC)
_STORAGE_SPEC.loader.exec_module(_STORAGE_MODULE)
write_recording = _STORAGE_MODULE.write_recording


class Value(Enum):
    """Enum value matching Home Assistant audio metadata values."""

    VALUE = "pcm"


class RecordingStorageTest(unittest.TestCase):
    """Verify recording content, metadata, permissions, and path safety."""

    def test_writes_exact_audio_and_metadata_with_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            metadata = SimpleNamespace(
                language="en-US",
                format=Value.VALUE,
                codec=Value.VALUE,
                bit_rate=16,
                sample_rate=16000,
                channel=1,
            )

            path = write_recording(root, "voice_recordings", b"\x00audio\xff", metadata)

            self.assertEqual(path.read_bytes(), b"\x00audio\xff")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(
                json.loads(path.with_suffix(".json").read_text()),
                {
                    "language": "en-US",
                    "format": "pcm",
                    "codec": "pcm",
                    "bit_rate": 16,
                    "sample_rate": 16000,
                    "channel": 1,
                },
            )

    def test_rejects_path_outside_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            metadata = SimpleNamespace()
            for directory in ("../outside", str(root / "absolute")):
                with self.subTest(directory=directory), self.assertRaises(ValueError):
                    write_recording(root, directory, b"audio", metadata)


if __name__ == "__main__":
    unittest.main()
