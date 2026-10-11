import asyncio

from agents.common.server import serve

NAME = "tech_risk"
GOAL = "Avoid ideas likely to fail technically"

if __name__ == "__main__":
    asyncio.run(serve(NAME, GOAL))
