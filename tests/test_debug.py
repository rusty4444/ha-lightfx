"""Integration tests for HA LightFX config flow."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from custom_components.ha_lightfx.const import DOMAIN
from custom_components.ha_lightfx.config_flow import LightFXConfigFlow, LightFXOptionsFlow


async def _create_mock_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a mock config entry for testing."""
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="HA LightFX",
        data={},
        source="user",
        unique_id="ha_lightfx",
        entry_id="test_entry_id",
        state=ConfigEntryState.NOT_LOADED,
    )
    await hass.config_entries.async_add(entry)
    return entry


@pytest.mark.config_flow
async def test_config_flow_single_instance(hass: HomeAssistant) -> None:
    """Test that config flow enforces single instance."""
    # First create a mock entry to simulate existing instance
    await _create_mock_config_entry(hass)

    # Verify entry is found
    entries = hass.config_entries.async_entries(DOMAIN)
    print(f"DEBUG: Found {len(entries)} entries for domain {DOMAIN}")
    for e in entries:
        print(f"  Entry: {e.entry_id}, domain: {e.domain}")

    flow = LightFXConfigFlow()
    flow.hass = hass

    # Flow should abort because instance exists
    result = await flow.async_step_user(user_input=None)
    print(f"DEBUG: Result type: {result['type']}")
    print(f"DEBUG: Result: {result}")

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"