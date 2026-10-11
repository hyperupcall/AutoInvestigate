"""AGNTCY/SLIM glue shared by the agent host and the orchestrator (patterns copied from coffeeAGNTCY)."""
import os

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

SLIM_SERVER = os.getenv("SLIM_SERVER", "localhost:46357")
SLIM_SECRET = os.getenv("SLIM_SHARED_SECRET", "")
NAMESPACE, GROUP = "deliberation", "agents"
SILENT = "__SILENT__"  # executor output meaning "do not post to the group"


def agent_card(agent_id: str, description: str = "") -> AgentCard:
    url = f"slim://{SLIM_SERVER}/{NAMESPACE}/{GROUP}/{agent_id}"
    return AgentCard(
        name=f"{agent_id} evaluator", id=agent_id, description=description or agent_id, version="1.0.0",
        defaultInputModes=["text"], defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[AgentSkill(id="evaluate", name="Evaluate", description="Discuss and evaluate an idea",
                           tags=["evaluation"], examples=["Evaluate this idea."])],
        supportsAuthenticatedExtendedCard=False, preferred_transport="slim", url=url,
        additional_interfaces=[AgentInterface(transport="slim", url=url)])


def identifier(agent_id: str) -> str:
    from agntcy_app_sdk import get_agent_identifier
    return get_agent_identifier(agent_card(agent_id))
