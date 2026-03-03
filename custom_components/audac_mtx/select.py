"""Select entities for Audac MTX zone source selection."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INPUT_NAMES, CONF_MODEL, MODEL_MTX88, MODEL_ZONES, MODEL_NAMES
from .coordinator import AudacMTXCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_source_names(entry: ConfigEntry) -> dict[int, str]:
    options = entry.options
    result = {}
    for input_id, default_name in INPUT_NAMES.items():
        if options.get(f"source_{input_id}_visible", True):
            result[input_id] = options.get(f"source_{input_id}_name", default_name)
    return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AudacMTXCoordinator = hass.data[DOMAIN][entry.entry_id]
    model = entry.data.get(CONF_MODEL, MODEL_MTX88)
    zones_count = entry.data.get("zones", MODEL_ZONES.get(model, 8))

    entities = []
    for zone in range(1, zones_count + 1):
        if entry.options.get(f"zone_{zone}_visible", True):
            entities.append(AudacMTXSourceSelect(coordinator, zone, entry))
    async_add_entities(entities)


class AudacMTXSourceSelect(CoordinatorEntity[AudacMTXCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:audio-input-rca"

    def __init__(self, coordinator: AudacMTXCoordinator, zone: int, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._zone = zone
        self._entry = entry
        zone_name = entry.options.get(f"zone_{zone}_name", f"Zone {zone}")
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_source"
        self._attr_name = f"{zone_name} Quelle"
        self._source_names = _get_source_names(entry)
        self._attr_options = list(self._source_names.values())
        model = entry.data.get(CONF_MODEL, MODEL_MTX88)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Audac MTX"),
            "manufacturer": "Audac",
            "model": MODEL_NAMES.get(model, "MTX"),
        }

    @property
    def _zone_data(self) -> dict[str, Any]:
        if self.coordinator.data and self._zone in self.coordinator.data:
            return self.coordinator.data[self._zone]
        return {}

    @property
    def current_option(self) -> str | None:
        data = self._zone_data
        if not data:
            return None
        routing = data.get("routing", 0)
        return self._source_names.get(routing, f"Input {routing}")

    async def async_select_option(self, option: str) -> None:
        for input_id, name in self._source_names.items():
            if name == option:
                await self.coordinator.client.set_routing(self._zone, input_id)
                await self.coordinator.async_request_refresh()
                return
