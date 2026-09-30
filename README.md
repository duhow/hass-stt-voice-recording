# STT Proxy Recorder for Home Assistant

This custom integration adds a Speech-to-Text engine that records incoming Assist audio locally, then forwards the same bytes and `SpeechMetadata` to an STT engine already configured in Home Assistant. It uses Home Assistant's built-in FFmpeg integration and binary to create a FLAC copy. It does not define a new STT API or modify Home Assistant Core.

## Install

Copy `custom_components/stt_proxy` into the `custom_components` directory under your Home Assistant configuration directory, then restart Home Assistant. In **Settings → Devices & services → Add integration**, add **STT Proxy Recorder** and choose an existing STT engine. Select the new `STT Proxy Recorder` engine in an Assist pipeline.

The selected engine must remain configured and available. Audio is buffered in memory until the incoming stream ends, saved locally, and then replayed to the upstream engine. Upstream failure does not delete the saved recording.

## Recordings

By default, recordings are saved under `<HA config>/voice_recordings/`. Change this using the integration's options. The path must be relative to the HA configuration directory and cannot escape it. Each recording consists of:

- `recording_<UTC timestamp>_<random id>.audio`: the exact received bytes (not transcoded or guaranteed to be a standalone WAV file).
- A sibling `.json` file with the speech format, codec, sample rate, bit rate, channel count, and language. After successful transcription, it also contains a `transcribed` field with the recognized text; it is absent if upstream transcription fails.
- A sibling `.flac` file converted asynchronously after the exact `.audio` bytes and JSON sidecar are stored. Its audio stream uses the source audio's decoded sample rate/channels, while Vorbis comments contain every JSON field (`language`, source `format`, `codec`, `bit_rate`, `sample_rate`, `channel`, and `transcribed` after success). The lossless metadata update after transcription remuxes the FLAC without re-encoding audio.

New files are created with owner-only read/write permissions where supported. The FLAC copy adds storage overhead alongside the exact input and JSON; recordings are **not automatically rotated or deleted**. Monitor disk use and manually remove files you no longer need. If FFmpeg cannot decode an input, the original `.audio` and `.json` are retained and STT proxying continues.

## Privacy

Audio and transcription text are sensitive personal data. This integration stores every request that reaches its STT entity, including recordings whose later upstream transcription fails. When transcription succeeds, the text is also embedded in the FLAC metadata. It also forwards those bytes to the selected upstream engine, which may itself process them remotely. Restrict access to the HA configuration directory, choose a trusted upstream, and delete recordings when they are no longer needed. There is no encryption-at-rest or retention policy built in.

## Validation

The storage helper tests run with Python's standard library:

```sh
python -m unittest discover -s tests -v
```

A Home Assistant runtime/pipeline test is not included in this repository yet.
