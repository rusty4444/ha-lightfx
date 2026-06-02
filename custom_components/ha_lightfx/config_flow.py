"""
Config flow for HA LightFX integration.

Provides a fully-editable options flow where users manage layouts and their
lights entirely through the HA UI — no YAML required.
"""

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_NAME, EFFECTS


class LightFXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Minimal config flow — the integration is set up, then configured via options."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="HA LightFX", data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LightFXOptionsFlow(config_entry)


class LightFXOptionsFlow(config_entries.OptionsFlow):
    """Full visual editor for layouts and lights."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._context_storage = {}  # cross-step state (layout_id, etc.)

    # ── Top-level menu ────────────────────────────────────────────────────

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "manage_layouts",
                "manage_lights",
                "manage_profiles",
                "manage_groups",
            ],
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  LAYOUTS
    # ═══════════════════════════════════════════════════════════════════════

    async def async_step_manage_layouts(self, user_input=None):
        """Submenu: create, rename, delete, or back."""
        return self.async_show_menu(
            step_id="manage_layouts",
            menu_options=["create_layout"]
            + (["rename_layout", "delete_layout"] if self._engine().list_layouts() else []),
        )

    async def async_step_create_layout(self, user_input=None):
        """Create a new layout."""
        if user_input is not None:
            name = user_input[CONF_NAME]
            try:
                self._engine().create_layout(name)
            except ValueError:
                return self.async_show_form(
                    step_id="create_layout",
                    data_schema=_LAYOUT_SCHEMA(),
                    errors={"base": "duplicate"},
                )
            await self._save()
            return self.async_create_entry(title=f"✓ Layout '{name}' created", data={})
        return self.async_show_form(
            step_id="create_layout",
            data_schema=_LAYOUT_SCHEMA(),
        )

    async def async_step_rename_layout_pick(self, user_input=None):
        """Pick which layout to rename."""
        engine = self._engine()
        layouts = engine.list_layouts()
        if not layouts:
            return self.async_abort(reason="no_layouts")
        if user_input is not None:
            self._context_storage["rename_layout_id"] = user_input["layout_id"]
            return await self.async_step_rename_layout_name(None)
        return self.async_show_form(
            step_id="rename_layout_pick",
            data_schema=vol.Schema({
                vol.Required("layout_id"): vol.In(
                    {lid: f"{info['name']} ({info['light_count']} lights)"
                     for lid, info in layouts.items()}
                ),
            }),
            description_placeholders={"hint": "Pick the layout to rename."},
        )

    async def async_step_rename_layout_name(self, user_input=None):
        """Enter the new name for the selected layout."""
        engine = self._engine()
        lid = self._context_storage.get("rename_layout_id")
        if not lid:
            return await self.async_step_rename_layout_pick(None)
        ls = engine.get_layout(lid)
        if user_input is not None:
            if ls and CONF_NAME in user_input:
                ls.name = user_input[CONF_NAME]
                await self._save()
            self._context_storage.pop("rename_layout_id", None)
            return self.async_create_entry(title=f"✓ Layout renamed", data={})
        return self.async_show_form(
            step_id="rename_layout_name",
            data_schema=_LAYOUT_SCHEMA(ls.name if ls else ""),
            description_placeholders={"hint": "Enter the new name."},
        )

    # Keep original step for menu backward compat — routes to pick
    async def async_step_rename_layout(self, user_input=None):
        return await self.async_step_rename_layout_pick(user_input)

    async def async_step_delete_layout(self, user_input=None):
        """Pick a layout and confirm deletion."""
        engine = self._engine()
        if user_input is not None:
            lid = self._context_storage.get("delete_layout_id")
            if not lid:
                lid = user_input.get("layout_id")
                if lid:
                    self._context_storage["delete_layout_id"] = lid
                    return await self.async_step_delete_layout(None)
            if user_input.get("confirm") is True:
                engine.remove_layout(lid)
                await self._save()
                self._context_storage.pop("delete_layout_id", None)
                return self.async_create_entry(title=f"✓ Layout deleted", data={})
            if user_input.get("confirm") is False:
                self._context_storage.pop("delete_layout_id", None)
                return self.async_abort(reason="canceled")

        lids = list(engine.list_layouts().keys())
        if not lids:
            return self.async_abort(reason="no_layouts")

        # Already have a layout_id picked from a prior step?
        lid = self._context_storage.get("delete_layout_id")
        if lid is None:
            # Show picker first
            return self.async_show_form(
                step_id="delete_layout",
                data_schema=vol.Schema({
                    vol.Required("layout_id"): vol.In(
                        {l: engine.get_layout(l).name for l in lids}
                    ),
                }),
            )

        # Confirm step
        self._context_storage["delete_layout_id"] = lid
        return self.async_show_form(
            step_id="delete_layout",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): bool,
            }),
            description_placeholders={
                "name": engine.get_layout(lid).name,
                "lights": str(len(engine.get_layout(lid).lights)),
            },
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  LIGHTS
    # ═══════════════════════════════════════════════════════════════════════

    async def async_step_manage_lights(self, user_input=None):
        """Pick a layout, then list its lights."""
        engine = self._engine()
        layouts = engine.list_layouts()
        if not layouts:
            return self.async_abort(reason="no_layouts")

        if user_input is not None:
            lid = user_input.get("layout_id")
            self._context_storage["light_layout_id"] = lid
            return await self._step_list_lights(lid)

        return self.async_show_form(
            step_id="manage_lights",
            data_schema=vol.Schema({
                vol.Required("layout_id"): vol.In(
                    {lid: info["name"] for lid, info in layouts.items()}
                ),
            }),
        )

    async def _step_list_lights(self, layout_id, user_input=None):
        """Show lights in a layout with what to do next."""
        engine = self._engine()
        ls = engine.get_layout(layout_id)
        if ls is None:
            return self.async_abort(reason="layout_not_found")

        if user_input is not None:
            action = user_input.get("_action")
            ent = user_input.get("entity_id")
            if action == "add":
                return await self._step_add_light(layout_id)
            if action == "edit" and ent:
                self._context_storage["edit_entity_id"] = ent
                return await self._step_edit_light(layout_id, ent, engine)
            if action == "remove" and ent:
                self._context_storage["remove_entity_id"] = ent
                return await self._step_remove_light(layout_id, ent, engine)
        else:
            self._context_storage["light_layout_id"] = layout_id

        has_lights = bool(ls.lights)
        menu_ops = ["add"]
        if has_lights:
            menu_ops += ["edit", "remove"]

        lights_desc = "\n".join(
            f"• **{lp.entity_id}**  (x={lp.x}, y={lp.y}, zone={lp.zone})"
            for lp in ls.lights
        ) if has_lights else "_No lights in this layout yet._"

        schema = {
            vol.Optional("_action", default="add"): vol.In(menu_ops),
        }
        if has_lights:
            schema[vol.Optional("entity_id")] = vol.In(
                {lp.entity_id: f"{lp.entity_id}  [{lp.zone}]" for lp in ls.lights}
            )

        return self.async_show_form(
            step_id="list_lights",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "layout": ls.name,
                "lights": lights_desc,
            },
        )

    async def async_step_list_lights(self, user_input=None):
        """Called when returning from add/edit/remove sub-steps."""
        lid = self._context_storage.get("light_layout_id")
        if not lid:
            return await self.async_step_manage_lights(None)
        return await self._step_list_lights(lid, user_input)

    # ── Add light ─────────────────────────────────────────────────────

    async def _step_add_light(self, layout_id, user_input=None):
        engine = self._engine()
        if user_input is not None:
            engine.add_light(
                layout_id,
                user_input["entity_id"],
                user_input["x"],
                user_input["y"],
                user_input.get("z", 0),
                user_input.get("zone", "other"),
            )
            await self._save()
            return await self._step_list_lights(layout_id, None)
        return self.async_show_form(
            step_id="add_light",
            data_schema=_LIGHT_SCHEMA(),
        )

    async def async_step_add_light(self, user_input=None):
        lid = self._context_storage.get("light_layout_id")
        if not lid:
            return self.async_abort(reason="no_layout")
        return await self._step_add_light(lid, user_input)

    # ── Edit light ────────────────────────────────────────────────────

    async def _step_edit_light(self, layout_id, entity_id, engine, user_input=None):
        ls = engine.get_layout(layout_id)
        if ls is None:
            return self.async_abort(reason="layout_not_found")
        existing = next((l for l in ls.lights if l.entity_id == entity_id), None)
        if existing is None:
            return self.async_abort(reason="light_not_found")

        if user_input is not None:
            existing.x = user_input["x"]
            existing.y = user_input["y"]
            existing.z = user_input.get("z", existing.z)
            existing.zone = user_input.get("zone", "other")
            await self._save()
            self._context_storage.pop("edit_entity_id", None)
            return await self._step_list_lights(layout_id, None)
        return self.async_show_form(
            step_id="edit_light",
            data_schema=vol.Schema({
                vol.Required("x", default=existing.x):
                    vol.All(vol.Coerce(int), vol.Range(0, 100)),
                vol.Required("y", default=existing.y):
                    vol.All(vol.Coerce(int), vol.Range(0, 100)),
                vol.Optional("z", default=existing.z):
                    vol.All(vol.Coerce(int), vol.Range(0, 100)),
                vol.Optional("zone", default=existing.zone): vol.In(
                    ["ceiling", "wall", "accent", "floor", "other"]
                ),
            }),
        )

    async def async_step_edit_light(self, user_input=None):
        lid = self._context_storage.get("light_layout_id")
        if not lid:
            return self.async_abort(reason="no_layout")
        engine = self._engine()
        ls = engine.get_layout(lid)
        if not ls:
            return self.async_abort(reason="layout_not_found")
        ents = {lp.entity_id: f"{lp.entity_id}  [{lp.zone}]" for lp in ls.lights}
        if user_input is None:
            return self.async_show_form(
                step_id="edit_light",
                data_schema=vol.Schema({
                    vol.Required("entity_id"): vol.In(ents),
                }),
                description_placeholders={"hint": "Pick the light to edit."},
            )
        ent = user_input.get("entity_id") or self._context_storage.get("edit_entity_id")
        if ent not in ents:
            return self.async_abort(reason="light_not_found")
        self._context_storage["edit_entity_id"] = ent
        if "x" not in user_input and "y" not in user_input:
            return await self._step_edit_light(lid, ent, engine, None)
        return await self._step_edit_light(lid, ent, engine, user_input)

    # ── Remove light ──────────────────────────────────────────────────

    async def _step_remove_light(self, layout_id, entity_id, engine, user_input=None):
        if user_input is not None:
            if user_input.get("confirm") is True:
                engine.remove_light(layout_id, entity_id)
                await self._save()
            self._context_storage.pop("remove_entity_id", None)
            return await self._step_list_lights(layout_id, None)
        return self.async_show_form(
            step_id="remove_light",
            data_schema=vol.Schema({
                vol.Required("confirm", default=False): bool,
            }),
            description_placeholders={"entity": entity_id},
        )

    async def async_step_remove_light(self, user_input=None):
        lid = self._context_storage.get("light_layout_id")
        if not lid:
            return self.async_abort(reason="no_layout")
        engine = self._engine()
        ls = engine.get_layout(lid)
        if not ls:
            return self.async_abort(reason="layout_not_found")
        ents = {lp.entity_id: lp.entity_id for lp in ls.lights}
        if user_input is None:
            return self.async_show_form(
                step_id="remove_light",
                data_schema=vol.Schema({
                    vol.Required("entity_id"): vol.In(ents),
                }),
            )
        ent = user_input.get("entity_id") or self._context_storage.get("remove_entity_id")
        if ent not in ents:
            return self.async_abort(reason="light_not_found")
        self._context_storage["remove_entity_id"] = ent
        if "confirm" not in user_input:
            return await self._step_remove_light(lid, ent, engine, None)
        return await self._step_remove_light(lid, ent, engine, user_input)


    # ═══════════════════════════════════════════════════════════════════════
    #  PROFILES
    # ═══════════════════════════════════════════════════════════════════════

    async def async_step_manage_profiles(self, user_input=None):
        """Profile submenu."""
        engine = self._engine()
        has_profiles = bool(engine.list_profiles())
        menu = ["create_profile"]
        if has_profiles:
            menu += ["delete_profile", "apply_profile"]
        return self.async_show_menu(step_id="manage_profiles", menu_options=menu)

    async def async_step_create_profile(self, user_input=None):
        """Create a new effect profile."""
        if user_input is not None:
            config = {
                "effect": user_input.get("effect", "rainbow"),
                "brightness": user_input.get("brightness", 50),
                "speed": user_input.get("speed", 50),
                "direction": user_input.get("direction", "forward"),
            }
            self._engine().create_profile(user_input["name"], config)
            await self._save()
            return self.async_create_entry(title=f"✓ Profile '{user_input['name']}' created", data={})
        return self.async_show_form(
            step_id="create_profile",
            data_schema=vol.Schema({
                vol.Required("name"): cv.string,
                vol.Optional("effect", default="rainbow"): vol.In(EFFECTS),
                vol.Optional("brightness", default=50):
                    vol.All(vol.Coerce(int), vol.Range(0, 100)),
                vol.Optional("speed", default=50):
                    vol.All(vol.Coerce(int), vol.Range(1, 100)),
                vol.Optional("direction", default="forward"):
                    vol.In(["forward", "reverse", "bounce"]),
            }),
        )

    async def async_step_delete_profile(self, user_input=None):
        """Delete a profile."""
        engine = self._engine()
        profiles = engine.list_profiles()
        if not profiles:
            return self.async_abort(reason="no_profiles")
        if user_input is not None:
            engine.delete_profile(user_input["profile_id"])
            await self._save()
            return self.async_create_entry(title=f"✓ Profile deleted", data={})
        return self.async_show_form(
            step_id="delete_profile",
            data_schema=vol.Schema({
                vol.Required("profile_id"): vol.In(
                    {pid: info["name"] for pid, info in profiles.items()}
                ),
            }),
        )

    async def async_step_apply_profile(self, user_input=None):
        """Apply a profile to a layout."""
        engine = self._engine()
        profiles = engine.list_profiles()
        layouts = engine.list_layouts()
        if not profiles or not layouts:
            return self.async_abort(reason="no_profiles_or_layouts")
        if user_input is not None:
            pid = user_input["profile_id"]
            lid = user_input["layout_id"]
            profile = profiles.get(pid)
            if profile:
                cfg = profile.get("config", {})
                engine.start_effect(
                    lid,
                    effect=cfg.get("effect", "rainbow"),
                    brightness=cfg.get("brightness", 50),
                    speed=cfg.get("speed", 50),
                    direction=cfg.get("direction", "forward"),
                )
            return self.async_create_entry(title=f"✓ Profile '{pid}' applied", data={})
        return self.async_show_form(
            step_id="apply_profile",
            data_schema=vol.Schema({
                vol.Required("profile_id"): vol.In(
                    {pid: info["name"] for pid, info in profiles.items()}
                ),
                vol.Required("layout_id"): vol.In(
                    {lid: info["name"] for lid, info in layouts.items()}
                ),
            }),
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  GROUPS
    # ═══════════════════════════════════════════════════════════════════════

    async def async_step_manage_groups(self, user_input=None):
        engine = self._engine()
        has_groups = bool(engine.list_groups())
        menu = ["create_group"]
        if has_groups:
            menu += ["delete_group"]
        return self.async_show_menu(step_id="manage_groups", menu_options=menu)

    async def async_step_create_group(self, user_input=None):
        engine = self._engine()
        layouts = engine.list_layouts()
        if not layouts:
            return self.async_abort(reason="no_layouts")
        if user_input is not None:
            engine.create_group(user_input["group_id"], user_input["layout_ids"])
            await self._save()
            return self.async_create_entry(title=f"✓ Group '{user_input['group_id']}' created", data={})
        return self.async_show_form(
            step_id="create_group",
            data_schema=vol.Schema({
                vol.Required("group_id"): cv.string,
                vol.Required("layout_ids"): cv.multi_select(
                    {lid: info["name"] for lid, info in layouts.items()}
                ),
            }),
        )

    async def async_step_delete_group(self, user_input=None):
        engine = self._engine()
        groups = engine.list_groups()
        if not groups:
            return self.async_abort(reason="no_groups")
        if user_input is not None:
            engine.delete_group(user_input["group_id"])
            await self._save()
            return self.async_create_entry(title=f"✓ Group deleted", data={})
        return self.async_show_form(
            step_id="delete_group",
            data_schema=vol.Schema({
                vol.Required("group_id"): vol.In(
                    {gid: f"{gid} ({len(lids)} layouts)" for gid, lids in groups.items()}
                ),
            }),
        )
    # ── Helpers ──────────────────────────────────────────────────────────

    def _engine(self):
        return self.hass.data[DOMAIN]["engine"]

    async def _save(self):
        engine = self._engine()
        store = self.hass.data[DOMAIN]["store"]
        await store.async_save(engine.to_storage())


# ─── Standalone schema factories ───────────────────────────────────────────

def _LAYOUT_SCHEMA(default_name=""):
    return vol.Schema({
        vol.Required(CONF_NAME, default=default_name): vol.All(cv.string, vol.Length(min=1)),
    })


def _LIGHT_SCHEMA():
    return vol.Schema({
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("x", default=50):
            vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Required("y", default=50):
            vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Optional("z", default=0):
            vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Optional("zone", default="other"): vol.In(
            ["ceiling", "wall", "accent", "floor", "other"]
        ),
    })
