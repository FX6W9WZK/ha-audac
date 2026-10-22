"""Config flow for Audac MTX integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.data_entry_flow import section
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    CONF_MODEL,
    MODEL_MTX48,
    MODEL_MTX88,
    MODEL_XMP44,
    MODEL_ZONES,
    MODEL_SLOTS,
    INPUT_NAMES,
    is_mtx_model,
    is_xmp_model,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_MODEL, default=MODEL_MTX88): vol.In(
            {
                MODEL_MTX48: "MTX48 (4 Zonen)",
                MODEL_MTX88: "MTX88 (8 Zonen)",
                MODEL_XMP44: "XMP44 (4 Slots)",
            }
        ),
        vol.Optional("name", default="Audac MTX"): str,
    }
)


class AudacMTXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            model = user_input.get(CONF_MODEL, MODEL_MTX88)

            if is_xmp_model(model):
                from .xmp44_client import XMP44Client
                user_input["slots"] = MODEL_SLOTS[model]
                client = XMP44Client(
                    host=user_input[CONF_HOST],
                    port=user_input.get(CONF_PORT, DEFAULT_PORT),
                )
            else:
                from .mtx_client import MTXClient
                user_input["zones"] = MODEL_ZONES[model]
                client = MTXClient(
                    host=user_input[CONF_HOST],
                    port=user_input.get(CONF_PORT, DEFAULT_PORT),
                )

            await self.async_set_unique_id(f"audac_mtx_{user_input[CONF_HOST]}")
            self._abort_if_unique_id_configured()

            try:
                await client.connect()

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
        return AudacMTXOptionsFlow()


def _flatten_options_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten section dicts back into the flat option keys used in storage."""
    flat: dict[str, Any] = {}
    for key, value in user_input.items():
        if isinstance(value, dict):
            if key == "sources":
                flat.update(value)
            else:
                for sub_key, sub_value in value.items():
                    flat[f"{key}_{sub_key}"] = sub_value
        else:
            flat[key] = value
    return flat


