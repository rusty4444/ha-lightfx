/**
 * HA LightFX — Lovelace Custom Card
 *
 * Displays a 2D layout of lights and provides effect controls
 * (start/stop effects with color, brightness, speed).
 *
 * Requires ha_lightfx integration to be installed and configured.
 */
import { LitElement, html, css } from "lit";
import { classMap } from "lit/directives/class-map.js";

const EFFECTS = [
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
];

const EFFECT_LABELS = {
  rainbow: "Rainbow",
  chase: "Chase",
  breathe: "Breathe",
  strobe: "Strobe",
  theater_chase: "Theater",
  fire: "Fire",
  color_cycle: "Color Cycle",
  sparkle: "Sparkle",
  wave: "Wave",
  twinkle: "Twinkle",
};

const ZONE_COLORS = {
  ceiling: "#4fc3f7",
  wall: "#81c784",
  accent: "#ffb74d",
  floor: "#a1887f",
  other: "#ce93d8",
};

class HAFXLayoutCard extends LitElement {
  static get properties() {
    return {
      _hass: { state: true },
      config: { type: Object },
      _layouts: { state: true },
      _selectedLayout: { state: true },
      _selectedEffect: { state: true },
      _color1: { state: true },
      _color2: { state: true },
      _brightness: { state: true },
      _speed: { state: true },
      _editMode: { state: true },
      _infoMsg: { state: true },
    };
  }

  constructor() {
    super();
    this.config = {};
    this._layouts = {};
    this._selectedLayout = null;
    this._selectedEffect = "rainbow";
    this._color1 = "#FF0000";
    this._color2 = "#0000FF";
    this._brightness = 50;
    this._speed = 50;
    this._editMode = false;
    this._infoMsg = "";
    this._lastConfigHash = "";
  }

  set hass(hass) {
    this._hass = hass;
  }

  updated(changedProps) {
    super.updated(changedProps);
    // Only refresh from WS when config first arrives or on first load
    if (changedProps.has("config") && this.config && this.config !== {}) {
      this._refreshLayouts();
    }
    if (!this._hass || this._layouts === null) {
      this._refreshLayouts();
    }
  }

  async _refreshLayouts() {
    try {
      const result = await this._hass.callWS({
        type: "ha_lightfx/layouts",
      });
      this._layouts = result.layouts || {};
    } catch (err) {
      console.warn("HA LightFX: failed to fetch layouts", err);
      this._layouts = {};
    }
  }

  _friendlyName(entityId) {
    if (this._hass && this._hass.states[entityId]) {
      const name = this._hass.states[entityId].attributes.friendly_name;
      if (name) return name;
    }
    return entityId.split(".").pop().replace(/_/g, " ");
  }

  async _callService(service, data = {}) {
    if (!this._hass) return;
    try {
      await this._hass.callService("ha_lightfx", service, data);
    } catch (err) {
      console.error("HA LightFX: service call failed", service, err);
      this._infoMsg = `⚠ Error: ${err.message || err}`;
      this.requestUpdate();
    }
  }

  _selectLayout(lid) {
    this._selectedLayout = lid;
    this._infoMsg = "";
  }

  _startEffect() {
    if (!this._selectedLayout) return;
    const hexToRgb = (hex) => {
      hex = hex.replace("#", "");
      if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
      return [parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16)];
    };

    const data = {
      layout_id: this._selectedLayout,
      effect: this._selectedEffect,
      brightness: this._brightness,
      speed: this._speed,
      transition: 0.5,
    };

    if (this._color1) data.color = hexToRgb(this._color1);
    if (this._color2) data.color2 = hexToRgb(this._color2);

