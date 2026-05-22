# HA LightFX

**Virtual WLED-style light effects for any Home Assistant light.**

Define room layouts, map lights to positions, and run ambient effects — rainbow, chase, breathe, strobe, theater chase, fire, color cycle, sparkle, wave, twinkle — across ordinary Zigbee, Z-Wave, Wi-Fi, or any HA-compatible lights. No special hardware needed.

![HA LightFX](images/repo-preview.png)

## Features

### Backend Integration

- **`ha_lightfx.create_layout`** — create a named layout (e.g. "Living Room")
- **`ha_lightfx.add_light`** — add a light at a grid position (x, y, zone)
- **`ha_lightfx.remove_light`** — remove a light from a layout
- **`ha_lightfx.start_effect`** — run an effect with color, brightness, speed, transition config
- **`ha_lightfx.stop_effect`** — stop and optionally restore lights to previous state
- Layouts persist across HA restarts (via HA storage)

### 10 Built-in Effects

| Effect | Description |
|--------|-------------|
| **Rainbow** | Smooth hue sweep across all lights based on position |
| **Chase** | Single light chases around the room |
| **Breathe** | Slow fade in/out on primary color |
| **Strobe** | Alternating on/off flash |
| **Theater Chase** | Classic alternating two-color chase (Cylon/Knight Rider style) |
| **Fire** | Randomized warm flicker on primary color |
| **Color Cycle** | Global hue transition |
| **Sparkle** | Random twinkling white sparkles against black |
| **Wave** | HSV wave across lights based on position |
| **Twinkle** | Random on/off twinkling between two colors |

### Lovelace Card

A built-in custom card (`ha-lightfx-card`) provides:
- Layout selector buttons
- 2D grid visualization of lights with zone coloring
- Effect dropdown, dual color pickers, brightness/speed sliders
- Play/Stop controls with state-aware enabling

![Preview](https://img.shields.io/badge/status-beta-yellow)

## Installation

### HACS (recommended)

1. Open HACS → Integrations → Custom Repositories
2. Add `https://github.com/rusty4444/ha-lightfx` as type **Integration**
3. Click **Download** on HA LightFX
4. Restart Home Assistant
5. Add the card from HACS → Frontend → HA LightFX

### Manual

1. Copy `custom_components/ha_lightfx/` to your HA `config/custom_components/` directory
2. Copy `www/ha-lightfx-card.js` to your HA `config/www/` directory
3. Restart Home Assistant
4. Add resource: `/local/ha-lightfx-card.js` as a **JavaScript Module**

## Setup

1. Go to **Settings → Devices & Services → Add Integration** → search "HA LightFX"
2. Click **Configure** on the HA LightFX entry to open the **visual editor**
3. Use **Manage Layouts → Create Layout** to add your first layout (e.g. "Living Room")
4. Use **Manage Lights → pick your layout → Add Light** to add lights with grid position (x, y) and zone tag (ceiling/wall/accent/floor/other)
5. Add the card to a dashboard: **Add Card → Custom: HA LightFX**

Alternatively, everything is available via services (Developer Tools → Services):

```yaml
# Create a layout
service: ha_lightfx.create_layout
data:
  name: "Living Room"
```

```yaml
# Add a light
service: ha_lightfx.add_light
data:
  layout_id: living_room
  entity_id: light.living_room_ceiling
  x: 50
  y: 30
  zone: ceiling
```

```yaml
# Run an effect
service: ha_lightfx.start_effect
data:
  layout_id: living_room
  effect: rainbow
  brightness: 60
  speed: 40
```

> The visual editor is the recommended way to manage layouts and lights — no YAML knowledge required.

## Dashboard Card Configuration

Add `ha-lightfx-card` as a custom card. No YAML config needed — the card auto-discovers layouts via the HA WebSocket API.

```yaml
type: custom:ha-lightfx-card
```

## Services Reference

| Service | Parameters | Description |
|---------|-----------|-------------|
| `create_layout` | `name` (required), `icon` (optional) | New layout |
| `remove_layout` | `layout_id` | Delete layout |
| `add_light` | `layout_id`, `entity_id`, `x` (0-100), `y` (0-100), `zone` | Add light to layout |
| `remove_light` | `layout_id`, `entity_id` | Remove light |
| `start_effect` | `layout_id`, `effect`, `color`, `color2`, `brightness`, `speed`, `transition` | Run effect |
| `stop_effect` | `layout_id`, `restore_previous` | Stop effect |
| `list_layouts` | — | Get all layouts and status |

## Automation Examples

### Motion-triggered rainbow on arrival

```yaml
alias: "Rainbow on Arrival"
trigger:
  - platform: state
    entity_id: binary_sensor.motion_living_room
    to: "on"
condition:
  - condition: sun
    after: sunset
action:
  - service: ha_lightfx.start_effect
    data:
      layout_id: living_room
      effect: rainbow
      brightness: 40
      speed: 30
  - delay:
      minutes: 5
  - service: ha_lightfx.stop_effect
    data:
      layout_id: living_room
      restore_previous: true
```

### Breathe during sleep mode

```yaml
alias: "Bedtime Breathe"
trigger:
  - platform: time
    at: "22:00:00"
action:
  - service: ha_lightfx.start_effect
    data:
      layout_id: bedroom
      effect: breathe
      color: [255, 50, 50]
      brightness: 20
      speed: 20
```

## Development

```bash
# Integration
custom_components/ha_lightfx/
├── __init__.py          # Entry point, services, WebSocket API
├── manifest.json        # HA manifest
├── config_flow.py       # Config flow (single instance)
├── const.py             # Constants
├── services.yaml        # Service definitions
└── lightfx_engine.py    # Effect engine

# Frontend
www/ha-lightfx-card.js   # Lovelace custom card (LitElement)
```

## License

MIT
