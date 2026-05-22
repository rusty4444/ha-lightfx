# HA LightFX

**Version 1.0.0** — Virtual WLED-inspired light effects for Home Assistant.

Define room layouts, map lights to positions, and run ambient effects — rainbow, chase, breathe, strobe, theater chase, fire, color cycle, sparkle, wave, twinkle — across ordinary Zigbee, Z-Wave, Wi-Fi, or any HA-compatible lights. No special hardware needed.

![HA LightFX](images/repo-preview.png)

## Features

### Backend Integration

- **`ha_lightfx.create_layout`** — create a named layout (e.g. "Living Room")
- **`ha_lightfx.add_light`** — add a light at a grid position (x, y, zone) with optional 3D depth (z-axis)
- **`ha_lightfx.remove_light`** — remove a light from a layout
- **`ha_lightfx.start_effect`** — run an effect with color, brightness, speed, transition config
- **`ha_lightfx.stop_effect`** — stop and optionally restore lights to previous state
- Layouts persist across HA restarts (via HA storage),

### Extended Services
- **`ha_lightfx.create_profile`** — save an effect preset (name + effect config)
- **`ha_lightfx.list_profiles`** — list saved effect presets
- **`ha_lightfx.create_group`** — group multiple layouts for synchronized effects
- **`ha_lightfx.start_sequence`** — run a timed multi-effect sequence on a layout
- **`ha_lightfx.start_layout_group`** — run the same effect synchronously on all layouts in a group
- **`ha_lightfx.list_layouts`** — list all layouts with status and light counts
- **`ha_lightfx.preview_effect`** — compute a single frame without running the full effect loop (supports return_response)

### 3D Z-Axis Positioning

Every light has a **depth (z)** coordinate (0 = front, 100 = back) in addition to x/y. The engine tracks z for all effects, enabling future 3D spatial effects. The config flow offers z-depth editing, and the z value is available in the WebSocket API and storage.

### 10 Built-in Effects + Zone-aware + Direction + Audio Reactivity

| Effect | Description |
|--------|-------------|
| **Rainbow** | Smooth hue sweep across all lights based on position (respects direction) |
| **Chase** | Single light chases around the room |
| **Breathe** | Slow fade in/out on primary color |
| **Strobe** | Alternating on/off flash |
| **Theater Chase** | Classic alternating two-color chase (Cylon/Knight Rider style) |
| **Fire** | Randomized warm flicker on primary color (seeded for deterministic preview) |
| **Color Cycle** | Global hue transition |
| **Sparkle** | Random twinkling white sparkles against black (seeded for deterministic preview) |
| **Wave** | HSV wave across lights based on position (follows x/y position, not color params) |
| **Twinkle** | Random on/off twinkling between two colors |

### Zone-Aware Effects

Lights can be tagged with a zone (`ceiling`, `wall`, `accent`, `floor`, `other`). Start an effect with `effect_per_zone` to dispatch different effects to different zones simultaneously — e.g. ceiling lights chase while wall lights breathe.

### Direction Control

Effects support three direction modes:
- **forward** — runs from lowest-index light to highest
- **reverse** — runs from highest to lowest
- **bounce** — alternates forward/reverse in a triangle wave

### Audio Reactivity

Pass an `audio_entity_id` (media player) to `start_effect` and the brightness modulates with the media player's `volume_level` — lights pulse to the music.

### Effect Sequencer

The `start_sequence` service runs a timed sequence of different effects on a single layout. Each step specifies an effect, duration, and optional color/brightness/speed overrides.

### Effect Profiles

Save named effect presets via `create_profile` and apply them to any layout with one call. Manage profiles through the visual editor or Developer Tools.

### Layout Groups

Group layouts together with `create_group`, then start/stop effects on all of them simultaneously with `start_layout_group`.

### Preview Mode

`preview_effect` computes a single frame of any effect without starting the loop. Use `return_response: true` to capture the computed per-light state. Perfect for visualisers or pre-flight checks.