    this._callService("start_effect", data);
  }

  _stopEffect() {
    if (!this._selectedLayout) return;
    const layout = this._layouts[this._selectedLayout];
    if (!layout || !layout.running) return;
    if (!confirm("Stop the running effect? Lights will restore to their previous state.")) return;
    this._callService("stop_effect", {
      layout_id: this._selectedLayout,
      restore_previous: true,
    });
  }

  _renderGrid() {
    const layout = this._layouts[this._selectedLayout];
    if (!layout || !layout.lights || layout.lights.length === 0) {
      return html`<div class="empty-grid">No lights in this layout. Use the integration services to add lights.</div>`;
    }

    const lights = layout.lights;

    return html`
      <div class="grid-container">
        <svg viewBox="0 0 100 100" class="layout-svg">
          <!-- Grid background -->
          <rect x="0" y="0" width="100" height="100" fill="none" stroke="var(--secondary-text-color)" stroke-width="0.3" opacity="0.3" />

          <!-- Light dots -->
          ${lights.map((lp) => {
            const color = ZONE_COLORS[lp.zone] || ZONE_COLORS.other;
            const state = this._hass ? this._hass.states[lp.entity_id] : null;
            const isOn = state && state.state === "on";
            return html`
              <g>
                <circle
                  cx="${lp.x}"
                  cy="${lp.y}"
                  r="${isOn ? 3.5 : 2.5}"
                  fill="${color}"
                  opacity="${isOn ? 1 : 0.4}"
                  class="light-dot"
                />
                ${isOn
                  ? html`<circle
                      cx="${lp.x}"
                      cy="${lp.y}"
                      r="5"
                      fill="${color}"
                      opacity="0.3"
                      class="light-glow"
                    />`
                  : ""}
                <text
                  x="${lp.x}"
                  y="${lp.y + 5}"
                  text-anchor="middle"
                  font-size="3"
                  fill="var(--primary-text-color)"
                >
                  ${this._friendlyName(lp.entity_id)}
                </text>
              </g>
            `;
          })}
        </svg>
      </div>
    `;
  }

  _renderControls() {
    const layout = this._layouts[this._selectedLayout];
    if (!layout) return "";

    const running = layout.current_effect != null && layout.running;

    return html`
      <div class="controls">
        ${this._infoMsg ? html`<div class="info-msg">${this._infoMsg}</div>` : ""}

        <div class="control-row">
          <label>Effect</label>
          <select
            @change="${(e) => (this._selectedEffect = e.target.value)}"
            .value="${this._selectedEffect}"
            ?disabled="${running}"
          >
            ${EFFECTS.map(
              (e) => html`<option value="${e}">${EFFECT_LABELS[e]}</option>`
            )}
          </select>
        </div>

        <div class="control-row">
          <label>Color</label>
          <input
            type="color"
            .value="${this._color1}"
            @change="${(e) => (this._color1 = e.target.value)}"
            ?disabled="${running}"
          />
          <input
            type="color"
            .value="${this._color2}"
            @change="${(e) => (this._color2 = e.target.value)}"
            ?disabled="${running}"
          />
        </div>

        <div class="control-row">
          <label>Brightness ${this._brightness}%</label>
          <input
            type="range"
            min="1"
            max="100"
            .value="${this._brightness}"
            @input="${(e) => (this._brightness = parseInt(e.target.value))}"
          />
        </div>

        <div class="control-row">
          <label>Speed ${this._speed}%</label>
          <input
            type="range"
            min="1"
            max="100"
            .value="${this._speed}"
            @input="${(e) => (this._speed = parseInt(e.target.value))}"
          />
        </div>

        <div class="button-row">
          <button
            class="btn-play"
            @click="${this._startEffect}"
            ?disabled="${running}"
          >
            ▶ Play
          </button>
          <button class="btn-stop" @click="${this._stopEffect}" ?disabled="${!running}">
            ⏹ Stop
          </button>
        </div>
      </div>
    `;
  }

  _renderLayoutList() {
    const lids = Object.keys(this._layouts);
    if (lids.length === 0) {
      return html`<div class="no-layouts">
        No layouts configured. Create one via Developer Tools → Services:
        <code>ha_lightfx.create_layout</code>
      </div>`;
    }

    return html`
      <div class="layout-list">
        ${lids.map(
          (lid) => html`
            <button
              class="layout-btn ${classMap({ active: lid === this._selectedLayout })}"
              @click="${() => this._selectLayout(lid)}"
            >
              ${this._layouts[lid].name}
              <span class="light-count">${this._layouts[lid].light_count || (this._layouts[lid].lights || []).length}</span>
            </button>
          `
        )}
      </div>
    `;
  }

  render() {
    if (!this._hass) {
      return html`<ha-card><div class="loading">Loading...</div></ha-card>`;
    }

    return html`
      <ha-card>
        <div class="card-header">
          <ha-icon icon="mdi:lightbulb-multiple"></ha-icon>
          <span>HA LightFX</span>
        </div>
        <div class="card-content">
          ${this._renderLayoutList()}
          ${this._selectedLayout
            ? html`
                ${this._renderGrid()}
                ${this._renderControls()}
              `
            : html`<div class="select-hint">Select a layout above to control effects</div>`}
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      ha-card {
        padding: 16px;
      }
      .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 18px;
        font-weight: 500;
        margin-bottom: 16px;
        color: var(--primary-text-color);
      }
      .card-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      /* Layout list */
      .layout-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .layout-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 14px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s;
      }
      .layout-btn:hover {
        border-color: var(--accent-color);
      }
      .layout-btn.active {
        border-color: var(--accent-color);
        background: var(--accent-color);
        color: var(--text-primary-color, #fff);
      }
      .light-count {
        background: rgba(128, 128, 128, 0.3);
        border-radius: 10px;
        padding: 1px 7px;
        font-size: 12px;
      }
      .layout-btn.active .light-count {
        background: rgba(255, 255, 255, 0.3);
      }
      .no-layouts,
      .select-hint,
      .empty-grid {
        color: var(--secondary-text-color);
        font-size: 14px;
        padding: 12px;
        text-align: center;
      }
      .no-layouts code {
        display: block;
        margin-top: 8px;
        font-size: 13px;
        background: var(--secondary-background-color);
        padding: 4px 8px;
        border-radius: 4px;
      }

      /* SVG grid */
      .grid-container {
        width: 100%;
        background: var(--secondary-background-color);
        border-radius: 12px;
        padding: 8px;
      }
      .layout-svg {
        width: 100%;
        height: auto;
        aspect-ratio: 1;
      }
      .light-dot {
        transition: all 0.3s;
        cursor: pointer;
      }
      .light-glow {
        animation: pulse 2s ease-in-out infinite;
      }
      @keyframes pulse {
        0%, 100% { opacity: 0.2; }
        50% { opacity: 0.4; }
      }

      /* Controls */
      .controls {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .info-msg {
        font-size: 13px;
        color: var(--accent-color);
        text-align: center;
        padding: 4px;
      }
      .control-row {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .control-row label {
        min-width: 90px;
        font-size: 13px;
        color: var(--primary-text-color);
      }
      .control-row select,
      .control-row input[type="range"] {
        flex: 1;
      }
      .control-row select {
        padding: 4px 8px;
        border-radius: 6px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font-size: 13px;
      }
      .control-row input[type="color"] {
        width: 36px;
        height: 36px;
        border: 1px solid var(--divider-color);
        border-radius: 6px;
        padding: 2px;
        cursor: pointer;
      }
      .control-row input[type="range"] {
        -webkit-appearance: none;
        appearance: none;
        height: 4px;
        border-radius: 2px;
        background: var(--secondary-text-color);
      }
      .control-row input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: var(--accent-color);
        cursor: pointer;
      }

      /* Buttons */
      .button-row {
        display: flex;
        gap: 8px;
        margin-top: 4px;
      }
      .button-row button {
        flex: 1;
        padding: 10px;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.2s;
      }
      .button-row button:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      .btn-play {
        background: var(--accent-color);
        color: var(--text-primary-color, #fff);
      }
      .btn-stop {
        background: var(--error-color, #ef5350);
        color: #fff;
      }

      .loading {
        padding: 24px;
        text-align: center;
        color: var(--secondary-text-color);
      }
    `;
  }
}

customElements.define("ha-lightfx-card", HAFXLayoutCard);

// Card configuration
window.customCards = window.customCards || [];
window.customCards.push({
  type: "ha-lightfx-card",
  name: "HA LightFX",
  description: "Virtual WLED-style light effects control card",
  preview: false,
});
