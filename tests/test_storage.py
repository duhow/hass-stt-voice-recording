"""Tests for private local audio recording storage."""

from enum import Enum
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import wave
from types import SimpleNamespace

_STORAGE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "stt_proxy" / "storage.py"
)
_STORAGE_SPEC = importlib.util.spec_from_file_location("stt_proxy_storage", _STORAGE_PATH)
assert _STORAGE_SPEC and _STORAGE_SPEC.loader
_STORAGE_MODULE = importlib.util.module_from_spec(_STORAGE_SPEC)
_STORAGE_SPEC.loader.exec_module(_STORAGE_MODULE)
write_recording = _STORAGE_MODULE.write_recording
write_transcription = _STORAGE_MODULE.write_transcription
convert_recording_to_flac = _STORAGE_MODULE.convert_recording_to_flac


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

            self.assertRegex(path.name, re.compile(r"^recording_\d{8}_\d{6}\.audio$"))
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

    def test_appends_transcription_without_losing_existing_metadata(self) -> None:
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
            recording_path = write_recording(root, "voice_recordings", b"audio", metadata)

            write_transcription(recording_path, "Turn on the kitchen lights.")

            self.assertEqual(
                json.loads(recording_path.with_suffix(".json").read_text()),
                {
                    "language": "en-US",
                    "format": "pcm",
                    "codec": "pcm",
                    "bit_rate": 16,
                    "sample_rate": 16000,
                    "channel": 1,
                    "transcribed": "Turn on the kitchen lights.",
                },
            )

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe unavailable")
    def test_converts_wav_to_private_flac_with_metadata_and_later_transcription(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            wav_path = root / "fixture.wav"
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(b"\x00\x00" * 1600)
            metadata = SimpleNamespace(
                language="ca-ES", format=SimpleNamespace(value="wav"),
                codec=SimpleNamespace(value="pcm"), bit_rate=16,
                sample_rate=16000, channel=1,
            )
            recording_path = write_recording(root, "voice_recordings", wav_path.read_bytes(), metadata)

            flac_path = convert_recording_to_flac(recording_path, shutil.which("ffmpeg"))
            self.assertEqual(flac_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(flac_path.suffix, ".flac")
            write_transcription(recording_path, "test transcription", shutil.which("ffmpeg"))

            probe = subprocess.run(
                [shutil.which("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(flac_path)],
                check=True, capture_output=True, text=True,
            )
            inspected = json.loads(probe.stdout)
            stream = inspected["streams"][0]
            tags = {key.lower(): value for key, value in inspected["format"]["tags"].items()}
            self.assertEqual(stream["codec_name"], "flac")
            self.assertEqual(stream["sample_rate"], "16000")
            self.assertEqual(stream["channels"], 1)
            self.assertEqual(tags["language"], "ca-ES")
            self.assertEqual(tags["format"], "wav")
            self.assertEqual(tags["codec"], "pcm")
            self.assertEqual(tags["bit_rate"], "16")
            self.assertEqual(tags["sample_rate"], "16000")
            self.assertEqual(tags["channel"], "1")
            self.assertEqual(tags["transcribed"], "test transcription")
            self.assertTrue(recording_path.exists())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe unavailable")
    def test_converts_headerless_pcm_using_stt_audio_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_pcm = b"\x00\x00\x01\x00" * 8000
            metadata = SimpleNamespace(
                language="ca-ES", format=SimpleNamespace(value="wav"),
                codec=SimpleNamespace(value="pcm"), bit_rate=16,
                sample_rate=16000, channel=1,
            )
            recording_path = write_recording(root, "voice_recordings", raw_pcm, metadata)

            flac_path = convert_recording_to_flac(recording_path, shutil.which("ffmpeg"))
            probe = subprocess.run(
                [shutil.which("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(flac_path)],
                check=True, capture_output=True, text=True,
            )

            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(recording_path.read_bytes(), raw_pcm)
            self.assertEqual(stream["codec_name"], "flac")
            self.assertEqual(stream["sample_rate"], "16000")
            self.assertEqual(stream["channels"], 1)


if __name__ == "__main__":
    unittest.main()
