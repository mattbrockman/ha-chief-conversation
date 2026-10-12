"""Admin-only HTTP views the Mini long-polls. Auth is HA's own bearer token."""
from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN


def get_store(hass: HomeAssistant):
    for key, val in hass.data.get(DOMAIN, {}).items():
        if key != "_views":
            return val
    return None


def _is_admin(request: web.Request) -> bool:
    user = request.get("hass_user")
    return bool(user is not None and user.is_admin)


class ChiefNextView(HomeAssistantView):
    url = "/api/chief_conversation/next"
    name = "api:chief_conversation:next"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        if not _is_admin(request):
            return self.json_message("Admin only", HTTPStatus.FORBIDDEN)
        store = get_store(self.hass)
        if store is None:
            return self.json_message("Not set up", HTTPStatus.SERVICE_UNAVAILABLE)
        try:
            wait = float(request.query.get("wait", "0"))
        except ValueError:
            return self.json_message("Bad wait", HTTPStatus.BAD_REQUEST)
        item = await store.next(wait)
        if item is None:
            return web.Response(status=HTTPStatus.NO_CONTENT)
        return self.json(item)


class ChiefReplyView(HomeAssistantView):
    url = "/api/chief_conversation/reply"
    name = "api:chief_conversation:reply"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        if not _is_admin(request):
            return self.json_message("Admin only", HTTPStatus.FORBIDDEN)
        try:
            body = await request.json()
        except ValueError:
            return self.json_message("Bad JSON", HTTPStatus.BAD_REQUEST)
        rid = body.get("id") if isinstance(body, dict) else None
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(rid, str) or not isinstance(text, str):
            return self.json_message("Need id and text", HTTPStatus.BAD_REQUEST)
        store = get_store(self.hass)
        if store is None or not store.deliver(rid, text):
            return self.json_message("Unknown id", HTTPStatus.NOT_FOUND)
        return self.json({"ok": True})
