"""Static regression tests for the Lovelace card source."""

from pathlib import Path


FRONTEND_SOURCE = Path(__file__).parents[1] / "frontend" / "ha-lightfx-card.js"


def test_layout_selection_falls_back_when_configured_layout_is_missing() -> None:
    """A stale default_layout must not leave the card stuck on an empty layout."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert "!this._layouts[this._selectedLayout]" in source
    assert "this._selectedLayout = layoutIds[0] || null" in source


def test_class_map_is_the_only_layout_button_class_expression() -> None:
    """Lit's classMap directive throws when mixed with static class text."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert 'class=${classMap({ "layout-btn": true, active: lid === this._selectedLayout })}' in source
    assert 'class="layout-btn ${classMap' not in source


def test_hass_setter_fetches_layouts_after_home_assistant_is_available() -> None:
    """If firstUpdated ran before hass was assigned, the card must still load layouts."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert "if (!oldHass && hass)" in source
    assert "void this._refreshLayouts();" in source
    assert "if (this._hass)" in source


def test_patched_stale_card_instances_refetch_layouts() -> None:
    """Patching a stale custom element should reload layout data, not just rerender old state."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert 'name === "ha-lightfx-card"' in source
    assert "typeof el._refreshLayouts === \"function\"" in source
    assert "void el._refreshLayouts();" in source


def test_custom_elements_are_defined_or_patched_idempotently() -> None:
    """Stale cached resources should not leave an old custom element active."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert 'defineOrPatchCustomElement("ha-lightfx-card-editor", HAFXLayoutCardEditor)' in source
    assert 'defineOrPatchCustomElement("ha-lightfx-card", HAFXLayoutCard)' in source
    assert "Object.defineProperty(existing.prototype, key, descriptor)" in source


def test_custom_card_picker_entries_are_replaced_not_appended() -> None:
    """A current module load should remove stale HA LightFX picker entries."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert 'Symbol.for("ha-lightfx.customCardsPush")' in source
    assert "dedupeLightfxCustomCards" in source
    assert 'cards[i]?.type === LIGHTFX_CUSTOM_CARD.type' in source


def test_custom_card_picker_dedupe_survives_customcards_reassignment() -> None:
    """Some Lovelace stacks replace window.customCards after modules load."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert 'Object.defineProperty(window, "customCards"' in source
    assert "set(newValue)" in source
    assert "_lightfxCustomCardsValue = newValue" in source
    assert "installLightfxCustomCardsDedupe();" in source


def test_custom_card_picker_dedupe_catches_late_parallel_resource_loads() -> None:
    """Late stale resources should be compacted after the first load pass."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert "[0, 250, 1000, 3000, 5000, 10000]" in source
    assert "function _lightfxDedupRaf()" in source
    assert "requestAnimationFrame(_lightfxDedupRaf);" in source


def test_light_dot_colour_has_safe_fallback() -> None:
    """Theme or stale-load CSS issues should not make light dots invisible."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert "var(--light-color, #888)" in source


def test_light_markers_render_as_html_overlay_not_nested_svg_circles() -> None:
    """Light dots should not depend on SVG child parsing quirks in browsers."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert 'class="layout-surface"' in source
    assert 'class="light-layer"' in source
    assert '"light-marker": true' in source
    assert '<span class="light-dot"></span>' in source
    assert '<circle' not in source
    assert 'class="light-group' not in source


def test_light_marker_positions_are_normalised_and_duplicate_safe() -> None:
    """Missing/bad coordinates and duplicate default positions should still be visible."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert "_normaliseCoord(value)" in source
    assert "if (!Number.isFinite(number)) return 50" in source
    assert "_visualPosition(lp, lights, x, y)" in source
    assert "siblings.length <= 1" in source
