"""
HA LightFX — Virtual WLED-style light effects for any Home Assistant light.

Define room layouts, map lights to virtual positions, and run ambient effects
(rainbow, chase, breathe, strobe, theater_chase, fire, color_cycle, sparkle,
wave, twinkle) with no special hardware required.
"""

import logging
import asyncio
from pathlib import Path
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    SERVICE_CREATE_LAYOUT,
    SERVICE_REMOVE_LAYOUT,
    SERVICE_LIST_LAYOUTS,
    SERVICE_START_EFFECT,
    SERVICE_STOP_EFFECT,
    SERVICE_ADD_LIGHT,
    SERVICE_REMOVE_LIGHT,
    SERVICE_CREATE_PROFILE,
    SERVICE_DELETE_PROFILE,
    SERVICE_LIST_PROFILES,
    SERVICE_CREATE_GROUP,
    SERVICE_DELETE_GROUP,
    SERVICE_LIST_GROUPS,
    SERVICE_PREVIEW_EFFECT,
    SERVICE_START_SEQUENCE,
    SERVICE_START_LAYOUT_GROUP,
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
FRONTEND_URL = "/ha_lightfx/ha-lightfx-card.js"
FRONTEND_PATH = Path(__file__).parent / "www" / "ha-lightfx-card.js"
SERVICE_NAMES = (
    SERVICE_CREATE_LAYOUT,
    SERVICE_REMOVE_LAYOUT,
    SERVICE_LIST_LAYOUTS,
    SERVICE_START_EFFECT,
    SERVICE_STOP_EFFECT,
    SERVICE_ADD_LIGHT,
    SERVICE_REMOVE_LIGHT,
    SERVICE_CREATE_PROFILE,
    SERVICE_DELETE_PROFILE,
    SERVICE_LIST_PROFILES,
    SERVICE_CREATE_GROUP,
    SERVICE_DELETE_GROUP,
    SERVICE_LIST_GROUPS,
    SERVICE_PREVIEW_EFFECT,
    SERVICE_START_SEQUENCE,
    SERVICE_START_LAYOUT_GROUP,
)


def _check_layout(ls, layout_id):
    """Return ls or log a warning when the layout doesn't exist."""
    if ls is None:
        _LOGGER.warning("Layout '%s' not found — service call ignored", layout_id)
    return ls is not None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA LightFX from a config entry."""
    engine = LightFXEngine(hass, hass.services.async_call)

    # Restore persisted layouts
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    if stored:
        engine.from_storage(stored)

    hass.data[DOMAIN] = {"engine": engine, "store": store}

    # Register services
    _register_services(hass, engine)

    # Serve bundled Lovelace card
    await _register_frontend(hass)

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

    remaining_entries = [
        existing
        for existing in hass.config_entries.async_entries(DOMAIN)
        if existing.entry_id != entry.entry_id
    ]
    if not remaining_entries:
        for service_name in SERVICE_NAMES:
            hass.services.async_remove(DOMAIN, service_name)

    hass.data.pop(DOMAIN, None)
    return True


async def _register_frontend(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card from the integration package."""
    if not FRONTEND_PATH.exists():
        _LOGGER.warning("HA LightFX frontend file not found: %s", FRONTEND_PATH)
        return

    try:
        from homeassistant.components.http import StaticPathConfig
    except ImportError:
        hass.http.register_static_path(
            FRONTEND_URL, str(FRONTEND_PATH), cache_headers=False
        )
    else:
        await hass.http.async_register_static_paths([
            StaticPathConfig(FRONTEND_URL, str(FRONTEND_PATH), cache_headers=False),
        ])


