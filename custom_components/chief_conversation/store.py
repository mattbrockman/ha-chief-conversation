"""Pending-request store for the Chief conversation agent.

Pure Python (no Home Assistant import) so it can be tested with stdlib only.
The Mini long-polls next(), then posts the answer back through deliver().
"""
import asyncio
import time
import uuid

MAX_TEXT_BYTES = 4000
MAX_REPLY_CHARS = 3500
MAX_PENDING = 20
MAX_WAIT_S = 30
CLAIM_TTL_S = 120
ANSWER_TTL_S = 900


class StoreError(Exception):
    """A request could not be accepted. args[0] is a short code."""


class RequestStore:
    def __init__(self, clock=time.monotonic, on_late_reply=None):
        self._clock = clock
        self.on_late_reply = on_late_reply  # callable(request, text) or None
        self._reqs = {}      # id -> record
        self._order = []     # ids not yet claimed, oldest first
        self._waiters = []   # futures waiting inside next()

    def _drop(self, rid):
        rec = self._reqs.pop(rid, None)
        if rid in self._order:
            self._order.remove(rid)
        if rec and not rec["fut"].done():
            rec["fut"].set_result(None)

    def _sweep(self):
        now = self._clock()
        for rid, rec in list(self._reqs.items()):
            age = now - rec["t0"]
            if age > ANSWER_TTL_S or (not rec["claimed"] and age > CLAIM_TTL_S):
                self._drop(rid)

    def pending(self):
        self._sweep()
        return len(self._reqs)

    def submit(self, text, device_id=None, user_id=None,
               conversation_id=None, language=None):
        self._sweep()
        if not isinstance(text, str) or not text.strip():
            raise StoreError("empty")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise StoreError("too_long")
        if len(self._reqs) >= MAX_PENDING:
            raise StoreError("busy")
        request = {
            "id": uuid.uuid4().hex,
            "text": text,
            "device_id": device_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "language": language,
            "ts": time.time(),
        }
        fut = asyncio.get_running_loop().create_future()
        self._reqs[request["id"]] = {
            "request": request, "claimed": False, "late": False,
            "t0": self._clock(), "fut": fut,
        }
        self._order.append(request["id"])
        self._wake()
        return request

    def _wake(self):
        while self._waiters and self._order:
            waiter = self._waiters.pop(0)
            if waiter.done():
                continue
            rec = self._reqs[self._order.pop(0)]
            rec["claimed"] = True
            waiter.set_result(rec["request"])

    async def next(self, wait_s=0):
        """Oldest unclaimed request, or None after wait_s (capped at 30)."""
        self._sweep()
        try:
            wait_s = max(0.0, min(float(wait_s), MAX_WAIT_S))
        except (TypeError, ValueError):
            wait_s = 0.0
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        self._wake()
        if not waiter.done():
            try:
                await asyncio.wait_for(asyncio.shield(waiter), wait_s)
            except asyncio.TimeoutError:
                pass
            finally:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)
        if waiter.done() and not waiter.cancelled():
            return waiter.result()
        waiter.cancel()
        return None

    def deliver(self, rid, text):
        """Hand the answer to the waiter. False for unknown or expired ids."""
        self._sweep()
        rec = self._reqs.get(rid)
        if rec is None or not isinstance(text, str):
            return False
        text = text[:MAX_REPLY_CHARS]
        if rec["late"]:
            self._drop(rid)
            if self.on_late_reply:
                self.on_late_reply(rec["request"], text)
            return True
        if rec["fut"].done():
            return False
        rec["fut"].set_result(text)
        self._reqs.pop(rid, None)
        return True

    async def wait_reply(self, rid, timeout):
        """The reply text, or None on timeout (the request then counts as late)."""
        rec = self._reqs.get(rid)
        if rec is None:
            return None
        try:
            return await asyncio.wait_for(asyncio.shield(rec["fut"]), timeout)
        except asyncio.TimeoutError:
            if rid in self._reqs:
                if rec["claimed"]:
                    rec["late"] = True
                else:  # review 1 MAJOR-3: the Mini never took it; never promise
                    self._drop(rid)
            return None

    def is_late(self, rid):
        """True when the Mini took the request and its answer is still owed."""
        rec = self._reqs.get(rid)
        return bool(rec and rec["late"])
