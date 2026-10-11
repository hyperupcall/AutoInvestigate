import asyncio

from agents.common.expert import ExpertExecutor
from agents.common.server import serve

NAME = "specialist_on_demand"
ROLE = "Generated specialist: takes whatever role the asking agent names"

if __name__ == "__main__":
    asyncio.run(serve(NAME, ROLE, executor=ExpertExecutor(NAME, ROLE)))
