"""Artifacts built from a real evaluation report (backend/examples), with the model calls faked."""
import json
import os
import unittest
from unittest import mock

from artifactfactory import evaluation as ev

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT = json.load(open(os.path.join(ROOT, "backend", "examples", "homomorphic-encryption.json")))
REPORT_WITH_PAPERS = dict(REPORT, sources={"papers": [
    {"id": "2305.05904", "title": "Revisiting Fully Homomorphic Encryption Schemes", "authors": ["A", "B", "C"],
     "year": "2023", "url": "https://arxiv.org/abs/2305.05904", "abstract": "A survey.", "cited_by": ["critical_reviewer"]}]})


class TestLiteratureReview(unittest.TestCase):
    def test_built_from_the_report_without_a_model(self):
        with mock.patch.object(ev, "chat", return_value=None):
            md = ev.literature_review_md(REPORT_WITH_PAPERS, "HE", "homomorphic encryption")
        self.assertIn(REPORT["verdict"]["headline"], md)
        self.assertIn("arXiv:2305.05904", md)
        self.assertIn("## What each group concluded", md)
        self.assertNotIn("placeholder", md.lower())

    def test_synthesis_drops_sentences_citing_unknown_papers(self):
        text = "Schemes are surveyed [arXiv:2305.05904]. A made-up result exists [arXiv:9999.99999]."
        with mock.patch.object(ev, "chat", return_value=text):
            out = ev._synthesis(REPORT_WITH_PAPERS, "idea")
        self.assertIn("2305.05904", out)
        self.assertNotIn("9999.99999", out)


class TestSourceRepo(unittest.TestCase):
    def test_valid_script_is_used(self):
        reply = json.dumps({"goal": "g", "hypothesis": "h", "method": ["a", "b"], "success_criteria": ["s"],
                            "stop_criteria": ["x"], "experiment_py": "def main():\n    print('ok')\n\nmain()\n",
                            "requirements": ["numpy"]})
        with mock.patch.object(ev, "chat", return_value=reply):
            out = ev.source_repo(REPORT, "HE", "homomorphic encryption")
        self.assertIn("experiment.py", out["files"])
        self.assertEqual(out["files"]["requirements.txt"], "numpy\n")
        self.assertIn(REPORT["verdict"]["headline"], out["readme"])

    def test_broken_script_falls_back_to_placeholders(self):
        reply = json.dumps({"experiment_py": "def main(:\n"})
        with mock.patch.object(ev, "chat", return_value=reply):
            self.assertIsNone(ev.source_repo(REPORT, "HE", "idea"))

    def test_no_run_id_means_no_fetch(self):
        self.assertIsNone(ev.run_id_of({"metadata": {}}))
        self.assertIsNone(ev.run_id_of({"metadata": {"evaluation_run_id": "../../etc"}}))


if __name__ == "__main__":
    unittest.main()
