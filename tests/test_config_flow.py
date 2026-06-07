"""Integration tests for HA LightFX config flow."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_lightfx.const import DOMAIN
from custom_components.ha_lightfx.config_flow import LightFXConfigFlow, LightFXOptionsFlow


async def _create_mock_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create a mock config entry for testing."""
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="HA LightFX",
        data={},
        options={},
        source="user",
        unique_id="ha_lightfx",
        entry_id="test_entry_id",
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.config_flow
async def test_config_flow_single_instance(hass: HomeAssistant) -> None:
    """Test that config flow enforces single instance."""
    # First create a mock entry to simulate existing instance
    await _create_mock_config_entry(hass)

    flow = LightFXConfigFlow()
    flow.hass = hass

    # Flow should abort because instance exists
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.config_flow
async def test_config_flow_user_input(hass: HomeAssistant) -> None:
    """Test config flow with user input."""
    flow = LightFXConfigFlow()
    flow.hass = hass

    # First call shows form
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # With user input, should create entry
    result2 = await flow.async_step_user(user_input={})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "HA LightFX"


@pytest.mark.config_flow
async def test_options_flow_with_mock_entry(hass: HomeAssistant) -> None:
    """Test that options flow works with a mock config entry."""
    # Create mock entry
    entry = await _create_mock_config_entry(hass)

    # Need to set up engine data
    from custom_components.ha_lightfx.lightfx_engine import LightFXEngine
    from custom_components.ha_lightfx.const import STORAGE_KEY, STORAGE_VERSION
    from homeassistant.helpers.storage import Store

    async def mock_call_service(domain, service, data):
        pass

    engine = LightFXEngine(hass, mock_call_service)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if stored:
        engine.from_storage(stored)
    hass.data[DOMAIN] = {"engine": engine, "store": store}

    # Options flow should be accessible
    options_flow = LightFXOptionsFlow(entry)
    options_flow.hass = hass

    result = await options_flow.async_step_init()
    # Should show the menu
    assert result["type"] == FlowResultType.MENU
    assert "manage_layouts" in result["menu_options"]


@pytest.mark.config_flow
async def test_options_flow_manage_layouts(hass: HomeAssistant) -> None:
    """Test options flow manage_layouts menu."""
    entry = await _create_mock_config_entry(hass)
    options_flow = LightFXOptionsFlow(entry)
    options_flow.hass = hass

    # Need to set up engine data
    from custom_components.ha_lightfx.lightfx_engine import LightFXEngine
    from custom_components.ha_lightfx.const import STORAGE_KEY, STORAGE_VERSION
    from homeassistant.helpers.storage import Store

    async def mock_call_service(domain, service, data):
        pass

    engine = LightFXEngine(hass, mock_call_service)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if stored:
        engine.from_storage(stored)
    hass.data[DOMAIN] = {"engine": engine, "store": store}

    # Test manage_layouts submenu - initially only create_layout available
    result = await options_flow.async_step_manage_layouts(user_input=None)
    assert result["type"] == FlowResultType.MENU
    assert "create_layout" in result["menu_options"]

    # Test create_layout form
    result2 = await options_flow.async_step_create_layout(user_input=None)
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "create_layout"


@pytest.mark.config_flow
async def test_options_flow_create_layout(hass: HomeAssistant) -> None:
    """Test creating a layout via options flow."""
    entry = await _create_mock_config_entry(hass)
    options_flow = LightFXOptionsFlow(entry)
    options_flow.hass = hass

    # Need to set up engine data
    from custom_components.ha_lightfx.lightfx_engine import LightFXEngine
    from custom_components.ha_lightfx.const import STORAGE_KEY, STORAGE_VERSION
    from homeassistant.helpers.storage import Store

    async def mock_call_service(domain, service, data):
        pass

    engine = LightFXEngine(hass, mock_call_service)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if stored:
        engine.from_storage(stored)
    hass.data[DOMAIN] = {"engine": engine, "store": store}

    # Create a layout
    result = await options_flow.async_step_create_layout(user_input={"name": "Test Layout"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "Test Layout" in result["title"]

    # Verify layout was created in engine
    engine = options_flow._engine()
    layouts = engine.list_layouts()
    assert len(layouts) == 1
    assert "test_layout" in layouts


@pytest.mark.config_flow
async def test_options_flow_manage_lights(hass: HomeAssistant) -> None:
    """Test options flow manage_lights submenu."""
    entry = await _create_mock_config_entry(hass)
    options_flow = LightFXOptionsFlow(entry)
    options_flow.hass = hass

    # Need to set up engine data
    from custom_components.ha_lightfx.lightfx_engine import LightFXEngine
    from custom_components.ha_lightfx.const import STORAGE_KEY, STORAGE_VERSION
    from homeassistant.helpers.storage import Store

    async def mock_call_service(domain, service, data):
        pass

    engine = LightFXEngine(hass, mock_call_service)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if stored:
        engine.from_storage(stored)
    hass.data[DOMAIN] = {"engine": engine, "store": store}

    # First create a layout
    options_flow._context_storage = {}
    await options_flow.async_step_create_layout(user_input={"name": "Test Layout"})

    # Now test manage_lights - should have layout picker
    result = await options_flow.async_step_manage_lights(user_input=None)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manage_lights"

    # Select layout and test list_lights
    result2 = await options_flow.async_step_manage_lights(user_input={"layout_id": "test_layout"})
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "list_lights"


@pytest.mark.unit
def test_config_flow_constants() -> None:
    """Test config flow constants are defined."""
    assert LightFXConfigFlow.VERSION == 1
    from custom_components.ha_lightfx.const import DOMAIN as CONST_DOMAIN
    assert DOMAIN == CONST_DOMAIN


@pytest.mark.unit
def test_layout_schema() -> None:
    """Test _LAYOUT_SCHEMA factory."""
    from custom_components.ha_lightfx.config_flow import _LAYOUT_SCHEMA

    schema = _LAYOUT_SCHEMA()
    # Test empty name is rejected
    with pytest.raises(Exception):
        schema({"name": ""})

    # Test valid name
    result = schema({"name": "Test Layout"})
    assert result["name"] == "Test Layout"


@pytest.mark.unit
def test_light_schema() -> None:
    """Test _LIGHT_SCHEMA factory."""
    from custom_components.ha_lightfx.config_flow import _LIGHT_SCHEMA

    schema = _LIGHT_SCHEMA()
    # Just verify schema can be constructed
    assert schema is not None