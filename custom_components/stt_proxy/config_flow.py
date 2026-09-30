"""Config and options flows for STT Proxy Recorder."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import stt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_RECORDING_DIRECTORY,
    CONF_UPSTREAM_ENGINE,
    DEFAULT_RECORDING_DIRECTORY,
    DOMAIN,
)


def _available_engines(hass: HomeAssistant) -> list[str]:
    """Return configured STT entity IDs and legacy provider IDs."""
    component = hass.data.get(stt.DATA_COMPONENT)
    entity_ids = (
        [
            entity.entity_id
            for entity in component.entities
            if entity.platform is None or entity.platform.platform_name != DOMAIN
        ]
        if component
        else []
    )
    legacy_providers = hass.data.get(stt.DATA_PROVIDERS, {})
    return sorted([*entity_ids, *legacy_providers])


def _engine_name(hass: HomeAssistant, engine_id: str) -> str:
    """Return the display name for an entity or legacy provider, if available."""
    state = hass.states.get(engine_id)
    if state and (name := state.attributes.get("friendly_name")):
        return str(name)

    component = hass.data.get(stt.DATA_COMPONENT)
    if component:
        entity = component.get_entity(engine_id)
        if entity and entity.name:
            return entity.name

    provider = hass.data.get(stt.DATA_PROVIDERS, {}).get(engine_id)
    if provider and provider.name:
        return str(provider.name)
    return engine_id


def _engine_selector(hass: HomeAssistant) -> selector.SelectSelector:
    """Build a selector with currently configured STT engines."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(
                    value=engine_id,
                    label=f"{_engine_name(hass, engine_id)} ({engine_id})",
                )
                for engine_id in _available_engines(hass)
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


class STTProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a recording proxy for an existing STT engine."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Choose the upstream speech-to-text engine."""
        if user_input is not None:
            engine_id = user_input[CONF_UPSTREAM_ENGINE]
            if engine_id not in _available_engines(self.hass):
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._schema(),
                    errors={"base": "engine_not_found"},
                )
            await self.async_set_unique_id(engine_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Recorder for {engine_id}", data=user_input
            )

        if not _available_engines(self.hass):
            return self.async_abort(reason="no_stt_engines")
        return self.async_show_form(step_id="user", data_schema=self._schema())

    def _schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_UPSTREAM_ENGINE): _engine_selector(self.hass),
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> STTProxyOptionsFlow:
        """Return the options flow."""
        return STTProxyOptionsFlow()


class STTProxyOptionsFlow(config_entries.OptionsFlowWithReload):
    """Configure the local recording directory."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Set a relative recording directory under the HA config directory."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RECORDING_DIRECTORY,
                        default=self.config_entry.options.get(
                            CONF_RECORDING_DIRECTORY, DEFAULT_RECORDING_DIRECTORY
                        ),
                    ): str,
                }
            ),
        )
