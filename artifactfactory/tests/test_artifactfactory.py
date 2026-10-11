import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from artifactfactory.api import make_handler
from artifactfactory.config import Config
from artifactfactory.service import Service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config = Config(data_dir=self.tmp)
        self.service = Service(self.config)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _wait_job(self, job_id, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.service.get_job(job_id)
            if job and job["status"] in ("succeeded", "failed"):
                return job
            time.sleep(0.05)
        self.fail("job did not finish in time")

    def test_validated_idea_creates_plan(self):
        result = self.service.add_idea("A quantum-safe key exchange service.")
        plan = result["plan"]
        self.assertIsNotNone(plan)
        self.assertTrue(plan["id"].startswith("plan-"))
        self.assertGreaterEqual(len(plan["artifact_specs"]), 5)
        self.assertEqual(result["idea"]["plan_id"], plan["id"])

    def test_unvalidated_idea_has_no_plan(self):
        result = self.service.add_idea("Rough idea", validated=False)
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["idea"]["plan_id"])

    def test_get_plan_round_trips(self):
        result = self.service.add_idea("Edge inference for factories.")
        plan_id = result["plan"]["id"]
        fetched = self.service.get_plan(plan_id)
        assert fetched is not None
        self.assertEqual(fetched["id"], plan_id)
        self.assertEqual(fetched["idea_text"], "Edge inference for factories.")

    def test_implementation_succeeds(self):
        result = self.service.add_idea("Homomorphic encryption toolkit.")
        plan_id = result["plan"]["id"]
        job = self.service.start_implementation(plan_id)
        assert job is not None
        final = self._wait_job(job["id"])
        self.assertEqual(final["status"], "succeeded")
        plan = self.service.get_plan(plan_id)
        assert plan is not None
        self.assertEqual(plan["status"], "implemented")
        types = {a["type"] for a in plan["artifacts"]}
        self.assertIn("source_repository", types)
        self.assertIn("tarball", types)
        self.assertIn("literature_review", types)

    def test_download_tarball(self):
        result = self.service.add_idea("Federated learning scheduler.")
        plan_id = result["plan"]["id"]
        job = self.service.start_implementation(plan_id)
        assert job is not None
        self._wait_job(job["id"])
        plan = self.service.get_plan(plan_id)
        assert plan is not None
        tarball = next(a for a in plan["artifacts"] if a["type"] == "tarball")
        dl = self.service.download_artifact(tarball["id"])
        assert dl is not None
        filename, _content_type, data = dl
        self.assertTrue(filename.endswith(".tar.gz"))
        self.assertGreater(len(data), 0)
        self.assertEqual(data[:2], b"\x1f\x8b")


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config = Config(data_dir=self.tmp, host="127.0.0.1", port=0)
        self.service = Service(self.config)
        handler = make_handler(self.service)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post(self, path, payload):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_http_smoke(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

        status, body = self._post("/ideas", {"text": "Zero-knowledge proof service."})
        self.assertEqual(status, 201)
        plan_id = body["plan"]["id"]

        status, plan = self._get(f"/plans/{plan_id}")
        self.assertEqual(status, 200)
        self.assertEqual(plan["id"], plan_id)

        status, job = self._post(f"/plans/{plan_id}/implement", {})
        self.assertEqual(status, 202)
        job_id = job["id"]

        deadline = time.time() + 30
        final = None
        while time.time() < deadline:
            _, final = self._get(f"/jobs/{job_id}")
            if final["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.05)
        assert final is not None
        self.assertEqual(final["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
