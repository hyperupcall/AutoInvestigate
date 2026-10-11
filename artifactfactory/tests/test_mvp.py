"""The prototype page: cleaned, made network-free, and always built (fallback page when generation fails)."""
import unittest
from unittest import mock

from artifactfactory import mvp

GOOD = """Here you go:
```html
<!DOCTYPE html><html><head><title>X</title>
<script src="https://cdn.example.com/lib.js"></script>
<link rel="stylesheet" href="//fonts.example.com/a.css">
<meta http-equiv="refresh" content="0;url=https://evil.example">
</head><body><a href="https://other.example/x">x</a><iframe src="https://x.example"></iframe>
<canvas id="c"></canvas><script>document.title = 'ok';</script></body></html>
```"""


class TestClean(unittest.TestCase):
    def test_strips_external_resources_and_injects_csp(self):
        doc, problem = mvp.clean(GOOD)
        self.assertEqual(problem, "")
        self.assertTrue(doc.startswith("<!DOCTYPE html>"))
        for bad in ("cdn.example.com", "fonts.example.com", "evil.example", "other.example", "<iframe"):
            self.assertNotIn(bad, doc)
        self.assertIn("Content-Security-Policy", doc)
        self.assertIn("connect-src 'none'", doc)
        self.assertIn("document.title = 'ok'", doc)

    def test_rejects_network_use_and_incomplete_pages(self):
        self.assertIsNone(mvp.clean("<html><body><script>fetch('/x')</script></body></html>")[0])
        self.assertIsNone(mvp.clean("<html><body>no script</body></html>")[0])
        self.assertIsNone(mvp.clean("<html><body><script>")[0])
        self.assertIsNone(mvp.clean(None)[0])

    def test_generation_failure_still_gives_a_safe_page(self):
        with mock.patch.object(mvp.evaluation, "chat", return_value=None):
            page, generated, note = mvp.generate("an <idea>", None)
        self.assertFalse(generated)
        self.assertIn("an &lt;idea&gt;", page)          # escaped
        self.assertIn("Content-Security-Policy", page)

    def test_entry_file(self):
        self.assertEqual(mvp.entry_file(["a/README.md", "a/index.html"]), "a/index.html")
        self.assertIsNone(mvp.entry_file(["a/README.md"]))


if __name__ == "__main__":
    unittest.main()
