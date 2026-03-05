"""Audac MTX integration for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, CARD_URL_PATH, CARD_URL_VERSIONED, CARD_VERSION, CARD_FILENAME, CONF_MODEL, MODEL_MTX48, MODEL_MTX88, MODEL_ZONES
from .coordinator import AudacMTXCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {"loaded": False})
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    if config_entry.version < 2:
        _LOGGER.info("Migrating Audac MTX config entry from version %s to 2", config_entry.version)
        new_data = {**config_entry.data}
        if CONF_MODEL not in new_data:
            zones = new_data.get("zones", 8)
            new_data[CONF_MODEL] = MODEL_MTX48 if zones <= 4 else MODEL_MTX88
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {"loaded": False})

    if not hass.data[DOMAIN].get("loaded"):
        await _register_card(hass)
        hass.data[DOMAIN]["loaded"] = True

    coordinator = AudacMTXCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        entry.add_update_listener(_async_update_options)
    )
    entry.async_on_unload(coordinator.async_shutdown)  # called automatically on unload

    return True


async def _register_card(hass: HomeAssistant) -> None:
    www_dir = Path(__file__).parent / "www"
    if not www_dir.is_dir():
        _LOGGER.warning("Audac MTX www directory not found at %s", www_dir)
        return

    # Register static path (unversioned, the file itself)
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_URL_PATH,
                str(www_dir / CARD_FILENAME),
                cache_headers=False,
            )
        ]
    )

    # Load as early frontend resource using versioned URL (cache-busting)
    try:
        from homeassistant.components.frontend import add_extra_js_url
        add_extra_js_url(hass, CARD_URL_VERSIONED)
        _LOGGER.debug("Registered Audac MTX card via add_extra_js_url: %s", CARD_URL_VERSIONED)
    except Exception as err:
        _LOGGER.debug("add_extra_js_url not available: %s", err)

    # Also register / update as Lovelace resource with versioned URL
    try:
        if hass.data.get("lovelace_resources"):
            from homeassistant.components.lovelace.resources import ResourceStorageCollection
            resources: ResourceStorageCollection = hass.data["lovelace_resources"]
            existing = [
                r for r in resources.async_items()
                if r.get("url", "").startswith(CARD_URL_PATH)
            ]
            if not existing:
                await resources.async_create_item(
                    {"res_type": "module", "url": CARD_URL_VERSIONED}
                )
                _LOGGER.info("Registered Audac MTX card as Lovelace resource: %s", CARD_URL_VERSIONED)
            else:
                # Update URL if version has changed
                for item in existing:
                    if item.get("url") != CARD_URL_VERSIONED:
                        await resources.async_update_item(
                            item["id"],
                            {"res_type": "module", "url": CARD_URL_VERSIONED},
                        )
                        _LOGGER.info(
                            "Updated Audac MTX card resource to %s", CARD_URL_VERSIONED
                        )
    except Exception as err:
        _LOGGER.debug("Could not register/update Lovelace resource: %s", err)


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # coordinator.async_shutdown() is already registered via async_on_unload
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
