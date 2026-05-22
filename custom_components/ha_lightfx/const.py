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

# Default effect config (0-100 range matches service schema)
DEFAULT_BRIGHTNESS = 50
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
SERVICE_CREATE_PROFILE = "create_profile"
SERVICE_DELETE_PROFILE = "delete_profile"
SERVICE_LIST_PROFILES = "list_profiles"
SERVICE_CREATE_GROUP = "create_group"
SERVICE_DELETE_GROUP = "delete_group"
SERVICE_LIST_GROUPS = "list_groups"
SERVICE_PREVIEW_EFFECT = "preview_effect"
SERVICE_START_SEQUENCE = "start_sequence"
SERVICE_START_LAYOUT_GROUP = "start_layout_group"

# Events
EVENT_EFFECT_STARTED = "ha_lightfx_effect_started"
EVENT_EFFECT_STOPPED = "ha_lightfx_effect_stopped"
