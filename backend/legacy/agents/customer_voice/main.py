import asyncio

from agents.common.expert import ExpertExecutor
from agents.common.server import serve

NAME = "customer_voice"
ROLE = "Outside expert on what enterprise buyers want and pay for"

if __name__ == "__main__":
    asyncio.run(serve(NAME, ROLE, executor=ExpertExecutor(NAME, ROLE)))
