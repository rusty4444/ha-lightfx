"""Constants for HA LightFX integration."""

DOMAIN = "ha_lightfx"
DOMAIN_TITLE = "HA LightFX"

# Config flow keys
CONF_LAYOUTS = "layouts"
CONF_NAME = "name"

# Storage keys
STORAGE_KEY = "ha_lightfx.layouts"
STORAGE_VERSION = 1

# Effect names (must match frontend)
EFFECTS = [
    "rainbow",
    "chase",
    "breathe",
    "strobe",
    "theater_chase",
    "fire",
    "color_cycle",
    "sparkle",
    "wave",
    "twinkle",
]

# Default effect config
DEFAULT_BRIGHTNESS = 128
DEFAULT_SPEED = 50
DEFAULT_COLOR = [255, 255, 255]
DEFAULT_EFFECT = "rainbow"
DEFAULT_TRANSITION = 0.5

# Service names
SERVICE_CREATE_LAYOUT = "create_layout"
SERVICE_REMOVE_LAYOUT = "remove_layout"
SERVICE_START_EFFECT = "start_effect"
SERVICE_STOP_EFFECT = "stop_effect"
SERVICE_ADD_LIGHT = "add_light"
SERVICE_REMOVE_LIGHT = "remove_light"

# Events
EVENT_EFFECT_STARTED = "ha_lightfx_effect_started"
EVENT_EFFECT_STOPPED = "ha_lightfx_effect_stopped"
