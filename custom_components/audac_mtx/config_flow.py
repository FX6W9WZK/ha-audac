"""Config flow for Audac MTX integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_PORT, INPUT_NAMES, MAX_ZONES

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional("zones", default=8): vol.All(int, vol.Range(min=1, max=8)),
        vol.Optional("name", default="Audac MTX"): str,
    }
)


class AudacMTXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            from .mtx_client import MTXClient

            client = MTXClient(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
            )
            try:
                await client.connect()
                await client.get_version()
                await client.disconnect()

                await self.async_set_unique_id(f"audac_mtx_{user_input[CONF_HOST]}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get("name", "Audac MTX"),
                    data=user_input,
                )
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await client.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return AudacMTXOptionsFlow(config_entry)


class AudacMTXOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        zones_count = self._config_entry.data.get("zones", 8)
        current_options = self._config_entry.options

        schema_dict = {}

        for i in range(1, zones_count + 1):
            default_name = current_options.get(f"zone_{i}_name", f"Zone {i}")
            schema_dict[vol.Optional(f"zone_{i}_name", default=default_name)] = str

        for input_id, default_label in INPUT_NAMES.items():
            current_label = current_options.get(f"source_{input_id}_name", default_label)
            schema_dict[vol.Optional(f"source_{input_id}_name", default=current_label)] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
