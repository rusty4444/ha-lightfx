"""Pytest configuration and fixtures for HA LightFX tests."""

import sys
from pathlib import Path

# Add custom_components to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.config_entries import ConfigEntry

from custom_components.ha_lightfx.const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from custom_components.ha_lightfx import LightFXEngine

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture(name="lightfx_engine")
async def lightfx_engine_fixture(hass: HomeAssistant) -> LightFXEngine:
    """Create a LightFXEngine instance for testing."""
    # Provide a mock call_service that does nothing
    async def mock_call_service(domain, service, service_data):
        pass

    engine = LightFXEngine(hass, mock_call_service)

    # Initialize with empty storage
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if stored:
        engine.from_storage(stored)

    hass.data[DOMAIN] = {"engine": engine, "store": store}
    return engine


@pytest.fixture(name="setup_integration")
async def setup_integration_fixture(hass: HomeAssistant, lightfx_engine: LightFXEngine) -> LightFXEngine:
    """Set up the integration for tests."""
    # Register services
    from custom_components.ha_lightfx.__init__ import _register_services
    _register_services(hass, lightfx_engine)

    # Register websocket commands
    from custom_components.ha_lightfx.__init__ import _register_websocket_api
    await _register_websocket_api(hass, lightfx_engine)

    return lightfx_engine


@pytest.fixture(name="mock_light_entities")
async def mock_light_entities_fixture(hass: HomeAssistant) -> list[str]:
    """Create mock light entities for testing."""
    entity_ids = [
        "light.light_1",
        "light.light_2",
        "light.light_3",
    ]
    for entity_id in entity_ids:
        hass.states.async_set(entity_id, "off", {"friendly_name": entity_id})
    return entity_ids


@pytest.fixture(name="sample_layout")
async def sample_layout_fixture(lightfx_engine: LightFXEngine, mock_light_entities: list[str]) -> str:
    """Create a sample layout with lights for testing."""
    layout_id = lightfx_engine.create_layout("Test Layout")
    lightfx_engine.add_light(layout_id, mock_light_entities[0], 50, 50, 0, "ceiling")
    lightfx_engine.add_light(layout_id, mock_light_entities[1], 30, 70, 10, "wall")
    return layout_id


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no Home Assistant)")
    config.addinivalue_line("markers", "integration: Integration tests (require Home Assistant)")
    config.addinivalue_line("markers", "config_flow: Config flow tests")