def _validate_option_names(flat: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Strip strings, coerce trigger counts, reject empty names."""
    validated: dict[str, Any] = {}
    for key, value in flat.items():
        if isinstance(value, str):
            value = value.strip()
            if key.endswith("_name") and not value:
                return validated, {"base": "empty_name"}
        if key.endswith("_triggers"):
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = 0
        validated[key] = value
    return validated, {}


class AudacMTXOptionsFlow(config_entries.OptionsFlowWithReload):
    def __init__(self) -> None:
        self._pending: dict[str, Any] = {}
        self._new_triggers: list[tuple[int, int]] = []

    def _slots_count(self) -> int:
        model = self.config_entry.data.get(CONF_MODEL, MODEL_MTX88)
        return self.config_entry.data.get("slots", MODEL_SLOTS.get(model, 4))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            flat = _flatten_options_input(user_input)
            validated, errors = _validate_option_names(flat)

            if not errors:
                # Freshly added FMP40 triggers get their name fields in a
                # dedicated second step instead of requiring a reopen.
                self._new_triggers = [
                    (slot, trigger)
                    for slot in range(1, self._slots_count() + 1)
                    if validated.get(f"slot_{slot}_module") == "6"
                    for trigger in range(1, validated.get(f"slot_{slot}_triggers", 0) + 1)
                    if f"slot_{slot}_trigger_{trigger}_name" not in validated
                ]
                if self._new_triggers:
                    self._pending = validated
                    return await self.async_step_triggers()
                return self.async_create_entry(title="", data=validated)

        return await self._show_options_form(errors)

    async def async_step_triggers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Name the triggers that were just added in the first step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            validated, errors = _validate_option_names(user_input)
            if not errors:
                self._pending.update(validated)
                return self.async_create_entry(title="", data=self._pending)

        schema_dict: dict = {}
        for slot, trigger in self._new_triggers:
            schema_dict[
                vol.Optional(f"slot_{slot}_trigger_{trigger}_name", default=f"Trigger {trigger}")
            ] = str
            schema_dict[
                vol.Optional(f"slot_{slot}_trigger_{trigger}_stop", default=False)
            ] = bool

        return self.async_show_form(
            step_id="triggers",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def _show_options_form(
        self,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        model = self.config_entry.data.get(CONF_MODEL, MODEL_MTX88)
        current_options = self.config_entry.options

        schema_dict: dict = {}

        if is_xmp_model(model):
            # XMP44: one section per slot with module, name, visibility and
            # (for FMP40) trigger configuration.
            slots_count = self._slots_count()

            module_options = [
                selector.SelectOptionDict(value="0", label="Kein Modul"),
                selector.SelectOptionDict(value="1", label="DMP40 (DAB/DAB+ & FM Tuner)"),
                selector.SelectOptionDict(value="2", label="TMP40 (FM Tuner)"),
                selector.SelectOptionDict(value="3", label="MMP40 (Media Player/Recorder)"),
                selector.SelectOptionDict(value="4", label="IMP40 (Internet Radio)"),
                selector.SelectOptionDict(value="6", label="FMP40 (Voice File)"),
                selector.SelectOptionDict(value="8", label="BMP40 (Bluetooth)"),
                selector.SelectOptionDict(value="9", label="NMP40 (Network Player)"),
            ]

            for i in range(1, slots_count + 1):
                default_module = current_options.get(f"slot_{i}_module", "0")
                if isinstance(default_module, int):
                    default_module = str(default_module)

                slot_schema: dict = {}
                slot_schema[vol.Optional("module", default=default_module)] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=module_options,
                        multiple=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
                slot_schema[vol.Optional("name", default=current_options.get(f"slot_{i}_name", f"Slot {i}"))] = str
                slot_schema[vol.Optional("visible", default=current_options.get(f"slot_{i}_visible", True))] = bool

                # FMP40-specific: trigger count, names and per-trigger stop button
                if default_module == "6":
                    default_triggers = current_options.get(f"slot_{i}_triggers", 0)
                    slot_schema[vol.Optional("triggers", default=default_triggers)] = selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=50, step=1, mode=selector.NumberSelectorMode.BOX,
                        )
                    )
                    try:
                        saved_triggers = int(current_options.get(f"slot_{i}_triggers", 0))
                    except (ValueError, TypeError):
                        saved_triggers = 0
                    for t in range(1, saved_triggers + 1):
                        slot_schema[
                            vol.Optional(f"trigger_{t}_name", default=current_options.get(f"slot_{i}_trigger_{t}_name", f"Trigger {t}"))
                        ] = str
                        slot_schema[
                            vol.Optional(f"trigger_{t}_stop", default=current_options.get(f"slot_{i}_trigger_{t}_stop", False))
                        ] = bool

                schema_dict[vol.Required(f"slot_{i}")] = section(
                    vol.Schema(slot_schema),
                    {"collapsed": default_module == "0"},
                )
        else:
            # MTX: one section per zone plus a sources section.
            zones_count = MODEL_ZONES.get(model, 8)

            for i in range(1, zones_count + 1):
                old_links = current_options.get(f"zone_{i}_links")
                if isinstance(old_links, list) and len(old_links) > 0:
                    migration_default = str(old_links[0])
                else:
                    old_linked = current_options.get(f"zone_{i}_linked_to", 0)
                    migration_default = str(old_linked) if old_linked and old_linked != 0 else "0"
                default_link = current_options.get(f"zone_{i}_link", migration_default)
                if isinstance(default_link, int):
                    default_link = str(default_link)

                coupling_options = [
                    selector.SelectOptionDict(value="0", label="Keine Kopplung"),
                ] + [
                    selector.SelectOptionDict(
                        value=str(j),
                        label=current_options.get(f"zone_{j}_name", f"Zone {j}"),
                    )
                    for j in range(1, zones_count + 1) if j != i
                ]

                zone_schema: dict = {
                    vol.Optional("name", default=current_options.get(f"zone_{i}_name", f"Zone {i}")): str,
                    vol.Optional("visible", default=current_options.get(f"zone_{i}_visible", True)): bool,
                    vol.Optional("link", default=default_link): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=coupling_options,
                            multiple=False,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
                schema_dict[vol.Required(f"zone_{i}")] = section(
                    vol.Schema(zone_schema),
                    {"collapsed": True},
                )

            source_schema: dict = {}
            for input_id, default_label in INPUT_NAMES.items():
                source_schema[
                    vol.Optional(f"source_{input_id}_name", default=current_options.get(f"source_{input_id}_name", default_label))
                ] = str
                default_visible = input_id != 0
                default_visible = current_options.get(f"source_{input_id}_visible", default_visible)
                source_schema[vol.Optional(f"source_{input_id}_visible", default=default_visible)] = bool
            schema_dict[vol.Required("sources")] = section(
                vol.Schema(source_schema),
                {"collapsed": True},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors or {},
        )
