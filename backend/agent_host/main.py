"""Agent host (supervisor): runs one process per configured agent, restarts any that die, and starts
new ones when agents are added in /settings (the settings file is re-read every few seconds)."""
import asyncio
import logging
import sys

from council import settings

logger = logging.getLogger("council.host")


def wanted_ids() -> list[str]:
    s = settings.load()
    return list(dict.fromkeys(a["id"] for g in s["groups"] for a in g["agents"]))


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    procs: dict[str, asyncio.subprocess.Process] = {}
    while True:
        want = wanted_ids()
        for agent_id in want:
            p = procs.get(agent_id)
            if p is None or p.returncode is not None:
                if p is not None:
                    logger.warning("%s exited with %s, restarting", agent_id, p.returncode)
                procs[agent_id] = await asyncio.create_subprocess_exec(sys.executable, "-m", "agent_host.single", agent_id)
                logger.info("started %s (pid %s, %d running)", agent_id, procs[agent_id].pid, len(procs))
        for agent_id in [i for i in procs if i not in want]:  # removed from settings: stop it
            procs.pop(agent_id).terminate()
            logger.info("stopped %s", agent_id)
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
