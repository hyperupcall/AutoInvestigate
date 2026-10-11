import asyncio

from agents.common.server import serve

NAME = "cisco_fit"
GOAL = "Pick ideas that build on Cisco/Outshift areas"

if __name__ == "__main__":
    asyncio.run(serve(NAME, GOAL))
