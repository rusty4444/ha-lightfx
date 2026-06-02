"""
Core effect engine for HA LightFX.

Generates per-light RGB+transition states for each effect tick.
All effects operate on a virtual 2D grid where each light has (x, y) coordinates
and an optional zone tag. The engine maps effect output to individual lights.
"""

import asyncio
import colorsys
import logging
import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .const import EVENT_EFFECT_STARTED, EVENT_EFFECT_STOPPED

def _hex_or_rgb(val, default):
    """Convert hex string or None to existing default."""
    if val is None:
        return default
    if isinstance(val, str):
        val = val.lstrip("#")
        if len(val) == 3:
            val = "".join(c * 2 for c in val)
        return tuple(int(val[i:i+2], 16) for i in (0, 2, 4))
    if isinstance(val, (list, tuple)):
        return tuple(int(c) for c in val[:3])
    return default

_LOGGER = logging.getLogger(__name__)


@dataclass
class LightPoint:
    """A light's position, state, and 3D position in a layout."""

    entity_id: str
    x: float  # 0.0 - 100.0
    y: float  # 0.0 - 100.0
    z: float = 0  # optional depth axis (0=front, 100=back)
    zone: str = "other"


@dataclass
class LayoutState:
    """Runtime state for a layout."""

    name: str
    icon: str | None = None
    lights: list[LightPoint] = field(default_factory=list)
    current_effect: str | None = None
    current_params: dict[str, Any] = field(default_factory=dict)
    running: bool = False
    task: asyncio.Task | None = None
    previous_states: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def layout_id(self) -> str:
        return self.name.lower().replace(" ", "_")


