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


def test_custom_elements_are_defined_idempotently() -> None:
    """Duplicate Lovelace resources should not crash module evaluation."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert 'if (!customElements.get("ha-lightfx-card-editor"))' in source
    assert 'if (!customElements.get("ha-lightfx-card"))' in source


def test_custom_card_picker_entries_are_replaced_not_appended() -> None:
    """A current module load should remove stale HA LightFX picker entries."""
    source = FRONTEND_SOURCE.read_text(encoding="utf-8")

    assert '.filter((card) => card.type !== "ha-lightfx-card")' in source
    assert 'window.customCards.push(LIGHTFX_CUSTOM_CARD)' in source
