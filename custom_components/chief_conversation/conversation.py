"""The "Chief" conversation agent."""
from homeassistant.components import conversation
from homeassistant.components.conversation import ChatLog, ConversationEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ERROR_TEXT, LATE_TEXT, QUICK_WAIT_S, UNREACHABLE_TEXT
from .store import StoreError


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ChiefConversationEntity(entry, hass.data[DOMAIN][entry.entry_id])])


class ChiefConversationEntity(ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = "Chief"

    def __init__(self, entry: ConfigEntry, store) -> None:
        self._store = store
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self):
        return "*"

    async def _async_handle_message(
        self, user_input: conversation.ConversationInput, chat_log: ChatLog
    ) -> conversation.ConversationResult:
        context = user_input.context
        try:
            request = self._store.submit(
                user_input.text,
                device_id=user_input.device_id,
                user_id=context.user_id if context else None,
                conversation_id=chat_log.conversation_id,
                language=user_input.language,
            )
        except StoreError:
            return self._result(user_input, chat_log, ERROR_TEXT)
        reply = await self._store.wait_reply(request["id"], QUICK_WAIT_S)
        if reply is None:
            reply = LATE_TEXT if self._store.is_late(request["id"]) else UNREACHABLE_TEXT
        return self._result(user_input, chat_log, reply)

    @staticmethod
    def _result(user_input, chat_log, text):
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(text)
        return conversation.ConversationResult(
            response=response, conversation_id=chat_log.conversation_id
        )
