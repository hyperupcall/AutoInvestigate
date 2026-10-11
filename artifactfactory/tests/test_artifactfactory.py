import json
import io
import os
import shutil
import tarfile
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import http.client
from http.server import ThreadingHTTPServer

from artifactfactory.api import make_handler
from artifactfactory.config import Config
from artifactfactory.service import Service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config = Config(data_dir=self.tmp,
                             artifacts_dir=os.path.join(self.tmp, "artifacts"))
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
        # Artifacts must land under the configured artifacts directory.
        prefix = "file://" + self.config.artifacts_dir
        for a in plan["artifacts"]:
            self.assertTrue(a["uri"].startswith(prefix), a["uri"])

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

    def test_prototype_downloads_as_a_single_html_file(self):
        # What the frontend's Execute -> asks for: one prototype, a single self-contained HTML file.
        result = self.service.add_idea("A homomorphic encryption toolkit.",
                                       options={"artifacts": ["mvp_prototype"]})
        plan_id = result["plan"]["id"]
        job = self.service.start_implementation(plan_id)
        assert job is not None
        self._wait_job(job["id"])
        plan = self.service.get_plan(plan_id)
        assert plan is not None
        proto = next(a for a in plan["artifacts"] if a["type"] == "mvp_prototype")
        self.assertEqual(proto["files"], [proto["key"] + "/index.html"])
        dl = self.service.download_artifact(proto["id"])
        assert dl is not None
        filename, content_type, data = dl
        self.assertEqual(filename, "index.html")
        self.assertTrue(content_type.startswith("text/html"), content_type)
        self.assertIn(b"<!DOCTYPE html>", data)

    def test_execution_plan_tarballs_the_generated_prototype(self):
        # The tarball builder packages every artifact built so far, including the prototype.
        result = self.service.add_idea("A homomorphic encryption toolkit.",
                                       options={"artifacts": ["mvp_prototype", "tarball"]})
        plan_id = result["plan"]["id"]
        job = self.service.start_implementation(plan_id)
        assert job is not None
        self._wait_job(job["id"])
        plan = self.service.get_plan(plan_id)
        assert plan is not None
        tarball = next(a for a in plan["artifacts"] if a["type"] == "tarball")
        dl = self.service.download_artifact(tarball["id"])
        assert dl is not None
        _filename, _content_type, data = dl
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            names = tar.getnames()
        self.assertTrue(any(n.endswith("index.html") for n in names), names)

    def test_run_and_stop_artifact_server(self):
        result = self.service.add_idea("A homomorphic encryption toolkit.",
                                       options={"artifacts": ["mvp_prototype"]})
        plan_id = result["plan"]["id"]
        job = self.service.start_implementation(plan_id)
        assert job is not None
        self._wait_job(job["id"])
        plan = self.service.get_plan(plan_id)
        assert plan is not None
        proto = next(a for a in plan["artifacts"] if a["type"] == "mvp_prototype")

        server = self.service.start_artifact_server(proto["id"])
        assert server is not None
        self.assertEqual(server["status"], "running")
        self.assertTrue(server["url"].startswith("http://127.0.0.1:"))
        self.assertEqual(server["path"], f"/run/{server['id']}/")
        try:
            with urllib.request.urlopen(server["url"], timeout=10) as resp:
                body = resp.read().decode("utf-8")
            self.assertIn("<!DOCTYPE html>", body)
        finally:
            stopped = self.service.stop_artifact_server(server["id"])
        assert stopped is not None
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(self.service.list_servers()[0]["status"], "stopped")

    def test_start_server_for_unknown_artifact(self):
        self.assertIsNone(self.service.start_artifact_server("artifact-nope"))
        self.assertIsNone(self.service.stop_artifact_server("server-nope"))


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config = Config(data_dir=self.tmp,
                             artifacts_dir=os.path.join(self.tmp, "artifacts"),
                             host="127.0.0.1", port=0)
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

    def _get_raw(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8")

    def _post(self, path, payload):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _request(self, method, path, origin=None, payload=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = origin
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, dict(resp.headers)

    def test_cors_allows_the_frontend_origin(self):
        origin = "http://localhost:8000"
        status, headers = self._request("OPTIONS", "/ideas", origin=origin)
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), origin)
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))

        status, headers = self._request("GET", "/health", origin=origin)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), origin)

    def test_cors_allows_a_file_page(self):
        # A page opened straight from disk (file://) sends "Origin: null"; the
        # dashboard must still reach the API.
        status, headers = self._request("GET", "/health", origin="null")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "null")

    def test_cors_allows_localhost_on_any_port(self):
        # run.sh can be started on a non-default port.
        origin = "http://localhost:9000"
        status, headers = self._request("GET", "/health", origin=origin)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), origin)

    def test_cors_ignores_unknown_origins(self):
        status, headers = self._request("GET", "/health", origin="http://evil.example")
        self.assertEqual(status, 200)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_keep_alive_after_post_with_body(self):
        # POST /plans/<id>/implement carries a body the route does not read; on a
        # keep-alive connection the leftover bytes must not be parsed as the next
        # request line (which would answer 501).
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", "/ideas", json.dumps({"text": "keep-alive idea"}),
                         {"Content-Type": "application/json"})
            plan_id = json.loads(conn.getresponse().read())["plan"]["id"]

            conn.request("POST", f"/plans/{plan_id}/implement", "{}",
                         {"Content-Type": "application/json"})
            conn.getresponse().read()

            conn.request("GET", f"/plans/{plan_id}")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertEqual(json.loads(resp.read())["id"], plan_id)
        finally:
            conn.close()

    def test_home_serves_the_frontend_dashboard(self):
        # The dashboard is now a frontend page (website/frontend/artifactfactory.html);
        # the daemon serves it and its assets, and the data comes from the JSON API.
        status, content_type, body = self._get_raw("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("Artifact Factory", body)
        self.assertIn("artifactfactory.js", body)

    def test_home_dashboard_assets_are_served(self):
        status, content_type, _ = self._get_raw("/js/artifactfactory.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", content_type)

    def test_ideas_route_lists_evaluations(self):
        self._post("/ideas", {"text": "A homomorphic encryption toolkit."})
        status, body = self._get("/ideas")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["ideas"]), 1)
        self.assertEqual(body["ideas"][0]["text"], "A homomorphic encryption toolkit.")

    def test_ideas_route_is_empty_before_any_evaluation(self):
        status, body = self._get("/ideas")
        self.assertEqual(status, 200)
        self.assertEqual(body["ideas"], [])

    def test_info_route_returns_service_json(self):
        status, body = self._get("/info")
        self.assertEqual(status, 200)
        self.assertEqual(body["service"], "artifactfactory")

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

    def test_run_route_starts_and_stops_a_server(self):
        _, body = self._post("/ideas", {"text": "A homomorphic encryption toolkit.",
                                        "options": {"artifacts": ["mvp_prototype"]}})
        plan_id = body["plan"]["id"]
        _, job = self._post(f"/plans/{plan_id}/implement", {})
        deadline = time.time() + 30
        while time.time() < deadline:
            _, final = self._get(f"/jobs/{job['id']}")
            if final["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.05)
        self.assertEqual(final["status"], "succeeded")

        _, plan = self._get(f"/plans/{plan_id}")
        proto = next(a for a in plan["artifacts"] if a["type"] == "mvp_prototype")

        status, res = self._post(f"/artifacts/{proto['id']}/run", {})
        self.assertEqual(status, 201)
        server = res["server"]
        self.assertEqual(server["status"], "running")

        # The run is reachable through the factory's own port (the proxy path).
        status, content_type, html = self._get_raw(server["path"])
        self.assertEqual(status, 200)
        self.assertIn("html", content_type)
        self.assertIn("<!DOCTYPE html>", html)

        status, res = self._post(f"/servers/{server['id']}/stop", {})
        self.assertEqual(status, 200)
        self.assertEqual(res["server"]["status"], "stopped")

        # A stopped server is no longer served through the proxy.
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get_raw(server["path"])
        self.assertEqual(ctx.exception.code, 409)


if __name__ == "__main__":
    unittest.main()
