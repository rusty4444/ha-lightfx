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

const DEFAULT_CONFIG = {
  title: "HA LightFX",
  default_layout: "",
  show_layout_selector: true,
  show_zone_legend: true,
  allow_drag: true,
  show_refresh_button: true,
  confirm_stop: true,
};

const CARD_SCHEMA = [
  { name: "title", selector: { text: {} } },
  { name: "default_layout", selector: { text: {} } },
  { name: "show_layout_selector", selector: { boolean: {} } },
  { name: "show_zone_legend", selector: { boolean: {} } },
  { name: "allow_drag", selector: { boolean: {} } },
  { name: "show_refresh_button", selector: { boolean: {} } },
  { name: "confirm_stop", selector: { boolean: {} } },
];

function fireConfigChanged(element, config) {
  element.dispatchEvent(new CustomEvent("config-changed", {
    detail: { config },
    bubbles: true,
    composed: true,
  }));
}

class HAFXLayoutCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
    };
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...(config || {}) };
  }

  _valueChanged(ev) {
    ev.stopPropagation();
    const value = ev.detail?.value || {};
    const config = { ...this._config, ...value };
    if (!config.default_layout) delete config.default_layout;
    if (!config.title) config.title = DEFAULT_CONFIG.title;
    this._config = config;
    fireConfigChanged(this, config);
  }

  render() {
    if (!this._config) return html``;
    return html`
      <div class="editor">
        <ha-form
          .hass=${this.hass}
          .data=${this._config}
          .schema=${CARD_SCHEMA}
          .computeLabel=${this._computeLabel}
          .computeHelper=${this._computeHelper}
          @value-changed=${this._valueChanged}
        ></ha-form>
        <div class="hint">
          Leave <code>default_layout</code> empty to auto-select the first available layout.
        </div>
      </div>
    `;
  }

  _computeLabel(schema) {
    const labels = {
      title: "Card title",
      default_layout: "Default layout ID",
      show_layout_selector: "Show layout selector",
      show_zone_legend: "Show zone legend",
      allow_drag: "Allow drag repositioning",
      show_refresh_button: "Show refresh button",
      confirm_stop: "Confirm before stopping",
    };
    return labels[schema.name] || schema.name;
  }

  _computeHelper(schema) {
    const helpers = {
      default_layout: "Example: living_room. Layout IDs are generated from layout names.",
      allow_drag: "When enabled, dragging a light dot updates its stored x/y position.",
      confirm_stop: "Show a confirmation prompt before restoring lights and stopping an effect.",
    };
    return helpers[schema.name] || undefined;
  }

  static get styles() {
    return css`
      .editor {
        display: block;
        padding: 8px 0;
      }
      .hint {
        color: var(--secondary-text-color);
        font-size: 12px;
        line-height: 1.4;
        margin-top: 8px;
      }
      code {
        background: var(--secondary-background-color);
        border-radius: 4px;
        padding: 1px 4px;
      }
    `;
  }
}

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
      _dragState: { state: true },
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
    this._dragState = null;
    this._lastConfigHash = "";
    this._loaded = false;
  }

  setConfig(config) {
    this.config = { ...DEFAULT_CONFIG, ...(config || {}) };
    if (this.config.default_layout) {
      this._selectedLayout = this.config.default_layout;
    }
  }

  static getConfigElement() {
    return document.createElement("ha-lightfx-card-editor");
  }

  static getStubConfig() {
    return { ...DEFAULT_CONFIG };
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener("pointermove", this._onDragMove);
    window.removeEventListener("pointerup", this._onDragEnd);
    this._dragState = null;
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;
    if (oldHass !== hass) this.requestUpdate();
  }

  firstUpdated() {
    this._refreshLayouts();
    this._loaded = true;
  }

  updated(changedProps) {
    super.updated(changedProps);
    if (!this._loaded && changedProps.has("config") && this.config && Object.keys(this.config).length > 0) {
      this._refreshLayouts();
    }
  }

  async _refreshLayouts() {
    try {
      const result = await this._hass.callWS({
        type: "ha_lightfx/layouts",
      });
      this._layouts = result.layouts || {};
      const layoutIds = Object.keys(this._layouts);
      if (this.config.default_layout && this._layouts[this.config.default_layout]) {
        this._selectedLayout = this.config.default_layout;
      } else if (!this._selectedLayout || !this._layouts[this._selectedLayout]) {
        this._selectedLayout = layoutIds[0] || null;
      }
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


  _onDragStart(e, lp) {
    e.preventDefault();
    this._dragState = {
      layoutId: this._selectedLayout,
      entityId: lp.entity_id,
      startLightX: lp.x,
      startLightY: lp.y,
    };
    window.addEventListener("pointermove", this._onDragMove);
    window.addEventListener("pointerup", this._onDragEnd);
  }

  _onDragMove = (e) => {
    if (!this._dragState || !this._hass) return;
    const svg = this.shadowRoot?.querySelector(".layout-svg");
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const dx = ((e.clientX - rect.left) / rect.width) * 100;
    const dy = ((e.clientY - rect.top) / rect.height) * 100;
    this._dragState.currentX = Math.round(Math.max(0, Math.min(100, dx)));
    this._dragState.currentY = Math.round(Math.max(0, Math.min(100, dy)));
    this.requestUpdate();
  };

  _onDragEnd = () => {
    if (!this._dragState) return;
    const { layoutId, entityId, currentX, currentY } = this._dragState;
    this._dragState = null;
    window.removeEventListener("pointermove", this._onDragMove);
    window.removeEventListener("pointerup", this._onDragEnd);
    if (currentX === undefined) return;
    if (this._layouts[layoutId]) {
      const lp = (this._layouts[layoutId].lights || []).find((l) => l.entity_id === entityId);
      void this._callService("add_light", {
        layout_id: layoutId,
        entity_id: entityId,
        x: currentX,
        y: currentY,
        z: lp?.z || 0,
        zone: lp?.zone || "other",
      });
    }
  };

  async _callService(service, data = {}, refreshAfter = true) {
    if (!this._hass) return false;
    try {
      await this._hass.callService("ha_lightfx", service, data);
      if (refreshAfter) await this._refreshLayouts();
      return true;
    } catch (err) {
      console.error("HA LightFX: service call failed", service, err);
      this._infoMsg = `⚠ Error: ${err.message || err}`;
      this.requestUpdate();
      return false;
    }
  }

  _selectLayout(lid) {
    this._selectedLayout = lid;
    this._infoMsg = "";
  }

  async _startEffect() {
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

    await this._callService("start_effect", data);
  }

  async _stopEffect() {
    if (!this._selectedLayout) return;
    const layout = this._layouts[this._selectedLayout];
    if (!layout || !layout.running) return;
    if (this.config.confirm_stop && !confirm("Stop the running effect? Lights will restore to their previous state.")) return;
    await this._callService("stop_effect", {
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
          <rect x="0" y="0" width="100" height="100" fill="none" stroke="var(--secondary-text-color)" stroke-width="0.3" opacity="0.3"></rect>

          <!-- Light dots -->
          ${lights.map((lp) => {
            const color = ZONE_COLORS[lp.zone] || ZONE_COLORS.other;
            const state = this._hass ? this._hass.states[lp.entity_id] : null;
            const isOn = state && state.state === "on";
            const isDragging = this._dragState?.entityId === lp.entity_id;
            const dotX = isDragging && this._dragState?.currentX !== undefined ? this._dragState.currentX : lp.x;
            const dotY = isDragging && this._dragState?.currentY !== undefined ? this._dragState.currentY : lp.y;
            return html`
              <g
                @pointerdown="${(e) => this.config.allow_drag && this._onDragStart(e, lp)}"
                class="light-group${this._dragState?.entityId === lp.entity_id ? ' dragging' : ''}${this.config.allow_drag ? ' draggable' : ''}"
              >
                <circle
                  cx="${dotX}"
                  cy="${dotY}"
                  r="${isOn ? 3.5 : 2.5}"
                  fill="${color}"
                  opacity="${isOn ? 1 : 0.4}"
                  class="light-dot"
                ></circle>
                ${isOn
                  ? html`<circle
                      cx="${dotX}"
                      cy="${dotY}"
                      r="5"
                      fill="${color}"
                      opacity="0.3"
                      class="light-glow"
                    ></circle>`
                  : ""}
                <text
                  x="${dotX}"
                  y="${dotY + 5}"
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
        ${this.config.show_zone_legend ? html`
          <!-- Zone legend (only zones present in layout) -->
          <div class="zone-legend">
            ${[...new Set(lights.map((l) => l.zone || "other"))].map((z) => html`
              <span class="zone-tag"><span class="zone-swatch" style="background:${ZONE_COLORS[z] || ZONE_COLORS.other}"></span>${z}</span>
            `)}
          </div>
        ` : ""}
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
          <label for="ha-lightfx-effect">Effect</label>
          <select
            id="ha-lightfx-effect"
            name="ha-lightfx-effect"
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
          <label for="ha-lightfx-color-primary">Color</label>
          <input
            id="ha-lightfx-color-primary"
            name="ha-lightfx-color-primary"
            type="color"
            .value="${this._color1}"
            @change="${(e) => (this._color1 = e.target.value)}"
            ?disabled="${running}"
          />
          <input
            id="ha-lightfx-color-secondary"
            name="ha-lightfx-color-secondary"
            type="color"
            .value="${this._color2}"
            @change="${(e) => (this._color2 = e.target.value)}"
            ?disabled="${running}"
          />
        </div>

        <div class="control-row">
          <label for="ha-lightfx-brightness">Brightness ${this._brightness}%</label>
          <input
            id="ha-lightfx-brightness"
            name="ha-lightfx-brightness"
            type="range"
            min="1"
            max="100"
            .value="${this._brightness}"
            @input="${(e) => (this._brightness = parseInt(e.target.value))}"
          />
        </div>

        <div class="control-row">
          <label for="ha-lightfx-speed">Speed ${this._speed}%</label>
          <input
            id="ha-lightfx-speed"
            name="ha-lightfx-speed"
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

    if (!this.config.show_layout_selector) return "";

    return html`
      <div class="layout-list">
        ${lids.map(
          (lid) => html`
            <button
              class=${classMap({ "layout-btn": true, active: lid === this._selectedLayout })}
              @click=${() => this._selectLayout(lid)}
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
          <div class="title-wrap">
            <ha-icon icon="mdi:lightbulb-multiple"></ha-icon>
            <span>${this.config.title || DEFAULT_CONFIG.title}</span>
          </div>
          ${this.config.show_refresh_button ? html`
            <button class="icon-btn" @click=${this._refreshLayouts} title="Refresh layouts">↻</button>
          ` : ""}
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
        justify-content: space-between;
        gap: 8px;
        font-size: 18px;
        font-weight: 500;
        margin-bottom: 16px;
        color: var(--primary-text-color);
      }
      .title-wrap {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .icon-btn {
        border: 1px solid var(--divider-color);
        border-radius: 999px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        font-size: 18px;
        height: 32px;
        line-height: 1;
        width: 32px;
      }
      .icon-btn:hover {
        border-color: var(--accent-color);
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
      .light-group.draggable {
        cursor: grab;
      }
      .light-group:active {
        cursor: grabbing;
      }
      .light-group text {
        pointer-events: none;
      }
      .light-group .light-glow {
        pointer-events: none;
      }
      .light-dot {
        transition: all 0.3s;
      }
      .light-dot.dragging {
        transition: none;
      }
      .light-group.dragging .light-dot {
        transition: none;
      }
      .zone-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 6px 4px 0;
        justify-content: center;
      }
      .zone-tag {
        display: flex;
        align-items: center;
        gap: 3px;
        font-size: 11px;
        color: var(--secondary-text-color);
        text-transform: capitalize;
      }
      .zone-swatch {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
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

if (!customElements.get("ha-lightfx-card-editor")) {
  customElements.define("ha-lightfx-card-editor", HAFXLayoutCardEditor);
}
if (!customElements.get("ha-lightfx-card")) {
  customElements.define("ha-lightfx-card", HAFXLayoutCard);
}

// Card configuration
window.customCards = window.customCards || [];
window.customCards.push({
  type: "ha-lightfx-card",
  name: "HA LightFX",
  description: "Virtual WLED-style light effects control card",
  preview: false,
});
