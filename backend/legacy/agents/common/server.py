"""Serve one council agent on SLIM (A2A over the app-sdk), Lungo-style."""
import asyncio
import logging

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from agntcy_app_sdk.factory import AgntcyFactory
from agntcy_app_sdk.semantic.a2a.server.experimental_patterns import A2AExperimentalServer

from agents.common.cards import build_card
from agents.common.config import SILENT
from agents.common.executor import CouncilExecutor

logger = logging.getLogger("council.server")

# Make SILENT replies a no-op: returning None makes the SLIM transport skip the
# group publish ("Received empty output from callback, skipping response").
_orig_handle = A2AExperimentalServer.handle_message


async def _handle(self, message, **kw):
    out = await _orig_handle(self, message, **kw)
    if out is not None and SILENT.encode() in (out.payload or b""):
        return None
    return out


A2AExperimentalServer.handle_message = _handle


async def serve(name: str, goal: str, executor=None) -> None:
    logging.basicConfig(level=logging.INFO)
    card = build_card(name, goal)
    handler = DefaultRequestHandler(
        agent_executor=executor or CouncilExecutor(name, goal), task_store=InMemoryTaskStore()
    )
    factory = AgntcyFactory(f"council.{name}", enable_tracing=False)
    session = factory.create_app_session()
    await session.add_a2a_card(card, handler).start(keep_alive=False)
    logger.info("Agent ready: %s", card.url)
    await asyncio.Event().wait()  # keep the process alive
