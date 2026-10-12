# Chief conversation (Home Assistant)

A custom integration that lets Assist (the Voice PE speaker, the HA app) talk to the chief on the Mac Mini. The Mini never accepts connections: it long-polls Home Assistant with its own admin token.

## Install
1. HACS > Custom repositories > add this repo (type Integration) and download it, or copy `custom_components/chief_conversation` into `/config/custom_components/`.
2. Restart Home Assistant.
3. Settings > Devices & services > Add integration > "Chief".
4. Settings > Voice assistants > your pipeline > Conversation agent: pick "Chief".
5. On the same pipeline turn on "Prefer handling commands locally", so lights, shades and music stay instant and only the rest reaches the chief.

## How it works
- Each utterance becomes a pending request. `GET /api/chief_conversation/next?wait=25` (admin token) returns one request or 204. `POST /api/chief_conversation/reply` with `{"id", "text"}` answers it.
- Assist waits 8 seconds, speaks the reply, else says the answer will be in Telegram. A later reply is announced on the same satellite (`assist_satellite.announce`).
- Limits: 4000 bytes in, 3500 characters out, 20 pending. Unclaimed after 120 s or unanswered after 900 s is dropped.
- No secrets in the integration. Auth is Home Assistant's bearer token, admin users only.