def _register_services(hass: HomeAssistant, engine: LightFXEngine) -> None:
    """Register all service calls."""

    async def _save(hass):
        store = hass.data[DOMAIN]["store"]
        await store.async_save(engine.to_storage())

    # ── create_layout ──────────────────────────────────────────────
    async def handle_create_layout(call: ServiceCall) -> dict | None:
        name = call.data[CONF_NAME]
        icon = call.data.get("icon")
        lid = engine.create_layout(name, icon)
        await _save(hass)
        if getattr(call, "return_response", False):
            return {"layout_id": lid}
        return None

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_LAYOUT, handle_create_layout,
        schema=vol.Schema({
            vol.Required(CONF_NAME): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional("icon"): cv.string,
        }),
        supports_response=SupportsResponse.OPTIONAL,
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

    # ── list_layouts ──────────────────────────────────────────────
    async def handle_list_layouts(call: ServiceCall) -> dict:
        return engine.list_layouts()
    hass.services.async_register(
        DOMAIN, SERVICE_LIST_LAYOUTS, handle_list_layouts,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
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
            z=call.data.get("z", 0),
            zone=call.data.get("zone", "other"),
        )
        await _save(hass)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_LIGHT, handle_add_light,
        schema=vol.Schema({
            vol.Required("layout_id"): cv.string,
            vol.Required("entity_id"): cv.entity_id,
            vol.Required("x"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("y"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Optional("z", default=0): vol.All(vol.Coerce(int), vol.Range(0, 100)),
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
        vol.All(
            cv.ensure_list,
            vol.Length(min=3, max=3),
            [vol.All(vol.Coerce(int), vol.Range(0, 255))],
        ),
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
        direction = call.data.get("direction", "forward")
        audio_entity_id = call.data.get("audio_entity_id")
        effect_per_zone = call.data.get("effect_per_zone")

        engine.start_effect(lid, effect, color, color2, brightness, speed, transition,
                            direction=direction, audio_entity_id=audio_entity_id,
                            effect_per_zone=effect_per_zone)

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
            vol.Optional("direction", default="forward"): vol.In(
                ["forward", "reverse", "bounce"]
            ),
            vol.Optional("audio_entity_id"): cv.entity_id,
            vol.Optional("effect_per_zone"): dict,
        }),
    )


    # ── create_profile ─────────────────────────────────────────────
    async def handle_create_profile(call: ServiceCall) -> None:
        engine.create_profile(call.data["name"], call.data.get("config", {}))
        await _save(hass)
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_PROFILE, handle_create_profile,
        schema=vol.Schema({
            vol.Required("name"): cv.string,
            vol.Optional("config", default={}): dict,
        }),
    )

    # ── delete_profile ─────────────────────────────────────────────
    async def handle_delete_profile(call: ServiceCall) -> None:
        engine.delete_profile(call.data["profile_id"])
        await _save(hass)
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_PROFILE, handle_delete_profile,
        schema=vol.Schema({vol.Required("profile_id"): cv.string}),
    )

    # ── list_profiles ──────────────────────────────────────────────
    async def handle_list_profiles(call: ServiceCall) -> dict:
        return engine.list_profiles()
    hass.services.async_register(
        DOMAIN, SERVICE_LIST_PROFILES, handle_list_profiles,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )

    # ── create_group ───────────────────────────────────────────────
    async def handle_create_group(call: ServiceCall) -> None:
        engine.create_group(call.data["group_id"], call.data["layout_ids"])
        await _save(hass)
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_GROUP, handle_create_group,
        schema=vol.Schema({
            vol.Required("group_id"): cv.string,
            vol.Required("layout_ids"): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    # ── delete_group ───────────────────────────────────────────────
    async def handle_delete_group(call: ServiceCall) -> None:
        engine.delete_group(call.data["group_id"])
        await _save(hass)
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_GROUP, handle_delete_group,
        schema=vol.Schema({vol.Required("group_id"): cv.string}),
    )

    # ── list_groups ──────────────────────────────────────────────────
    async def handle_list_groups(call: ServiceCall) -> dict:
        return engine.list_groups()
    hass.services.async_register(
        DOMAIN, SERVICE_LIST_GROUPS, handle_list_groups,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )

    # ── start_sequence ─────────────────────────────────────────────
    async def handle_start_sequence(call: ServiceCall) -> None:
        lid = call.data["layout_id"]
        ls = engine.get_layout(lid)
        if not _check_layout(ls, lid):
            return
        engine.start_effect(
            lid, call.data.get("effect", "rainbow"),
            sequence=call.data.get("sequence", []),
            brightness=call.data.get("brightness", 50),
        )
    hass.services.async_register(
        DOMAIN, SERVICE_START_SEQUENCE, handle_start_sequence,
        schema=vol.Schema({
            vol.Required("layout_id"): cv.string,
            vol.Optional("effect", default="rainbow"): vol.In(EFFECTS),
            vol.Optional("brightness", default=50): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("sequence"): vol.All(cv.ensure_list, [{
                vol.Required("effect"): vol.In(EFFECTS),
                vol.Required("duration_seconds"): vol.All(vol.Coerce(int), vol.Range(1, 3600)),
                vol.Optional("color"): _color_or_none,
                vol.Optional("color2"): _color_or_none,
                vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
                vol.Optional("speed"): vol.All(vol.Coerce(int), vol.Range(1, 100)),
                vol.Optional("direction"): vol.In(["forward", "reverse", "bounce"]),
            }]),
        }),
    )

    # ── start_layout_group ─────────────────────────────────────────
    async def handle_start_layout_group(call: ServiceCall) -> None:
        group_id = call.data["group_id"]
        layout_ids = engine.get_group(group_id)
        if not layout_ids:
            _LOGGER.warning("Layout group '%s' not found", group_id)
            return
        effect = call.data.get("effect", DEFAULT_EFFECT)
        color = _resolve_color(call.data.get("color"))
        color2 = _resolve_color(call.data.get("color2"))
        brightness = call.data.get("brightness", 50)
        speed = call.data.get("speed", DEFAULT_SPEED)
        transition = call.data.get("transition", DEFAULT_TRANSITION)
        direction = call.data.get("direction", "forward")
        for lid in layout_ids:
            try:
                engine.start_effect(lid, effect=effect, color=color, color2=color2,
                                    brightness=brightness, speed=speed,
                                    transition=transition, direction=direction)
            except ValueError:
                _LOGGER.warning(
                    "Skipping missing layout '%s' in layout group '%s'", lid, group_id
                )
    hass.services.async_register(
        DOMAIN, SERVICE_START_LAYOUT_GROUP, handle_start_layout_group,
        schema=vol.Schema({
            vol.Required("group_id"): cv.string,
            vol.Optional("effect", default=DEFAULT_EFFECT): vol.In(EFFECTS),
            vol.Optional("color"): _color_or_none,
            vol.Optional("color2"): _color_or_none,
            vol.Optional("brightness", default=50): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Optional("speed", default=DEFAULT_SPEED): vol.All(vol.Coerce(int), vol.Range(1, 100)),
            vol.Optional("transition", default=DEFAULT_TRANSITION): vol.All(vol.Coerce(float), vol.Range(0.1, 5.0)),
            vol.Optional("direction", default="forward"): vol.In(["forward", "reverse", "bounce"]),
        }),
    )

    # ── preview_effect ─────────────────────────────────────────────
    async def handle_preview_effect(call: ServiceCall) -> dict | None:
        if getattr(call, "return_response", False):
            lid = call.data["layout_id"]
            effect = call.data.get("effect", DEFAULT_EFFECT)
            try:
                return engine.compute_frame_one(lid, effect, call.data.get("params"))
            except ValueError as err:
                _LOGGER.warning("Preview effect failed: %s", err)
                return None
        return None
    hass.services.async_register(
        DOMAIN, SERVICE_PREVIEW_EFFECT, handle_preview_effect,
        schema=vol.Schema({
            vol.Required("layout_id"): cv.string,
            vol.Optional("effect", default=DEFAULT_EFFECT): vol.In(EFFECTS),
            vol.Optional("params"): dict,
        }),
        supports_response=SupportsResponse.OPTIONAL,
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
    if isinstance(color, (list, tuple)) and len(color) >= 3:
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
                    {"entity_id": lp.entity_id, "x": lp.x, "y": lp.y, "z": lp.z, "zone": lp.zone}
                    for lp in (ls.lights if ls else [])
                ],
            }
        connection.send_result(msg["id"], {"layouts": layouts})


    @websocket_api.async_response
    async def ws_preview(hass, connection, msg):
        """Compute a single preview frame for an effect."""
        lid = msg.get("layout_id")
        effect = msg.get("effect", "rainbow")
        try:
            result = engine.compute_frame_one(lid, effect, msg.get("params"))
            connection.send_result(msg["id"], {"states": result})
        except ValueError as e:
            connection.send_error(msg["id"], "not_found", str(e))

    websocket_api.async_register_command(
        hass,
        "ha_lightfx/preview",
        ws_preview,
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {
                vol.Required("type"): "ha_lightfx/preview",
                vol.Required("layout_id"): cv.string,
                vol.Optional("effect", default="rainbow"): vol.In(EFFECTS),
                vol.Optional("params"): dict,
            }
        ),
    )

    @websocket_api.async_response
    async def ws_profiles(hass, connection, msg):
        """Return all profiles."""
        connection.send_result(msg["id"], {"profiles": engine.list_profiles()})

    websocket_api.async_register_command(
        hass,
        "ha_lightfx/profiles",
        ws_profiles,
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {"type": "ha_lightfx/profiles"}
        ),
    )

    @websocket_api.async_response
    async def ws_groups(hass, connection, msg):
        """Return all layout groups."""
        connection.send_result(msg["id"], {"groups": engine.list_groups()})

    websocket_api.async_register_command(
        hass,
        "ha_lightfx/groups",
        ws_groups,
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {"type": "ha_lightfx/groups"}
        ),
    )
    websocket_api.async_register_command(
        hass,
        "ha_lightfx/layouts",
        ws_layouts,
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {"type": "ha_lightfx/layouts"}
        ),
    )
