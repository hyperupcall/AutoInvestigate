import os

SLIM_SERVER = os.getenv("SLIM_SERVER", "localhost:46357")
SLIM_SHARED_SECRET = os.getenv("SLIM_SHARED_SECRET", "")
NAMESPACE, GROUP = "council", "agents"
SILENT = "__SILENT__"  # executor output meaning "do not post to the group"
EVENTS_LOG = os.getenv("EVENTS_LOG", "logs/events.jsonl")
