"""Tests for HA LightFX Lovelace resource registration."""

from types import SimpleNamespace

import pytest

from custom_components.ha_lightfx import (
    _frontend_resource_url,
    _register_lovelace_resource,
)


class FakeResourcesCollection:
    """Small Lovelace resources collection test double."""

    def __init__(self, items):
        self.items = list(items)
        self.created = []
        self.updated = []
        self.deleted = []

    def async_items(self):
        return list(self.items)

    async def async_create_item(self, payload):
        item = {
            "id": f"created-{len(self.created)}",
            "url": payload["url"],
            "type": payload["res_type"],
        }
        self.created.append(payload)
        self.items.append(item)
        return item

    async def async_update_item(self, item_id, payload):
        self.updated.append((item_id, payload))
        for item in self.items:
            if item.get("id") == item_id:
                item["url"] = payload["url"]
                item["type"] = payload["res_type"]
                return item
        raise KeyError(item_id)

    async def async_delete_item(self, item_id):
        self.deleted.append(item_id)
        self.items = [item for item in self.items if item.get("id") != item_id]


@pytest.mark.unit
async def test_register_lovelace_resource_removes_duplicate_lightfx_entries():
    """Only one HA LightFX card resource should remain after setup."""
    current_url = _frontend_resource_url()
    resources = FakeResourcesCollection(
        [
            {"id": "new", "url": current_url, "type": "module"},
            {"id": "old-1", "url": "/ha_lightfx/ha-lightfx-card.js?v=1.1.5", "type": "module"},
            {"id": "old-2", "url": "/ha_lightfx/ha-lightfx-card.js?v=1.1.4", "type": "module"},
            {"id": "other", "url": "/hacsfiles/other/card.js", "type": "module"},
        ]
    )
    hass = SimpleNamespace(data={"lovelace": {"resources": resources}})

    await _register_lovelace_resource(hass)

    assert resources.updated == []
    assert resources.created == []
    assert resources.deleted == ["old-1", "old-2"]
    lightfx_urls = [item["url"] for item in resources.items if "ha-lightfx-card.js" in item["url"]]
    assert lightfx_urls == [current_url]


@pytest.mark.unit
async def test_register_lovelace_resource_updates_one_stale_entry_and_deletes_rest():
    """Stale resource URLs are updated and extra stale copies are removed."""
    current_url = _frontend_resource_url()
    resources = FakeResourcesCollection(
        [
            {"id": "old-1", "url": "/ha_lightfx/ha-lightfx-card.js?v=1.1.5", "type": "module"},
            {"id": "old-2", "url": "/ha_lightfx/ha-lightfx-card.js?v=1.1.4", "type": "module"},
        ]
    )
    hass = SimpleNamespace(data={"lovelace": SimpleNamespace(resources=resources)})

    await _register_lovelace_resource(hass)

    assert resources.updated == [("old-1", {"res_type": "module", "url": current_url})]
    assert resources.deleted == ["old-2"]
    assert [item["url"] for item in resources.items] == [current_url]
