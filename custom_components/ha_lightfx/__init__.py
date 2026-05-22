"""
HA LightFX — Virtual WLED-style light effects for any Home Assistant light.

Define room layouts, map lights to virtual positions, and run ambient effects
(rainbow, chase, breathe, strobe, theater_chase, fire, color_cycle, sparkle,
wave, twinkle) with no special hardware required.
"""

import logging
import asyncio
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_CREATE_LAYOUT,
    SERVICE_REMOVE_LAYOUT,
    SERVICE_START_EFFECT,
    SERVICE_STOP_EFFECT,
    SERVICE_ADD_LIGHT,
    SERVICE_REMOVE_LIGHT,
    CONF_NAME,
    STORAGE_KEY,
    STORAGE_VERSION,
    EFFECTS,
    DEFAULT_BRIGHTNESS,
    DEFAULT_EFFECT,
    DEFAULT_SPEED,
    DEFAULT_TRANSITION,
)
from .lightfx_engine import LightFXEngine

_LOGGER = logging.getLogger(__name__)

PLATFORMS = []


def _check_layout(ls, layout_id):
    """Return ls or log a warning when the layout doesn't exist."""
    if ls is None:
        _LOGGER.warning("Layout '%s' not found — service call ignored", layout_id)
    return ls is not None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA LightFX from a config entry."""
    engine = LightFXEngine(hass, hass.services.async_call)

    # Restore persisted layouts
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if stored:
        engine.from_storage(stored)

    hass.data[DOMAIN] = {"engine": engine, "store": store}

    # Register services
    _register_services(hass, engine)

    # Register WebSocket API
    await _register_websocket_api(hass, engine)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HA LightFX."""
    engine: LightFXEngine = hass.data[DOMAIN]["engine"]
    # Cancel all running effect tasks before unload
    pending = []
    for lid, ls in engine._layouts.items():
        if ls.task and not ls.task.done():
            ls.task.cancel()
            pending.append(ls.task)
        ls.running = False
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    hass.data.pop(DOMAIN, None)
    return True


