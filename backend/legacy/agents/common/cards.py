from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from agents.common.config import GROUP, NAMESPACE, SLIM_SERVER


def build_card(agent_id: str, goal: str) -> AgentCard:
    url = f"slim://{SLIM_SERVER}/{NAMESPACE}/{GROUP}/{agent_id}"
    return AgentCard(
        name=f"{agent_id} council agent",
        id=agent_id,
        description=goal,
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[AgentSkill(id="deliberate", name="Deliberate", description=goal,
                           tags=["council"], examples=["Rank the ideas."])],
        supportsAuthenticatedExtendedCard=False,
        preferred_transport="slim",
        url=url,
        additional_interfaces=[AgentInterface(transport="slim", url=url)],
    )
