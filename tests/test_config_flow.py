"""Tests for the Audac MTX config and options flows."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.audac_mtx.const import (
    CONF_MODEL,
    DOMAIN,
    MODEL_MTX48,
    MODEL_MTX88,
    MODEL_XMP44,
)

MTX_USER_INPUT = {
    CONF_HOST: "192.168.1.50",
    CONF_PORT: 5001,
    CONF_MODEL: MODEL_MTX88,
    "name": "Wohnzimmer MTX",
}


async def test_user_flow_mtx_success(
    hass: HomeAssistant, mock_mtx_client, mock_setup_entry
) -> None:
    """A successful MTX88 setup creates an entry with the zone count."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MTX_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Wohnzimmer MTX"
    assert result["data"][CONF_HOST] == "192.168.1.50"
    assert result["data"][CONF_MODEL] == MODEL_MTX88
    assert result["data"]["zones"] == 8
    assert result["result"].unique_id == "audac_mtx_192.168.1.50"
    mock_mtx_client.assert_awaited_once()
    mock_setup_entry.assert_awaited_once()


async def test_user_flow_mtx48_zone_count(
    hass: HomeAssistant, mock_mtx_client, mock_setup_entry
) -> None:
    """An MTX48 entry stores four zones."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MTX_USER_INPUT, CONF_MODEL: MODEL_MTX48},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["zones"] == 4


async def test_user_flow_xmp44_success(
    hass: HomeAssistant, mock_xmp_client, mock_setup_entry
) -> None:
    """A successful XMP44 setup creates an entry with the slot count."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MTX_USER_INPUT, CONF_MODEL: MODEL_XMP44},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["slots"] == 4
    mock_xmp_client.assert_awaited_once()


