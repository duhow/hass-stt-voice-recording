# STT Proxy Recorder for Home Assistant

This custom integration adds a Speech-to-Text engine that records incoming Assist audio locally, then forwards the same bytes and `SpeechMetadata` to an STT engine already configured in Home Assistant. It uses Home Assistant's built-in FFmpeg integration and binary to create a FLAC copy. It does not define a new STT API or modify Home Assistant Core.

## Install

[![Install repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=duhow&repository=hass-stt-voice-recording&category=integration)

Copy `custom_components/stt_proxy` into the `custom_components` directory under your Home Assistant configuration directory, then restart Home Assistant. 

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=stt_proxy)

In **Settings → Devices & services → Add integration**, add **STT Proxy Recorder** and choose an existing STT engine. Select the new `STT Proxy Recorder` engine in an Assist pipeline.

The selected engine must remain configured and available. Audio is buffered in memory until the incoming stream ends, saved locally, and then replayed to the upstream engine. Upstream failure does not delete the saved recording.

## Recordings

By default, recordings are saved under `<HA config>/voice_recordings/`. Change this using the integration's options. The path must be relative to the HA configuration directory and cannot escape it. Filenames use `recording_YYYYMMDD_HHMMSS`; if a recording already exists for that second, the timestamp advances to avoid overwriting it.

- Home Assistant's Assist pipeline may provide headerless PCM even when metadata reports `format=wav`; conversion uses the supplied codec, bit depth, sample rate, and channel count when needed.
- On successful conversion, the `.flac` file is retained with the source metadata stored as FLAC Vorbis comments. The temporary `.audio` input and `.json` sidecar are removed.
- After successful transcription, the recognized text is added to the FLAC's native `comment` field by losslessly remuxing the FLAC (the audio is not re-encoded). If conversion fails, the original `.audio` and `.json` are retained; successful transcription is added to the JSON as `transcribed`.

New files are created with owner-only read/write permissions where supported. Recordings are **not automatically rotated or deleted**. Monitor disk use and manually remove FLAC files you no longer need. If FFmpeg cannot decode an input, the original `.audio` and `.json` are retained and STT proxying continues.

## Privacy

Audio and transcription text are sensitive personal data. This integration stores every request that reaches its STT entity, including recordings whose later upstream transcription fails. When transcription succeeds, the text is also embedded in the FLAC metadata. It also forwards those bytes to the selected upstream engine, which may itself process them remotely. Restrict access to the HA configuration directory, choose a trusted upstream, and delete recordings when they are no longer needed. There is no encryption-at-rest or retention policy built in.

## Validation

The storage helper tests run with Python's standard library:

```sh
python -m unittest discover -s tests -v
```

A Home Assistant runtime/pipeline test is not included in this repository yet.
