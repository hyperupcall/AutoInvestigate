import os
from dataclasses import dataclass, field
from typing import Dict

# The project root is the directory that contains the `ideation` package (website/).
# Defaults are anchored here so the SQLite database and the frontend always resolve
# to the same place no matter which directory the daemon is started from.
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PACKAGE_DIR)
REPO_ROOT = os.path.dirname(PROJECT_ROOT)

# The SQLite database lives in a directory that is mounted as a volume in Docker,
# so the watchlist, the signals, the ideas and the memory survive a rebuild.
DEFAULT_DATA_DIR = os.path.join(REPO_ROOT, "_ideation-data")
DEFAULT_FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8091
    data_dir: str = DEFAULT_DATA_DIR            # where ideation.db lives (a Docker volume)
    frontend_dir: str = DEFAULT_FRONTEND_DIR    # where the Ideation View page + assets live
    poll_interval_seconds: int = 900            # how often the scheduler runs a cycle
    max_cost_usd: float = 0.50                  # per session, and per cycle
    autostart: bool = True                      # start the scheduler with the daemon
    model: str = "openai/gpt-oss-120b"          # default model for the ideation agents
    thinking: bool = True                       # default thinking mode for agents without their own
    agent_models: Dict[str, str] = field(default_factory=dict)      # per-agent model overrides (agent id -> model)
    agent_thinking: Dict[str, bool] = field(default_factory=dict)   # per-agent thinking overrides (agent id -> bool)
    topic_model: str = ""                       # model that drafts a topic from a description ("" = the default model)
    topic_thinking: bool = True                 # thinking mode for the topic drafter
    rounds: int = 2                             # refinement rounds per session
    signals_per_topic: int = 12                 # newest signals fed to a session

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "ideation.db")

    @classmethod
    def from_env(cls) -> "Config":
        def flag(name: str, default: bool) -> bool:
            raw = os.environ.get(name)
            if raw is None:
                return default
            return raw.strip().lower() not in ("0", "false", "no", "off", "")

        return cls(
            host=os.environ.get("ID_HOST", "127.0.0.1"),
            port=int(os.environ.get("ID_PORT", "8091")),
            data_dir=os.environ.get("ID_DATA_DIR", DEFAULT_DATA_DIR),
            frontend_dir=os.environ.get("ID_FRONTEND_DIR", DEFAULT_FRONTEND_DIR),
            poll_interval_seconds=int(os.environ.get("ID_POLL_INTERVAL", "900")),
            max_cost_usd=float(os.environ.get("ID_MAX_COST", "0.50")),
            autostart=flag("ID_AUTOSTART", True),
            model=os.environ.get("ID_MODEL", "openai/gpt-oss-120b"),
            rounds=int(os.environ.get("ID_ROUNDS", "2")),
            signals_per_topic=int(os.environ.get("ID_SIGNALS_PER_TOPIC", "12")),
        )