async def test_user_flow_cannot_connect_then_recover(
    hass: HomeAssistant, mock_mtx_client, mock_setup_entry
) -> None:
    """A failed connection shows an error; the flow can then succeed."""
    mock_mtx_client.side_effect = ConnectionError("no route")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MTX_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_mtx_client.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MTX_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_host_aborts(
    hass: HomeAssistant, mock_mtx_client, mock_setup_entry
) -> None:
    """The same host cannot be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="audac_mtx_192.168.1.50",
        data=MTX_USER_INPUT,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MTX_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_mtx_client.assert_not_awaited()


async def _setup_entry(hass: HomeAssistant, data: dict, options: dict | None = None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"audac_mtx_{data[CONF_HOST]}",
        data=data,
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _mtx_sections(**overrides):
    """Full nested options payload for an MTX88 (all sections present)."""
    payload = {f"zone_{i}": {} for i in range(1, 9)}
    payload["sources"] = {}
    for key, value in overrides.items():
        payload[key] = value
    return payload


def _xmp_sections(**overrides):
    payload = {f"slot_{i}": {} for i in range(1, 5)}
    for key, value in overrides.items():
        payload[key] = value
    return payload


def _section_fields(result, section_key):
    """Return the inner field names of a section in the rendered schema."""
    for key, value in result["data_schema"].schema.items():
        if str(key) == section_key:
            return {str(k): k for k in value.schema.schema}
    raise AssertionError(f"section {section_key} not in schema")


async def test_options_flow_mtx(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """MTX options accept zone names and store stripped flat values."""
    entry = await _setup_entry(hass, {**MTX_USER_INPUT, "zones": 8})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _mtx_sections(
            zone_1={"name": "  Küche  "},
            zone_2={"visible": False},
            sources={"source_1_name": "Mikro Bühne"},
        ),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["zone_1_name"] == "Küche"
    assert entry.options["zone_2_visible"] is False
    assert entry.options["source_1_name"] == "Mikro Bühne"
    # Defaults of untouched sections are stored flat as well
    assert entry.options["zone_3_name"] == "Zone 3"


async def test_options_flow_empty_name_then_recover(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """A blank name is rejected with empty_name, then accepted once fixed."""
    entry = await _setup_entry(hass, {**MTX_USER_INPUT, "zones": 8})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _mtx_sections(zone_1={"name": "   "})
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "empty_name"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _mtx_sections(zone_1={"name": "Bad"})
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["zone_1_name"] == "Bad"


async def test_options_flow_mtx_link_migration_defaults(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Legacy zone_x_links / zone_x_linked_to options prefill the dropdown."""
    entry = await _setup_entry(
        hass,
        {**MTX_USER_INPUT, "zones": 8},
        options={
            "zone_1_links": [2],
            "zone_2_linked_to": 3,
            "zone_3_link": 4,
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    expected = {"zone_1": "2", "zone_2": "3", "zone_3": "4"}
    for section_key, link_default in expected.items():
        fields = _section_fields(result, section_key)
        assert fields["link"].default() == link_default


async def test_options_flow_xmp44_with_fmp40_triggers(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """XMP44 options render trigger fields inside the FMP40 slot section."""
    entry = await _setup_entry(
        hass,
        {**MTX_USER_INPUT, CONF_MODEL: MODEL_XMP44, "slots": 4},
        options={
            "slot_1_module": 6,
            "slot_1_triggers": 2,
            "slot_1_trigger_2_stop": True,
            "slot_2_module": "8",
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    slot1 = _section_fields(result, "slot_1")
    assert "trigger_1_name" in slot1
    assert "trigger_2_name" in slot1
    assert slot1["trigger_2_stop"].default() is True
    assert "trigger_1_name" not in _section_fields(result, "slot_2")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _xmp_sections(
            slot_1={
                "module": "6",
                "name": "Durchsagen",
                "triggers": 2,
                "trigger_1_name": "Gong",
                "trigger_1_stop": True,
            },
        ),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["slot_1_trigger_1_name"] == "Gong"
    assert entry.options["slot_1_trigger_1_stop"] is True
    assert entry.options["slot_1_name"] == "Durchsagen"


async def test_options_flow_xmp44_new_triggers_second_step(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Raising the trigger count asks for the new names in a second step."""
    entry = await _setup_entry(
        hass,
        {**MTX_USER_INPUT, CONF_MODEL: MODEL_XMP44, "slots": 4},
        options={
            "slot_1_module": "6",
            "slot_1_triggers": 1,
            "slot_1_trigger_1_name": "Feierabend",
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _xmp_sections(
            slot_1={
                "module": "6",
                "triggers": 3,
                "trigger_1_name": "Feierabend",
            },
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "triggers"
    field_names = [str(key) for key in result["data_schema"].schema]
    assert field_names == [
        "slot_1_trigger_2_name",
        "slot_1_trigger_2_stop",
        "slot_1_trigger_3_name",
        "slot_1_trigger_3_stop",
    ]

    # Empty names are rejected in the second step as well
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot_1_trigger_2_name": "  "}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "empty_name"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "slot_1_trigger_2_name": "Evakuierung",
            "slot_1_trigger_2_stop": True,
            "slot_1_trigger_3_name": "Pausenzeichen",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["slot_1_triggers"] == 3
    assert entry.options["slot_1_trigger_1_name"] == "Feierabend"
    assert entry.options["slot_1_trigger_2_name"] == "Evakuierung"
    assert entry.options["slot_1_trigger_2_stop"] is True
    assert entry.options["slot_1_trigger_3_name"] == "Pausenzeichen"
    assert entry.options["slot_1_trigger_3_stop"] is False


async def test_options_flow_xmp44_invalid_trigger_count(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """A corrupt trigger count falls back to no trigger name fields."""
    entry = await _setup_entry(
        hass,
        {**MTX_USER_INPUT, CONF_MODEL: MODEL_XMP44, "slots": 4},
        options={"slot_1_module": "6", "slot_1_triggers": "kaputt"},
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    for key, value in result["data_schema"].schema.items():
        if str(key) == "slot_1":
            assert "trigger_1_name" not in {str(k) for k in value.schema.schema}
            break
    else:
        raise AssertionError("slot_1 section missing")


def test_options_flatten_and_validate_helpers() -> None:
    """Direct coverage of the flatten/validate edge cases."""
    from custom_components.audac_mtx.config_flow import (
        _flatten_options_input,
        _validate_option_names,
    )

    # Non-section scalar values pass through unchanged
    flat = _flatten_options_input({"zone_1": {"name": "A"}, "stray": 7})
    assert flat == {"zone_1_name": "A", "stray": 7}

    # Corrupt trigger counts coerce to 0
    validated, errors = _validate_option_names({"slot_1_triggers": "kaputt"})
    assert errors == {}
    assert validated["slot_1_triggers"] == 0
