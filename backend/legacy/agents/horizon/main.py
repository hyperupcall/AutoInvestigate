import asyncio

from agents.common.server import serve

NAME = "horizon"
GOAL = "Balance near-term payoff vs long-term bets"

if __name__ == "__main__":
    asyncio.run(serve(NAME, GOAL))
