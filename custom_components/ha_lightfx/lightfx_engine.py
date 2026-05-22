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

_LOGGER = logging.getLogger(__name__)


@dataclass
class LightPoint:
    """A light's position and state in a layout."""

    entity_id: str
    x: float  # 0.0 - 100.0
    y: float  # 0.0 - 100.0
    zone: str = "other"


@dataclass
class LayoutState:
    """Runtime state for a layout."""

    name: str
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

    # ── Layout management ──────────────────────────────────────────────

    def create_layout(self, name: str, icon: str | None = None) -> str:
        lid = name.lower().replace(" ", "_")
        if lid in self._layouts:
            raise ValueError(f"Layout '{name}' already exists")
        self._layouts[lid] = LayoutState(name=name)
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
                "light_count": len(ls.lights),
                "current_effect": ls.current_effect,
                "running": ls.running,
            }
            for lid, ls in self._layouts.items()
        }

    def add_light(self, layout_id: str, entity_id: str, x: float, y: float,
                  zone: str = "other") -> None:
        ls = self._get(layout_id)
        existing = [l for l in ls.lights if l.entity_id == entity_id]
        if existing:
            existing[0].x = x
            existing[0].y = y
            existing[0].zone = zone
        else:
            ls.lights.append(LightPoint(entity_id, x, y, zone))

    def remove_light(self, layout_id: str, entity_id: str) -> bool:
        ls = self._get(layout_id)
        before = len(ls.lights)
        ls.lights = [l for l in ls.lights if l.entity_id != entity_id]
        return len(ls.lights) < before

    def to_storage(self) -> dict:
        """Serialise layouts for persistent storage."""
        return {
            lid: {
                "name": ls.name,
                "lights": [
                    {"entity_id": lp.entity_id, "x": lp.x, "y": lp.y, "zone": lp.zone}
                    for lp in ls.lights
                ],
            }
            for lid, ls in self._layouts.items()
        }

    def from_storage(self, data: dict) -> None:
        """Restore layouts from storage. Skip corrupted entries."""
        for lid, info in data.items():
            try:
                name = info.get("name", lid)
                ls = LayoutState(name=name)
                for lp in info.get("lights", []):
                    ls.lights.append(
                        LightPoint(
                            lp.get("entity_id", ""),
                            lp.get("x", 0),
                            lp.get("y", 0),
                            lp.get("zone", "other"),
                        )
                    )
                self._layouts[lid] = ls
            except (KeyError, TypeError) as exc:
                _LOGGER.warning("Skipping corrupted layout '%s' from storage: %s", lid, exc)

    # ── Effects ────────────────────────────────────────────────────────

    def start_effect(self, layout_id: str, effect: str,
                     color: tuple | None = None,
                     color2: tuple | None = None,
                     brightness: int = 50, speed: int = 50,
                     transition: float = 0.5) -> None:
        ls = self._get(layout_id)
        self.stop_effect(layout_id)

        # Snapshot current states
        ls.previous_states = {}
        for lp in ls.lights:
            state = self._hass.states.get(lp.entity_id)
            if state:
                ls.previous_states[lp.entity_id] = dict(state.attributes)

        ls.current_effect = effect
        ls.current_params = {
            "color": color or (255, 0, 0),
            "color2": color2 or (0, 0, 255),
            "brightness": int(brightness * 2.55),  # 0-100 → 0-255
            "speed": speed,
            "transition": transition,
        }
        ls.running = True
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
            for entity_id, attrs in ls.previous_states.items():
                data = {}
                if "brightness" in attrs:
                    data["brightness"] = attrs["brightness"]
                if "rgb_color" in attrs:
                    data["rgb_color"] = attrs["rgb_color"]
                if "color_temp" in attrs:
                    data["color_temp"] = attrs["color_temp"]
                if data:
                    self._hass.async_create_task(
                        self._call_service("light", "turn_on",
                                           entity_id=entity_id, **data)
                    )
        ls.previous_states = {}
        ls.current_effect = None

    # ── Effect implementations ─────────────────────────────────────────

    async def _run_effect_loop(self, layout_id: str, effect: str,
                                interval: float) -> None:
        """Run a continuous effect loop."""
        ls = self._get(layout_id)
        if not ls.lights:
            return

        tick = 0
        try:
            while ls.running:
                states = self._compute_frame(effect, ls, tick)
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
            ls.task = None

    def _compute_frame(self, effect: str, ls: LayoutState,
                       tick: int) -> dict[str, dict]:
        """Compute per-light state for this frame tick."""
        p = ls.current_params
        brightness = p["brightness"]
        speed = p["speed"]
        trans = p["transition"]
        c1 = p["color"]
        c2 = p["color2"]

        n = len(ls.lights)
        t = tick * (speed / 25)  # phase accumulator

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
            return {
                lp.entity_id: {
                    "rgb_color": (
                        min(255, int(c1[0] * (0.6 + random.random() * 0.4))),
                        min(255, int(c1[1] * (0.2 + random.random() * 0.2))),
                        min(255, int(c1[2] * (0.0 + random.random() * 0.1))),
                    ),
                    "brightness": int(brightness * (0.7 + random.random() * 0.3)),
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
            result = {}
            for lp in ls.lights:
                if random.random() < 0.15:
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