def _register_services(hass: HomeAssistant, engine: LightFXEngine) -> None:
    """Register all service calls."""

    async def _save(hass):
        store = hass.data[DOMAIN]["store"]
        await store.async_save(engine.to_storage())

    # ── create_layout ──────────────────────────────────────────────
    async def handle_create_layout(call: ServiceCall) -> None:
        name = call.data[CONF_NAME]
        lid = engine.create_layout(name)
        await _save(hass)

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_LAYOUT, handle_create_layout,
        schema=vol.Schema({vol.Required(CONF_NAME): cv.string,
                           vol.Optional("icon"): cv.string}),
    )

    # ── remove_layout ──────────────────────────────────────────────
    async def handle_remove_layout(call: ServiceCall) -> None:
        lid = call.data["layout_id"]
        engine.remove_layout(lid)
        await _save(hass)

    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_LAYOUT, handle_remove_layout,
        schema=vol.Schema({vol.Required("layout_id"): cv.string}),
    )

    # ── add_light ──────────────────────────────────────────────────
    async def handle_add_light(call: ServiceCall) -> None:
        lid = call.data["layout_id"]
        ls = engine.get_layout(lid)
        if not _check_layout(ls, lid):
            return
        engine.add_light(
            lid,
            call.data["entity_id"],
            call.data["x"],
            call.data["y"],
            call.data.get("zone", "other"),
        )
        await _save(hass)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_LIGHT, handle_add_light,
        schema=vol.Schema({
            vol.Required("layout_id"): cv.string,
            vol.Required("entity_id"): cv.entity_id,
            vol.Required("x"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("y"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Optional("zone", default="other"): vol.In(
                ["ceiling", "wall", "accent", "floor", "other"]
            ),
        }),
    )

    # ── remove_light ───────────────────────────────────────────────
    async def handle_remove_light(call: ServiceCall) -> None:
        lid = call.data["layout_id"]
        ls = engine.get_layout(lid)
        if not _check_layout(ls, lid):
            return
        engine.remove_light(lid, call.data["entity_id"])
        await _save(hass)

    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_LIGHT, handle_remove_light,
        schema=vol.Schema({
            vol.Required("layout_id"): cv.string,
            vol.Required("entity_id"): cv.entity_id,
        }),
    )

    # ── start_effect ──────────────────────────────────────────────
    _color_or_none = vol.Any(
        cv.color_hex,
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 255))]),
        None,
    )

    async def handle_start_effect(call: ServiceCall) -> None:
        lid = call.data["layout_id"]
        ls = engine.get_layout(lid)
        if not _check_layout(ls, lid):
            return
        effect = call.data.get("effect", DEFAULT_EFFECT)
        color = _resolve_color(call.data.get("color"))
        color2 = _resolve_color(call.data.get("color2"))
        brightness = call.data.get("brightness", 50)
        speed = call.data.get("speed", DEFAULT_SPEED)
        transition = call.data.get("transition", DEFAULT_TRANSITION)

        engine.start_effect(lid, effect, color, color2, brightness, speed, transition)

    hass.services.async_register(
        DOMAIN, SERVICE_START_EFFECT, handle_start_effect,
        schema=vol.Schema({
            vol.Required("layout_id"): cv.string,
            vol.Optional("effect", default=DEFAULT_EFFECT): vol.In(EFFECTS),
            vol.Optional("color"): _color_or_none,
            vol.Optional("color2"): _color_or_none,
            vol.Optional("brightness", default=50): vol.All(
                vol.Coerce(int), vol.Range(0, 100)
            ),
            vol.Optional("speed", default=DEFAULT_SPEED): vol.All(
                vol.Coerce(int), vol.Range(1, 100)
            ),
            vol.Optional("transition", default=DEFAULT_TRANSITION): vol.All(
                vol.Coerce(float), vol.Range(0.1, 5.0)
            ),
        }),
    )

    # ── stop_effect ────────────────────────────────────────────────
    async def handle_stop_effect(call: ServiceCall) -> None:
        lid = call.data["layout_id"]
        ls = engine.get_layout(lid)
        if not _check_layout(ls, lid):
            return
        restore = call.data.get("restore_previous", True)
        engine.stop_effect(lid, restore=restore)

    hass.services.async_register(
        DOMAIN, SERVICE_STOP_EFFECT, handle_stop_effect,
        schema=vol.Schema({
            vol.Required("layout_id"): cv.string,
            vol.Optional("restore_previous", default=True): cv.boolean,
        }),
    )


def _resolve_color(color):
    """Convert hex string or list to (R,G,B) tuple."""
    if color is None:
        return None
    if isinstance(color, str):
        color = color.lstrip("#")
        if len(color) == 3:
            color = "".join(c * 2 for c in color)
        return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
    if isinstance(color, (list, tuple)):
        return tuple(int(c) for c in color[:3])
    return None


async def _register_websocket_api(hass, engine):
    """Register WebSocket commands for the frontend card."""
    from homeassistant.components import websocket_api

    @websocket_api.async_response
    async def ws_layouts(hass, connection, msg):
        """Return all layouts with light data."""
        raw = engine.list_layouts()
        layouts = {}
        for lid, info in raw.items():
            ls = engine.get_layout(lid)
            layouts[lid] = {
                **info,
                "lights": [
                    {"entity_id": lp.entity_id, "x": lp.x, "y": lp.y, "zone": lp.zone}
                    for lp in (ls.lights if ls else [])
                ],
            }
        connection.send_result(msg["id"], {"layouts": layouts})

    websocket_api.async_register_command(
        hass,
        "ha_lightfx/layouts",
        ws_layouts,
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {"type": "ha_lightfx/layouts"}
        ),
    )
