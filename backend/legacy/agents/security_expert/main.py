import asyncio

from agents.common.expert import ExpertExecutor
from agents.common.server import serve

NAME = "security_expert"
ROLE = "Outside expert on security, cryptography and identity standards"

if __name__ == "__main__":
    asyncio.run(serve(NAME, ROLE, executor=ExpertExecutor(NAME, ROLE)))
