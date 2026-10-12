"""Chief conversation agent: Assist utterances go to the chief on the Mini."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .http import ChiefNextView, ChiefReplyView
from .store import RequestStore

PLATFORMS = ["conversation"]


def _announce(hass: HomeAssistant, request: dict, text: str) -> None:
    """Late reply: speak it on the satellite the question came from, if any."""
    device_id = request.get("device_id")
    if not device_id:
        return
    for ent in er.async_entries_for_device(er.async_get(hass), device_id):
        if ent.domain == "assist_satellite":
            hass.async_create_task(
                hass.services.async_call(
                    "assist_satellite", "announce",
                    {"entity_id": ent.entity_id, "message": text},
                    blocking=False,
                )
            )
            return


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = RequestStore(on_late_reply=lambda req, text: _announce(hass, req, text))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = store
    if not hass.data[DOMAIN].get("_views"):
        hass.http.register_view(ChiefNextView(hass))
        hass.http.register_view(ChiefReplyView(hass))
        hass.data[DOMAIN]["_views"] = True
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok
