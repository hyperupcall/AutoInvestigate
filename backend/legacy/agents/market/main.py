import asyncio

from agents.common.server import serve

NAME = "market"
GOAL = "Pick ideas with clear buyers"

if __name__ == "__main__":
    asyncio.run(serve(NAME, GOAL))
