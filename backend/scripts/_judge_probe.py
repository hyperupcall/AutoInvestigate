import importlib.util, os, json, urllib.request

spec = importlib.util.spec_from_file_location("bench", os.path.join(os.path.dirname(__file__), "benchmark_vs_baseline.py"))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
bench.KEY = bench._key()

rid = "20261011-115155-703f"
rep = bench.http("GET", f"{bench.API}/api/runs/{rid}/report", timeout=300)
council = bench.council_text(rep)
print("COUNCIL TEXT LEN:", len(council))
baseline = "Baseline placeholder report for probing."
try:
    g = bench.judge("An AI fridge that tracks when ingredients inside it expire and alerts the household before they go bad.", council, baseline)
    print("JUDGE OK:", json.dumps(g, indent=2)[:1500])
except Exception as e:
    print("JUDGE FAILED:", type(e).__name__, e)