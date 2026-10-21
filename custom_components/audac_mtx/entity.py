"""Base entity for Audac MTX integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_MODEL, MODEL_MTX88, MODEL_NAMES
from .coordinator import AudacMTXCoordinator


class AudacMTXBaseEntity(CoordinatorEntity[AudacMTXCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AudacMTXCoordinator, zone: int, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._zone = zone
        self._entry = entry
        model = entry.data.get(CONF_MODEL, MODEL_MTX88)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", "Audac MTX"),
            manufacturer="Audac",
            model=MODEL_NAMES.get(model, "MTX"),
        )

    @property
    def _zone_data(self) -> dict[str, Any]:
        if self.coordinator.data and self._zone in self.coordinator.data:
            return self.coordinator.data[self._zone]
        return {}

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self._zone_data)
