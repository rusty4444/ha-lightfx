"""Unit tests for HA LightFX engine and core functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ha_lightfx import LightFXEngine
from custom_components.ha_lightfx.const import EFFECTS


@pytest.mark.unit
def test_create_layout() -> None:
    """Test creating a layout."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    layout_id = engine.create_layout("Test Layout")
    assert layout_id == "test_layout"

    layouts = engine.list_layouts()
    assert "test_layout" in layouts
    assert layouts["test_layout"]["name"] == "Test Layout"


@pytest.mark.unit
def test_create_layout_duplicate_raises() -> None:
    """Test that creating a duplicate layout raises ValueError."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    engine.create_layout("Test Layout")
    with pytest.raises(ValueError, match="already exists"):
        engine.create_layout("Test Layout")


@pytest.mark.unit
def test_remove_layout() -> None:
    """Test removing a layout."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    layout_id = engine.create_layout("Test Layout")
    result = engine.remove_layout(layout_id)
    assert result is True
    assert engine.get_layout(layout_id) is None


@pytest.mark.unit
def test_add_light() -> None:
    """Test adding a light to a layout."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    layout_id = engine.create_layout("Test Layout")
    engine.add_light(layout_id, "light.test_1", 50, 50, 10, "ceiling")

    layout = engine.get_layout(layout_id)
    assert len(layout.lights) == 1
    assert layout.lights[0].entity_id == "light.test_1"
    assert layout.lights[0].x == 50
    assert layout.lights[0].y == 50
    assert layout.lights[0].z == 10
    assert layout.lights[0].zone == "ceiling"


@pytest.mark.unit
def test_add_light_updates_existing() -> None:
    """Test that adding the same light updates its position."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    layout_id = engine.create_layout("Test Layout")
    engine.add_light(layout_id, "light.test_1", 10, 20)
    engine.add_light(layout_id, "light.test_1", 30, 40)

    layout = engine.get_layout(layout_id)
    assert len(layout.lights) == 1
    assert layout.lights[0].x == 30
    assert layout.lights[0].y == 40


@pytest.mark.unit
def test_remove_light() -> None:
    """Test removing a light from a layout."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    layout_id = engine.create_layout("Test Layout")
    engine.add_light(layout_id, "light.test_1", 50, 50)
    result = engine.remove_light(layout_id, "light.test_1")

    assert result is True
    layout = engine.get_layout(layout_id)
    assert len(layout.lights) == 0


@pytest.mark.unit
def test_remove_nonexistent_light_returns_false() -> None:
    """Test that removing a non-existent light returns False."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    layout_id = engine.create_layout("Test Layout")
    result = engine.remove_light(layout_id, "light.nonexistent")
    assert result is False


@pytest.mark.unit
def test_create_profile() -> None:
    """Test creating an effect profile."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    profile_id = engine.create_profile("Test Profile", {"effect": "rainbow", "speed": 50})
    assert profile_id == "test_profile"

    profiles = engine.list_profiles()
    assert "test_profile" in profiles
    assert profiles["test_profile"]["name"] == "Test Profile"
    assert profiles["test_profile"]["config"]["effect"] == "rainbow"


@pytest.mark.unit
def test_delete_profile() -> None:
    """Test deleting an effect profile."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    engine.create_profile("Test Profile", {"effect": "rainbow"})
    result = engine.delete_profile("test_profile")
    assert result is True

    profiles = engine.list_profiles()
    assert "test_profile" not in profiles


@pytest.mark.unit
def test_create_group() -> None:
    """Test creating a layout group."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    engine.create_group("test_group", ["layout_1", "layout_2"])

    groups = engine.list_groups()
    assert "test_group" in groups
    assert set(groups["test_group"]) == {"layout_1", "layout_2"}


@pytest.mark.unit
def test_delete_group() -> None:
    """Test deleting a layout group."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    engine.create_group("test_group", ["layout_1"])
    result = engine.delete_group("test_group")
    assert result is True

    groups = engine.list_groups()
    assert "test_group" not in groups


