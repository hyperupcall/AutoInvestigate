"""Orchestrator's SLIM client. One call opens a SLIM group containing the target agents, posts one command,
collects the replies, and closes the group. The orchestrator relays and records; agents do the thinking."""
import asyncio
import json
import logging
from uuid import uuid4

from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart
from agntcy_app_sdk.semantic.a2a import ClientConfig, SlimTransportConfig
from agntcy_app_sdk.semantic.a2a.client.factory import A2AClientFactory

from deliberation.slim import GROUP, NAMESPACE, SLIM_SECRET, SLIM_SERVER, agent_card, identifier

logger = logging.getLogger("deliberation.bus")


class Bus:
    def __init__(self):
        self.client = None

    async def connect(self, any_agent_id: str) -> None:
        cfg = ClientConfig(slim_config=SlimTransportConfig(
            endpoint=f"http://{SLIM_SERVER}", name=f"{NAMESPACE}/{GROUP}/orchestrator",
            shared_secret_identity=SLIM_SECRET))
        self.client = await A2AClientFactory(cfg).create(agent_card(any_agent_id))

    async def ask(self, members: list[str], cmd: dict, expect: list[str], timeout: float = 120,
                  on_open=None, on_reply=None) -> dict[str, dict]:
        """Post `cmd` to a SLIM group of `members`; return {agent_id: reply} for the agents in `expect`."""
        cmd = {**cmd, "cmd": uuid4().hex, "to": expect}
        request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(
            message=Message(messageId=str(uuid4()), role=Role.user, parts=[Part(TextPart(text=json.dumps(cmd)))])))
        got: dict[str, dict] = {}
        channel = str(uuid4())
        if on_open:
            on_open(channel, members)
        # The SDK arms an asyncio.timeout inside an async generator; if it fires between iterations it cancels the
        # task instead of raising TimeoutError. Running the exchange in its own task contains that: a cancel coming
        # from inside the SDK only ends this exchange, while a real Stop (our own task cancelled) still propagates.
        inner = asyncio.create_task(self._collect(request, channel, members, cmd["cmd"], expect, timeout, got, on_reply))
        try:
            await inner
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                inner.cancel()
                raise
            logger.warning("SLIM exchange %s ended early inside the SDK; got %d of %d replies", channel[:8], len(got), len(expect))
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning("timed out waiting for %s", sorted(set(expect) - set(got)))
        return got

    async def _collect(self, request, channel, members, cmd_id, expect, timeout, got, on_reply=None) -> None:
        stream = self.client.start_streaming_groupchat(
            init_message=request, group_channel=channel, participants=[identifier(m) for m in members],
            end_message="__never__", timeout=timeout)
        try:
            async for resp in stream:
                try:
                    parts = resp.root.result.parts
                except Exception:
                    continue
                for p in parts:
                    try:
                        r = json.loads(getattr(p.root, "text", ""))
                    except Exception:
                        continue
                    if isinstance(r, dict) and r.get("kind") == "reply" and r.get("cmd") == cmd_id and r.get("agent") in expect \
                            and r["agent"] not in got:
                        got[r["agent"]] = r
                        if on_reply:  # let the caller log each reply the moment it arrives
                            on_reply(r)
                if len(got) == len(expect):
                    break
        finally:
            try:
                await stream.aclose()
            except BaseException:
                pass
