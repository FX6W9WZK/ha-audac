"""Audac MTX integration for Home Assistant."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CARD_URL_PATH, CARD_URL_VERSIONED, CARD_VERSION, CARD_FILENAME, XMP44_CARD_FILENAME, XMP44_CARD_URL_PATH, XMP44_CARD_URL_VERSIONED, CONF_MODEL, MODEL_MTX48, MODEL_MTX88, MODEL_XMP44, MODEL_ZONES, is_xmp_model
from .coordinator import AudacMTXCoordinator
from .xmp44_coordinator import XMP44Coordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS_MTX = [
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BUTTON,
]

PLATFORMS_XMP44 = [
    Platform.MEDIA_PLAYER,
    Platform.BUTTON,
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
        hass.data[DOMAIN]["loaded"] = True  # Set early to prevent race condition
        try:
            await _register_card(hass)
        except RuntimeError as err:
            if "already registered" in str(err):
                _LOGGER.debug("Card path already registered, skipping: %s", err)
            else:
                raise

    model = entry.data.get(CONF_MODEL, "mtx88")

    if is_xmp_model(model):
        coordinator = XMP44Coordinator(hass, entry)
        platforms = PLATFORMS_XMP44
    else:
        coordinator = AudacMTXCoordinator(hass, entry)
        platforms = PLATFORMS_MTX

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    entry.async_on_unload(
        entry.add_update_listener(_async_update_options)
    )
    entry.async_on_unload(coordinator.async_shutdown)

    return True


async def _register_card(hass: HomeAssistant) -> None:
    www_dir = Path(__file__).parent / "www"
    if not www_dir.is_dir():
        _LOGGER.warning("Audac www directory not found at %s", www_dir)
        return

    # Register static paths for both cards
    paths = [
        StaticPathConfig(
            CARD_URL_PATH,
            str(www_dir / CARD_FILENAME),
            cache_headers=False,
        ),
    ]
    if (www_dir / XMP44_CARD_FILENAME).exists():
        paths.append(
            StaticPathConfig(
                XMP44_CARD_URL_PATH,
                str(www_dir / XMP44_CARD_FILENAME),
                cache_headers=False,
            )
        )
    await hass.http.async_register_static_paths(paths)
    _LOGGER.debug("Registered Audac static paths: %s, %s", CARD_URL_PATH, XMP44_CARD_URL_PATH)

    # Register as Lovelace storage resources
    await _register_lovelace_resource(hass, CARD_URL_PATH, CARD_URL_VERSIONED, "MTX")
    if (www_dir / XMP44_CARD_FILENAME).exists():
        await _register_lovelace_resource(hass, XMP44_CARD_URL_PATH, XMP44_CARD_URL_VERSIONED, "XMP44")


async def _register_lovelace_resource(hass: HomeAssistant, url_path: str, url_versioned: str, label: str = "") -> None:
    """Register a card as a Lovelace storage resource."""
    resource_collection = None
    try:
        from homeassistant.components.lovelace.resources import ResourceStorageCollection
        lovelace_data = hass.data.get("lovelace")
        if isinstance(lovelace_data, dict):
            candidate = lovelace_data.get("resources")
            if isinstance(candidate, ResourceStorageCollection):
                resource_collection = candidate

        if resource_collection is None:
            candidate = hass.data.get("lovelace_resources")
            if isinstance(candidate, ResourceStorageCollection):
                resource_collection = candidate

        if resource_collection is None and isinstance(lovelace_data, dict):
            for key, val in lovelace_data.items():
                if isinstance(val, ResourceStorageCollection):
                    resource_collection = val
                    break

    except ImportError:
        pass

    if resource_collection is None:
        if not hass.is_running:
            _up = url_path
            _uv = url_versioned
            _lb = label
            hass.bus.async_listen_once(
                "homeassistant_started",
                lambda _: hass.async_create_task(_register_lovelace_resource(hass, _up, _uv, _lb))
            )
            _LOGGER.debug("Audac %s: Lovelace not ready yet, deferring to homeassistant_started", label)
            return
        _LOGGER.debug(
            "Audac %s: Lovelace resource collection not found — card was likely already added manually or via UI. URL=%s",
            label, url_versioned,
        )
        return

    try:
        existing = [
            r for r in resource_collection.async_items()
            if r.get("url", "").startswith(url_path)
        ]

        if not existing:
            await resource_collection.async_create_item(
                {"res_type": "module", "url": url_versioned}
            )
            _LOGGER.info("Registered Audac %s card as Lovelace resource: %s", label, url_versioned)
        else:
            for item in existing:
                if item.get("url") != url_versioned:
                    await resource_collection.async_update_item(
                        item["id"],
                        {"res_type": "module", "url": url_versioned},
                    )
                    _LOGGER.info("Updated Audac %s card resource to %s", label, url_versioned)
                else:
                    _LOGGER.debug("Audac %s card resource up-to-date: %s", label, url_versioned)
    except Exception as err:
        _LOGGER.warning("Could not register Audac %s Lovelace resource: %s", label, err)


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    model = entry.data.get(CONF_MODEL, "mtx88")
    platforms = PLATFORMS_XMP44 if is_xmp_model(model) else PLATFORMS_MTX
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
