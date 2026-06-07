"""Tests for HA LightFX frontend resource registration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ha_lightfx import (
    FRONTEND_URL,
    _frontend_resource_url,
    _lovelace_resources_collection,
    _register_lovelace_resource,
    _same_frontend_resource,
)


class MockResourcesCollection:
    """Minimal Lovelace resources collection for registration tests."""

    def __init__(self, items=None):
        self.items = list(items or [])
        self.async_create_item = AsyncMock(side_effect=self._create)
        self.async_update_item = AsyncMock(side_effect=self._update)

    def async_items(self):
        return self.items

    async def _create(self, data):
        item = {"id": f"item-{len(self.items) + 1}", **data}
        self.items.append(item)
        return item

    async def _update(self, item_id, updates):
        for item in self.items:
            if item.get("id") == item_id:
                item.update(updates)
                return item
        raise KeyError(item_id)


@pytest.mark.unit
def test_same_frontend_resource_ignores_query_string() -> None:
    """Resource matching ignores cache-busting query params."""
    assert _same_frontend_resource(FRONTEND_URL)
    assert _same_frontend_resource(f"{FRONTEND_URL}?v=1.0.0")
    assert not _same_frontend_resource("/local/other-card.js?v=1.0.0")
    assert not _same_frontend_resource(None)


@pytest.mark.unit
def test_lovelace_resources_collection_supports_dict_and_object() -> None:
    """Home Assistant has used both dict and LovelaceData object shapes."""
    dict_collection = object()
    hass = MagicMock()
    hass.data = {"lovelace": {"resources": dict_collection}}
    assert _lovelace_resources_collection(hass) is dict_collection

    object_collection = object()
    hass.data = {"lovelace": SimpleNamespace(resources=object_collection)}
    assert _lovelace_resources_collection(hass) is object_collection


@pytest.mark.unit
async def test_register_lovelace_resource_creates_resource() -> None:
    """The card is auto-registered when no existing resource is present."""
    collection = MockResourcesCollection()
    hass = MagicMock()
    hass.data = {"lovelace": SimpleNamespace(resources=collection)}

    await _register_lovelace_resource(hass)

    expected_url = _frontend_resource_url()
    collection.async_create_item.assert_awaited_once_with(
        {"res_type": "module", "url": expected_url}
    )
    assert collection.items[0]["url"] == expected_url


@pytest.mark.unit
async def test_register_lovelace_resource_updates_stale_cache_busted_url() -> None:
    """Existing HA LightFX resources are updated to the current versioned URL."""
    collection = MockResourcesCollection(
        [{"id": "abc", "url": f"{FRONTEND_URL}?v=1.1.3", "res_type": "module"}]
    )
    hass = MagicMock()
    hass.data = {"lovelace": SimpleNamespace(resources=collection)}

    await _register_lovelace_resource(hass)

    expected_url = _frontend_resource_url()
    collection.async_update_item.assert_awaited_once_with(
        "abc", {"res_type": "module", "url": expected_url}
    )
    collection.async_create_item.assert_not_awaited()
    assert collection.items[0]["url"] == expected_url


@pytest.mark.unit
async def test_register_lovelace_resource_skips_exact_match() -> None:
    """Already-current resources are left alone."""
    collection = MockResourcesCollection(
        [{"id": "abc", "url": _frontend_resource_url(), "res_type": "module"}]
    )
    hass = MagicMock()
    hass.data = {"lovelace": SimpleNamespace(resources=collection)}

    await _register_lovelace_resource(hass)

    collection.async_update_item.assert_not_awaited()
    collection.async_create_item.assert_not_awaited()


@pytest.mark.unit
def test_frontend_resource_url_uses_cached_manifest_version(monkeypatch) -> None:
    """Resource URL generation must not read manifest.json in the event loop."""
    import custom_components.ha_lightfx as ha_lightfx

    monkeypatch.setattr(ha_lightfx, "MANIFEST_VERSION", "9.9.9")
    monkeypatch.setattr(
        ha_lightfx.Path,
        "read_text",
        MagicMock(side_effect=AssertionError("manifest should not be read here")),
    )

    assert ha_lightfx._frontend_resource_url() == f"{FRONTEND_URL}?v=9.9.9"