class LightFXEngine:
    """Orchestrates light effects across layouts."""

    def __init__(self, hass, call_service: Callable):
        self._hass = hass
        self._call_service = call_service
        self._layouts: dict[str, LayoutState] = {}
        self._profiles: dict[str, dict] = {}
        self._groups: dict[str, list[str]] = {}

    # ── Layout management ──────────────────────────────────────────────

    def create_layout(self, name: str, icon: str | None = None) -> str:
        lid = name.lower().replace(" ", "_")
        if lid in self._layouts:
            raise ValueError(f"Layout '{name}' already exists")
        self._layouts[lid] = LayoutState(name=name, icon=icon)
        return lid

    def remove_layout(self, layout_id: str) -> bool:
        self.stop_effect(layout_id)
        return self._layouts.pop(layout_id, None) is not None

    def get_layout(self, layout_id: str) -> LayoutState | None:
        return self._layouts.get(layout_id)

    def list_layouts(self) -> dict[str, dict]:
        return {
            lid: {
                "name": ls.name,
                "icon": ls.icon,
                "light_count": len(ls.lights),
                "current_effect": ls.current_effect,
                "running": ls.running,
            }
            for lid, ls in self._layouts.items()
        }

    def add_light(self, layout_id: str, entity_id: str, x: float, y: float,
                  z: float = 0, zone: str = "other") -> None:
        ls = self._layouts.get(layout_id)
        if ls is None:
            return
        existing = [l for l in ls.lights if l.entity_id == entity_id]
        if existing:
            existing[0].x = x
            existing[0].y = y
            existing[0].z = z
            existing[0].zone = zone
        else:
            ls.lights.append(LightPoint(entity_id, x, y, z, zone))

    def remove_light(self, layout_id: str, entity_id: str) -> bool:
        ls = self._layouts.get(layout_id)
        if ls is None:
            return False
        before = len(ls.lights)
        ls.lights = [l for l in ls.lights if l.entity_id != entity_id]
        return len(ls.lights) < before

    def to_storage(self) -> dict:
        """Serialise all data for persistent storage."""
        return {
            "version": 2,
            "layouts": {
            lid: {
                "name": ls.name,
                "icon": ls.icon,
                "lights": [
                    {"entity_id": lp.entity_id, "x": lp.x, "y": lp.y, "z": lp.z, "zone": lp.zone}
                    for lp in ls.lights
                ],
            }
            for lid, ls in self._layouts.items()
            },
            "profiles": self._profiles,
            "groups": self._groups,
        }
    def from_storage(self, data: dict) -> None:
        """Restore all data from storage. Skip corrupted entries."""
        if data.get("version") == 2:
            layouts_data = data.get("layouts", {})
            self._profiles = data.get("profiles", {})
            self._groups = data.get("groups", {})
        else:
            layouts_data = data
        for lid, info in layouts_data.items():
            try:
                name = info.get("name", lid)
                icon = info.get("icon")
                ls = LayoutState(name=name, icon=icon)
                for lp in info.get("lights", []):
                    ls.lights.append(
                        LightPoint(
                            lp.get("entity_id", ""),
                            lp.get("x", 0),
                            lp.get("y", 0),
                            lp.get("z", 0),
                            lp.get("zone", "other"),
                        )
                    )
                self._layouts[lid] = ls
            except (KeyError, TypeError) as exc:
                _LOGGER.warning("Skipping corrupted layout '%s' from storage: %s", lid, exc)


    # ── Effect profiles ────────────────────────────────────────────────

    def create_profile(self, name: str, config: dict) -> str:
        """Create a named effect profile."""
        pid = name.lower().replace(" ", "_")
        self._profiles[pid] = {"name": name, "config": config}
        return pid

    def delete_profile(self, profile_id: str) -> bool:
        return self._profiles.pop(profile_id, None) is not None

    def list_profiles(self) -> dict[str, dict]:
        return dict(self._profiles)

    # ── Layout groups ──────────────────────────────────────────────────

    def create_group(self, group_id: str, layout_ids: list[str]) -> None:
        self._groups[group_id] = layout_ids

    def delete_group(self, group_id: str) -> bool:
        return self._groups.pop(group_id, None) is not None

    def list_groups(self) -> dict[str, list[str]]:
        return dict(self._groups)

    def get_group(self, group_id: str) -> list[str] | None:
        return self._groups.get(group_id)

    # ── Preview ────────────────────────────────────────────────────────

    def compute_frame_one(self, layout_id: str, effect: str,
                          params: dict | None = None) -> dict:
        """Compute a single frame without starting an effect loop (preview)."""
        ls = self._get(layout_id)
        if not ls.lights:
            return {}
        base = dict(ls.current_params)
        if params:
            base.update(params)
        base.setdefault("color", (255, 0, 0))
        base.setdefault("color2", (0, 0, 255))
        base.setdefault("brightness", 128)
        base.setdefault("speed", 50)
        base.setdefault("transition", 0.5)
        base.setdefault("direction", "forward")
        saved = ls.current_params
        try:
            ls.current_params = base
            result = self._compute_frame(effect, ls, 0)
            return result
        finally:
            ls.current_params = saved
    # ── Effects ────────────────────────────────────────────────────────

    def start_effect(self, layout_id: str, effect: str,
                     color: tuple | None = None,
                     color2: tuple | None = None,
                     brightness: int = 50, speed: int = 50,
                     transition: float = 0.5,
                     direction: str = "forward",
                     audio_entity_id: str | None = None,
                     effect_per_zone: dict | None = None,
                     sequence: list[dict] | None = None) -> None:
        ls = self._get(layout_id)
        had_previous_snapshot = bool(ls.previous_states)
        self.stop_effect(layout_id, restore=False)

        # Snapshot current states unless this is replacing an already-running
        # effect. Replacement should still restore to the state from before the
        # first effect started, not to an intermediate effect frame.
        if not had_previous_snapshot:
            ls.previous_states = {}
            for lp in ls.lights:
                state = self._hass.states.get(lp.entity_id)
                if state:
                    ls.previous_states[lp.entity_id] = {
                        "state": state.state,
                        "attributes": dict(state.attributes),
                    }

        ls.current_effect = effect
        ls.current_params = {
            "color": color or (255, 0, 0),
            "color2": color2 or (0, 0, 255),
            "brightness": int(brightness * 2.55),  # 0-100 → 0-255
            "speed": speed,
            "transition": transition,
            "direction": direction,
            "audio_entity_id": audio_entity_id,
            "effect_per_zone": effect_per_zone,
            "sequence": sequence,
            "sequence_index": 0,
            "sequence_elapsed": 0.0,
        }
        ls.running = True
        self._hass.bus.async_fire(
            EVENT_EFFECT_STARTED,
            {"layout_id": layout_id, "effect": effect},
        )
        interval = max(0.05, 1.0 - (speed / 100) * 0.95)

        ls.task = asyncio.create_task(
            self._run_effect_loop(layout_id, effect, interval)
        )

    def stop_effect(self, layout_id: str, restore: bool = True) -> None:
        ls = self._layouts.get(layout_id)
        if not ls:
            return
        ls.running = False
        if ls.task and not ls.task.done():
            ls.task.cancel()
            ls.task = None
        if restore and ls.previous_states:
            for entity_id, saved in ls.previous_states.items():
                # Backward-compatible with old in-memory snapshots that stored
                # attributes directly. New snapshots preserve the on/off state.
                if "attributes" in saved or "state" in saved:
                    previous_state = saved.get("state")
                    attrs = saved.get("attributes", {})
                else:
                    previous_state = "on"
                    attrs = saved

                if previous_state == "off":
                    self._hass.async_create_task(
                        self._call_service("light", "turn_off", entity_id=entity_id)
                    )
                    continue

                data = {}
                if "brightness" in attrs:
                    data["brightness"] = attrs["brightness"]
                if "rgb_color" in attrs:
                    data["rgb_color"] = attrs["rgb_color"]
                elif "color_temp" in attrs:
                    data["color_temp"] = attrs["color_temp"]
                if data:
                    self._hass.async_create_task(
                        self._call_service("light", "turn_on",
                                           entity_id=entity_id, **data)
                    )
        if restore:
            ls.previous_states = {}
        if ls.current_effect is not None:
            self._hass.bus.async_fire(
                EVENT_EFFECT_STOPPED,
                {"layout_id": layout_id, "effect": ls.current_effect},
            )
        ls.current_effect = None

    # ── Effect implementations ─────────────────────────────────────────

    async def _run_effect_loop(self, layout_id: str, effect: str,
                                interval: float) -> None:
        """Run a continuous effect loop."""
        ls = self._get(layout_id)
        my_task = asyncio.current_task()
        if not ls.lights:
            ls.running = False
            if ls.task is my_task:
                ls.task = None
            return

        tick = 0
        audio_level = 1.0
        if ls.current_params.get("audio_entity_id"):
            _last_audio = ls.current_params.get("_last_audio_level", 1.0)
            audio_level = _last_audio
            # Snapshot base brightness before any modulation
            ls.current_params["_base_brightness"] = ls.current_params.get("brightness", 128)

        seq_index = 0
        seq_elapsed = 0.0

        try:
            while ls.running:
                # Audio reactivity: read volume from audio entity
                if audio_entity_id := ls.current_params.get("audio_entity_id"):
                    audio_state = self._hass.states.get(audio_entity_id)
                    if audio_state:
                        vol_level = audio_state.attributes.get("volume_level", 1.0)
                        audio_level = max(0.05, vol_level)
                        ls.current_params["_last_audio_level"] = audio_level
                    else:
                        audio_level = 1.0
                    # Modulate brightness by audio level
                    base_brightness = ls.current_params.get("_base_brightness",
                        ls.current_params.get("brightness", 128))
                    ls.current_params["brightness"] = max(1, int(base_brightness * audio_level))

                # Effect sequencer: advance through sequence steps
                if seq := ls.current_params.get("sequence"):
                    if seq_index < len(seq):
                        step = seq[seq_index]
                        dur = step.get("duration_seconds", 10)
                        seq_elapsed += interval
                        if seq_elapsed >= dur:
                            seq_index += 1
                            seq_elapsed = 0.0
                    if seq_index < len(seq):
                        step = seq[seq_index]
                        # Apply step params
                        step_effect = step.get("effect", effect)
                        step_params = ls.current_params.copy()
                        step_params["color"] = _hex_or_rgb(step.get("color", None), step_params["color"])
                        step_params["color2"] = _hex_or_rgb(step.get("color2", None), step_params["color2"])
                        step_params["direction"] = step.get("direction", ls.current_params.get("direction", "forward"))
                        if "speed" in step:
                            step_params["speed"] = step["speed"]
                        if "brightness" in step:
                            # brightness in step is 0-100, convert to 0-255
                            step_params["brightness"] = int(step["brightness"] * 2.55)
                        current_effect_for_frame = step_effect
                        ls.current_params.update(step_params)
                    else:
                        # Sequence complete — stop gracefully
                        ls.running = False
                        continue
                else:
                    current_effect_for_frame = effect

                states = self._compute_frame(current_effect_for_frame, ls, tick)
                calls = []
                for entity_id, sv in states.items():
                    calls.append(
                        self._call_service(
                            "light", "turn_on",
                            entity_id=entity_id,
                            **sv
                        )
                    )
                if calls:
                    await asyncio.gather(*calls)
                tick += 1
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.exception("Effect loop error for layout %s", layout_id)
            ls.running = False
        finally:
            if ls.task is my_task:
                ls.task = None

    def _compute_frame(self, effect: str, ls: LayoutState,
                       tick: int, _depth: int = 0) -> dict[str, dict]:
        """Compute per-light state for this frame tick."""
        p = ls.current_params

        # Zone-aware: dispatch per-zone effects
        effect_per_zone = p.get("effect_per_zone")
        if effect_per_zone and len(effect_per_zone) > 0 and _depth == 0:
            result = {}
            zones_in_layout = set(lp.zone for lp in ls.lights)
            for zone in zones_in_layout:
                zone_effect = effect_per_zone.get(zone, effect)
                zone_lights = [lp for lp in ls.lights if lp.zone == zone]
                if not zone_lights:
                    continue
                # Compute zone frame on a sub-layout context
                sub_result = self._compute_frame(zone_effect, ls, tick, _depth=1)
                # Filter result to only this zone
                for eid, state in sub_result.items():
                    if any(lp.entity_id == eid for lp in zone_lights):
                        result[eid] = state
            return result

        brightness = p["brightness"]
        speed = p["speed"]
        trans = p["transition"]
        c1 = p["color"]
        c2 = p["color2"]

        n = len(ls.lights)
        t_raw = tick * (speed / 25)
        if p.get("direction", "forward") == "reverse":
            t = -t_raw
        elif p.get("direction", "forward") == "bounce":
            period = max(1, speed)
            t = period - abs((int(t_raw) % (2 * period)) - period)
        else:
            t = t_raw

        if effect == "rainbow":
            return {
                lp.entity_id: {
                    "rgb_color": self._hsv_to_rgb(
                        ((lp.x + t * 2) / 100) % 1.0, 1.0, 1.0
                    ),
                    "brightness": brightness,
                    "transition": trans,
                }
                for lp in ls.lights
            }

        elif effect == "chase":
            if n == 0:
                return {}
            idx = int(t) % n
            result = {}
            for i, lp in enumerate(ls.lights):
                if i == idx:
                    result[lp.entity_id] = {
                        "rgb_color": c1,
                        "brightness": brightness,
                        "transition": trans,
                    }
                else:
                    result[lp.entity_id] = {
                        "rgb_color": [0, 0, 0],
                        "brightness": 0,
                        "transition": trans,
                    }
            return result

        elif effect == "breathe":
            phase = (math.sin(t * 0.5) + 1) / 2  # 0 → 1 → 0
            b = int(brightness * phase)
            return {
                lp.entity_id: {
                    "rgb_color": c1,
                    "brightness": max(1, b),
                    "transition": trans,
                }
                for lp in ls.lights
            }

        elif effect == "strobe":
            on = int(t) % 2 == 0
            return {
                lp.entity_id: (
                    {
                        "rgb_color": c1,
                        "brightness": brightness,
                        "transition": 0,
                    }
                    if on
                    else {
                        "rgb_color": [0, 0, 0],
                        "brightness": 0,
                        "transition": 0,
                    }
                )
                for lp in ls.lights
            }

        elif effect == "theater_chase":
            result = {}
            for i, lp in enumerate(ls.lights):
                on = (i + int(t)) % 3 == 0
                result[lp.entity_id] = (
                    {
                        "rgb_color": c1,
                        "brightness": brightness,
                        "transition": trans,
                    }
                    if on
                    else {
                        "rgb_color": c2,
                        "brightness": int(brightness * 0.3),
                        "transition": trans,
                    }
                )
            return result

        elif effect == "fire":
            rng = random.Random(hash((id(ls), tick)) & 0xFFFFFFFF)
            return {
                lp.entity_id: {
                    "rgb_color": (
                        min(255, max(180, int(c1[0] * (0.6 + rng.random() * 0.4)))),
                        min(255, max(60, int(c1[1] * (0.2 + rng.random() * 0.2)))),
                        min(60, int(c1[2] * rng.random() * 0.15)),
                    ),
                    "brightness": int(brightness * (0.7 + rng.random() * 0.3)),
                    "transition": 0.1,
                }
                for lp in ls.lights
            }

        elif effect == "color_cycle":
            hue = ((t * 0.5) / 100) % 1.0
            rgb = self._hsv_to_rgb(hue, 1.0, 1.0)
            return {
                lp.entity_id: {
                    "rgb_color": rgb,
                    "brightness": brightness,
                    "transition": trans,
                }
                for lp in ls.lights
            }

        elif effect == "sparkle":
            rng = random.Random(hash((id(ls), tick)) & 0xFFFFFFFF)
            result = {}
            for lp in ls.lights:
                if rng.random() < 0.15:
                    result[lp.entity_id] = {
                        "rgb_color": c1,
                        "brightness": brightness,
                        "transition": 0,
                    }
                else:
                    result[lp.entity_id] = {
                        "rgb_color": [0, 0, 0],
                        "brightness": 0,
                        "transition": trans,
                    }
            return result

        elif effect == "wave":
            return {
                lp.entity_id: {
                    "rgb_color": self._hsv_to_rgb(
                        ((t + lp.x + lp.y) / 80) % 1.0, 1.0, 1.0
                    ),
                    "brightness": int(
                        brightness
                        * (0.5 + 0.5 * math.sin((lp.x + lp.y + t * 4) / 20))
                    ),
                    "transition": trans,
                }
                for lp in ls.lights
            }

        elif effect == "twinkle":
            seed = hash((id(ls), tick)) & 0xFFFFFFFF
            rng = random.Random(seed)
            result = {}
            for lp in ls.lights:
                on = rng.random() < 0.3
                result[lp.entity_id] = (
                    {
                        "rgb_color": c1,
                        "brightness": brightness,
                        "transition": 0,
                    }
                    if on
                    else {
                        "rgb_color": c2,
                        "brightness": int(brightness * 0.1),
                        "transition": trans,
                    }
                )
            return result

        # fallback
        return {
            lp.entity_id: {"rgb_color": c1, "brightness": brightness, "transition": trans}
            for lp in ls.lights
        }

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> list[int]:
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return [int(r * 255), int(g * 255), int(b * 255)]

    def _get(self, layout_id: str) -> LayoutState:
        ls = self._layouts.get(layout_id)
        if ls is None:
            raise ValueError(f"Layout '{layout_id}' not found")
        return ls
