"""STT platform that records audio and proxies it to an existing engine."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
import logging
from pathlib import Path

from homeassistant.components import stt
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_RECORDING_DIRECTORY, CONF_UPSTREAM_ENGINE, DEFAULT_RECORDING_DIRECTORY
from .storage import write_recording

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the recording proxy entity."""
    async_add_entities([STTProxyEntity(entry)])


class STTProxyEntity(SpeechToTextEntity):
    """Capture each request locally, then forward its exact bytes and metadata."""

    _attr_name = "STT Proxy Recorder"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the proxy entity."""
        self._upstream_engine_id = entry.data[CONF_UPSTREAM_ENGINE]
        self._recording_directory = entry.options.get(
            CONF_RECORDING_DIRECTORY, DEFAULT_RECORDING_DIRECTORY
        )
        self._attr_unique_id = entry.entry_id

    def _upstream(self):
        """Return the configured provider, which may be an entity or legacy engine."""
        engine = stt.async_get_speech_to_text_engine(
            self.hass, self._upstream_engine_id
        )
        if engine is None:
            raise HomeAssistantError(
                f"Configured STT engine {self._upstream_engine_id} is unavailable"
            )
        return engine

    @property
    def supported_languages(self) -> list[str]:
        """Expose upstream language support unchanged."""
        try:
            return self._upstream().supported_languages
        except HomeAssistantError:
            return []

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Expose upstream format support unchanged."""
        try:
            return self._upstream().supported_formats
        except HomeAssistantError:
            return []

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Expose upstream codec support unchanged."""
        try:
            return self._upstream().supported_codecs
        except HomeAssistantError:
            return []

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Expose upstream bit-rate support unchanged."""
        try:
            return self._upstream().supported_bit_rates
        except HomeAssistantError:
            return []

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Expose upstream sample-rate support unchanged."""
        try:
            return self._upstream().supported_sample_rates
        except HomeAssistantError:
            return []

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Expose upstream channel support unchanged."""
        try:
            return self._upstream().supported_channels
        except HomeAssistantError:
            return []

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Persist audio before sending it to the configured STT engine."""
        chunks: list[bytes] = []
        async for chunk in stream:
            chunks.append(chunk)
        audio = b"".join(chunks)

        try:
            recording_path = await asyncio.to_thread(
                write_recording,
                Path(self.hass.config.config_dir),
                self._recording_directory,
                audio,
                metadata,
            )
        except (OSError, ValueError) as err:
            _LOGGER.error("Unable to save incoming STT audio: %s", err)
            raise HomeAssistantError("Unable to save STT recording") from err

        engine = self._upstream()
        replay_stream = _replay_chunks(chunks)
        try:
            return await engine.async_process_audio_stream(metadata, replay_stream)
        except Exception as err:
            _LOGGER.exception(
                "Upstream STT engine %s failed; recording retained at %s",
                self._upstream_engine_id,
                recording_path,
            )
            raise HomeAssistantError("Configured upstream STT engine failed") from err


async def _replay_chunks(chunks: list[bytes]) -> AsyncIterable[bytes]:
    """Replay the original chunk boundaries without changing audio bytes."""
    for chunk in chunks:
        yield chunk