@pytest.mark.unit
def test_to_storage_and_from_storage() -> None:
    """Test serializing and deserializing engine state."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    # Create data
    layout_id = engine.create_layout("Test Layout")
    engine.add_light(layout_id, "light.test_1", 10, 20, 5, "wall")
    engine.create_profile("Test Profile", {"effect": "chase", "speed": 75})
    engine.create_group("test_group", ["layout_1"])

    # Serialize
    data = engine.to_storage()

    assert data["version"] == 2
    assert "test_layout" in data["layouts"]
    assert "test_profile" in data["profiles"]
    assert "test_group" in data["groups"]
    assert data["layouts"]["test_layout"]["name"] == "Test Layout"

    # Deserialize into new engine
    engine2 = LightFXEngine(hass, MagicMock())
    engine2.from_storage(data)

    assert "test_layout" in engine2.list_layouts()
    assert engine2.get_layout("test_layout").lights[0].entity_id == "light.test_1"
    assert engine2.list_profiles()["test_profile"]["config"]["effect"] == "chase"
    assert engine2.list_groups()["test_group"] == ["layout_1"]


@pytest.mark.unit
def test_from_storage_version_1_migration() -> None:
    """Test loading version 1 storage format."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    # Version 1 format (no version key)
    data = {
        "test_layout": {
            "name": "Test Layout",
            "lights": [{"entity_id": "light.1", "x": 10, "y": 20}],
        }
    }

    engine.from_storage(data)

    assert "test_layout" in engine.list_layouts()
    assert len(engine.get_layout("test_layout").lights) == 1


@pytest.mark.unit
def test_from_storage_corrupted_layout_skipped() -> None:
    """Test that corrupted layouts are skipped with a warning."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    data = {
        "version": 2,
        "layouts": {
            "good_layout": {"name": "Good", "lights": [{"entity_id": "light.1"}]},
            "bad_layout": {"lights": [{"entity_id": "light.2"}, "not_a_dict"]},
        },
    }

    # Should not raise, just skip bad entry
    engine.from_storage(data)

    assert "good_layout" in engine.list_layouts()
    assert "bad_layout" not in engine.list_layouts()


@pytest.mark.unit
def test_stop_effect_restores_rgbw_rgbww_and_white_attributes() -> None:
    """Restore colour attributes used by RGBW/RGBWW/white-capable lights."""
    hass = MagicMock()
    call_service = MagicMock()
    engine = LightFXEngine(hass, call_service)
    layout_id = engine.create_layout("Kitchen")
    engine.add_light(layout_id, "light.rgbw", 10, 20)
    layout = engine.get_layout(layout_id)
    assert layout is not None
    layout.running = True
    layout.current_effect = "rainbow"
    layout.previous_states = {
        "light.rgbw": {
            "state": "on",
            "attributes": {
                "brightness": 123,
                "rgbw_color": (1, 2, 3, 4),
                "rgbww_color": (5, 6, 7, 8, 9),
                "white": 42,
                "color_mode": "rgbw",
                "supported_color_modes": ["rgbw"],
            },
        }
    }

    engine.stop_effect(layout_id, restore=True)

    hass.async_create_task.assert_called_once()
    coro = hass.async_create_task.call_args.args[0]
    coro.close()
    call_service.assert_called_once_with(
        "light",
        "turn_on",
        {
            "entity_id": "light.rgbw",
            "brightness": 123,
            "rgbw_color": (1, 2, 3, 4),
            "rgbww_color": (5, 6, 7, 8, 9),
            "white": 42,
        },
    )
    assert layout.previous_states == {}


@pytest.mark.unit
def test_compute_frame_rainbow() -> None:
    """Test rainbow effect frame computation."""
    hass = MagicMock()
    engine = LightFXEngine(hass, MagicMock())

    layout_id = engine.create_layout("Test Layout")
    engine.add_light(layout_id, "light.1", 0, 0)
    engine.add_light(layout_id, "light.2", 50, 50)

    ls = engine._get(layout_id)
    ls.current_params = {
        "color": (255, 0, 0),
        "color2": (0, 0, 255),
        "brightness": 128,
        "speed": 50,
        "transition": 0.5,
        "direction": "forward",
    }

    frame = engine._compute_frame("rainbow", ls, 0)

    assert "light.1" in frame
    assert "light.2" in frame
    assert "rgb_color" in frame["light.1"]
    assert "brightness" in frame["light.1"]
    assert "transition" in frame["light.1"]


@pytest.mark.unit
def test_all_effects_in_const() -> None:
    """Test that EFFECTS list matches implemented effects."""
    # Ensure no effect is missing from the list
    implemented = {
        "rainbow", "chase", "breathe", "strobe", "theater_chase",
        "fire", "color_cycle", "sparkle", "wave", "twinkle",
    }
    assert set(EFFECTS) == implemented


@pytest.mark.unit
async def test_start_stop_effect_state() -> None:
    """Test that start/stop effect updates layout state."""
    hass = MagicMock()
    call_service = AsyncMock()
    engine = LightFXEngine(hass, call_service)

    layout_id = engine.create_layout("Test Layout")
    engine.add_light(layout_id, "light.1", 50, 50)

    # Start effect
    engine.start_effect(layout_id, "rainbow", {"speed": 50})

    ls = engine._get(layout_id)
    assert ls.running is True
    assert ls.current_effect == "rainbow"

    # Stop effect
    engine.stop_effect(layout_id)

    assert ls.running is False
    assert ls.current_effect is None