### Visual Editor (Config Flow)

The integration provides a full visual editor accessible via **Settings → Devices & Services → HA LightFX → Configure** — no YAML required:
- **Manage Layouts** — create, rename, delete layouts
- **Manage Lights** — add, edit, remove lights with x/y/z position and zone
- **Manage Profiles** — create, delete, and apply effect profiles
- **Manage Groups** — create and delete layout groups

### Lovelace Card

A built-in custom card (`ha-lightfx-card`) provides:
- Layout selector buttons
- 2D grid visualization of lights with zone coloring
- Effect dropdown, dual color pickers, brightness/speed sliders
- Play/Stop controls with state-aware enabling
- Draggable light dots (drag to reposition on the 2D grid)

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
4. Use **Manage Lights → pick your layout → Add Light** to add lights with grid position (x, y, z depth) and zone tag (ceiling/wall/accent/floor/other)
5. Use **Manage Profiles/Groups** for advanced workflows
6. Add the card to a dashboard: **Add Card → Custom: HA LightFX**

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
  z: 10
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
| `list_layouts` | — | Get all layouts and status |
| `add_light` | `layout_id`, `entity_id`, `x` (0-100), `y` (0-100), `z` (0-100, optional), `zone` | Add light to layout |
| `remove_light` | `layout_id`, `entity_id` | Remove light |
| `start_effect` | `layout_id`, `effect`, `color`, `color2`, `brightness`, `speed`, `transition`, `direction`, `audio_entity_id`, `effect_per_zone` | Run effect |
| `stop_effect` | `layout_id`, `restore_previous` | Stop effect |
| `preview_effect` | `layout_id`, `effect`, `params` | Compute single preview frame |
| `create_profile` | `name`, `config` | Save effect profile |
| `delete_profile` | `profile_id` | Delete profile |
| `list_profiles` | — | List all profiles |
| `create_group` | `group_id`, `layout_ids` | Group layouts for sync |
| `delete_group` | `group_id` | Delete group |
| `list_groups` | — | List groups |
| `start_sequence` | `layout_id`, `sequence` (array of steps with `effect`, `duration_seconds`), `brightness` | Run timed effect sequence |
| `start_layout_group` | `group_id`, `effect`, `color`, `color2`, `brightness`, `speed`, `transition`, `direction` | Sync effect on group |

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

### Effect sequence (party mode)

```yaml
alias: "Party Mode Sequence"
trigger:
  - platform: state
    entity_id: binary_sensor.doorbell
    to: "on"
action:
  - service: ha_lightfx.start_sequence
    data:
      layout_id: living_room
      brightness: 80
      sequence:
        - effect: rainbow
          duration_seconds: 30
        - effect: chase
          duration_seconds: 15
          speed: 60
        - effect: strobe
          duration_seconds: 10
          brightness: 100
```

### Audio-reactive fire effect

```yaml
alias: "Party Audio Fire"
trigger:
  - platform: state
    entity_id: binary_sensor.motion_living_room
    to: "on"
action:
  - service: ha_lightfx.start_effect
    data:
      layout_id: living_room
      effect: fire
      color: [255, 100, 0]
      audio_entity_id: media_player.living_room
```

### Layout group sync

```yaml
alias: "Sync Downstairs"
action:
  - service: ha_lightfx.start_layout_group
    data:
      group_id: downstairs
      effect: rainbow
      brightness: 50
```

## Development

```bash
# Integration
custom_components/ha_lightfx/
├── __init__.py          # Entry point, services, WebSocket API
├── manifest.json        # HA manifest
├── config_flow.py       # Config flow (single instance)
├── const.py             # Constants
├── strings.json         # Config flow strings
├── services.yaml        # Service definitions
├── lightfx_engine.py    # Effect engine
└── translations/
    └── en.json          # English translations

# Frontend
www/ha-lightfx-card.js   # Lovelace custom card (LitElement)
```

## License

MIT
