import io
import os
import threading
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from .artifacts import BuildContext, get_builder
from .models import Idea, Job, new_id, now_iso
from .planner import create_plan as build_plan
from .runtime import Runtime
from .storage import build_storage
from .store import Store


class Service:
    def __init__(self, config):
        self.config = config
        self.store = Store(os.path.join(config.data_dir, "state.json"))
        self.storage = build_storage(config)
        self.runtime = Runtime(self.storage, getattr(config, "run_host", "127.0.0.1"))
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ ideas
    def add_idea(self, text: str, title: str = "", validated: bool = True,
                 metadata: Optional[Dict[str, Any]] = None,
                 options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        idea = Idea(
            id=new_id("idea"),
            text=text,
            title=title or "",
            validated=bool(validated),
            metadata=metadata or {},
        )
        idea_dict = idea.to_dict()
        plan_dict = None
        if validated:
            plan_dict = self.create_plan(idea_dict, options)
            idea_dict["plan_id"] = plan_dict["id"]
        self.store.put("ideas", idea_dict)
        return {"idea": idea_dict, "plan": plan_dict}

    def create_plan(self, idea_dict: Dict[str, Any],
                    options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        plan = build_plan(idea_dict, options)
        self.store.put("plans", plan)
        return plan

    def list_ideas(self) -> List[Dict[str, Any]]:
        return self.store.list("ideas")

    def get_idea(self, id: str) -> Optional[Dict[str, Any]]:
        return self.store.get("ideas", id)

    # ------------------------------------------------------------------ plans
    def list_plans(self) -> List[Dict[str, Any]]:
        return self.store.list("plans")

    def get_plan(self, id: str) -> Optional[Dict[str, Any]]:
        plan = self.store.get("plans", id)
        if plan is None:
            return None
        plan = dict(plan)
        artifacts = [self.store.get("artifacts", aid) for aid in plan.get("artifact_ids", [])]
        plan["artifacts"] = [a for a in artifacts if a is not None]
        return plan

    # --------------------------------------------------------- implementation
    def start_implementation(self, plan_id: str) -> Optional[Dict[str, Any]]:
        plan = self.store.get("plans", plan_id)
        if plan is None:
            return None
        job = Job(id=new_id("job"), plan_id=plan_id)
        job_dict = job.to_dict()
        with self._lock:
            self._jobs[job_dict["id"]] = job_dict
        self.store.update("plans", plan_id, status="implementing", updated_at=now_iso())
        thread = threading.Thread(target=self._run_job, args=(job_dict["id"],), daemon=True)
        thread.start()
        return job_dict

    def _run_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        plan = self.store.get("plans", job["plan_id"])
        if plan is None:
            self._set_job(job_id, status="failed", error="plan not found",
                          finished_at=now_iso())
            return
        idea = self.store.get("ideas", plan["idea_id"]) or {}
        self._set_job(job_id, status="running", started_at=now_iso())

        base_key = f"plans/{plan['id']}"
        built: List[Dict[str, Any]] = []
        try:
            ctx = BuildContext(
                plan=plan, idea=idea, storage=self.storage,
                base_key=base_key, built=built, job_id=job_id,
            )
            for spec in plan.get("artifact_specs", []):
                builder = get_builder(spec["type"])
                artifact = builder.build(ctx, spec)
                self.store.put("artifacts", artifact)
                built.append(artifact)
                job["artifact_ids"].append(artifact["id"])
                plan["artifact_ids"].append(artifact["id"])
                self._mark_spec(plan, spec, artifact)
                self.store.update(
                    "plans", plan["id"],
                    artifact_ids=plan["artifact_ids"],
                    artifact_specs=plan["artifact_specs"],
                    updated_at=now_iso(),
                )
            self.store.update("plans", plan["id"], status="implemented", updated_at=now_iso())
            self._set_job(job_id, status="succeeded",
                          artifact_ids=job["artifact_ids"], finished_at=now_iso())
        except Exception as exc:  # noqa: BLE001 - report any failure to the job
            self.store.update("plans", plan["id"], status="failed", updated_at=now_iso())
            self._set_job(job_id, status="failed", error=str(exc),
                          artifact_ids=job["artifact_ids"], finished_at=now_iso())

    @staticmethod
    def _mark_spec(plan: Dict[str, Any], spec: Dict[str, Any],
                   artifact: Dict[str, Any]) -> None:
        for s in plan.get("artifact_specs", []):
            if s is spec or (s.get("type") == spec.get("type")
                             and s.get("name") == spec.get("name")):
                s["status"] = "built"
                s["artifact_id"] = artifact["id"]
                break

    def _set_job(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(fields)

    # ------------------------------------------------------------------- jobs
    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(j) for j in self._jobs.values()]

    def get_job(self, id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(id)
            return dict(job) if job is not None else None

    # -------------------------------------------------------------- artifacts
    def get_artifact(self, id: str) -> Optional[Dict[str, Any]]:
        return self.store.get("artifacts", id)

    def download_artifact(self, id: str) -> Optional[Tuple[str, str, bytes]]:
        artifact = self.store.get("artifacts", id)
        if artifact is None:
            return None
        files = artifact.get("files", [])
        if len(files) == 1 and files[0].endswith(".tar.gz"):
            data = self.storage.get_bytes(files[0])
            return (os.path.basename(files[0]), "application/gzip", data)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fkey in files:
                if self.storage.exists(fkey):
                    zf.writestr(fkey, self.storage.get_bytes(fkey))
        filename = f"{artifact.get('name') or artifact['type']}.zip"
        return (filename, "application/zip", buf.getvalue())

    # -------------------------------------------------------- run / stop server
    def start_artifact_server(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Run a built artifact as a local HTTP server; None if the artifact is unknown."""
        artifact = self.store.get("artifacts", artifact_id)
        if artifact is None:
            return None
        return self.runtime.start(artifact)

    def stop_artifact_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        return self.runtime.stop(server_id)

    def get_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        return self.runtime.get(server_id)

    def list_servers(self) -> List[Dict[str, Any]]:
        return self.runtime.list()
