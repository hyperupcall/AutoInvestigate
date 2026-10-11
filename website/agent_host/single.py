"""One agent = one process = one SLIM identity (the SDK keeps a single SLIM connection per process)."""
import asyncio
import logging
import sys

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from agntcy_app_sdk.factory import AgntcyFactory
from agntcy_app_sdk.semantic.a2a.server.experimental_patterns import A2AExperimentalServer

from agent_host.executor import AgentWorker
from deliberation.slim import SILENT, agent_card

# A SILENT answer must not be posted to the group: returning None makes the SLIM transport skip it.
_orig_handle = A2AExperimentalServer.handle_message


async def _handle(self, message, **kw):
    out = await _orig_handle(self, message, **kw)
    if out is not None and SILENT.encode() in (out.payload or b""):
        return None
    return out


A2AExperimentalServer.handle_message = _handle


async def main(agent_id: str) -> None:
    logging.basicConfig(level=logging.INFO)
    handler = DefaultRequestHandler(agent_executor=AgentWorker(agent_id), task_store=InMemoryTaskStore())
    factory = AgntcyFactory(f"deliberation.{agent_id}", enable_tracing=False)
    await factory.create_app_session().add_a2a_card(agent_card(agent_id), handler).start(keep_alive=False)
    logging.getLogger("deliberation.agent").info("agent ready: %s", agent_id)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
