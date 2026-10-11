"""arXiv sources for the groups that use them (research and private equity by default).

  1. a cheap model writes 3 specific keyword queries for the idea
  2. OpenAlex, restricted to papers hosted on arXiv (fast, generous limits); the arXiv API itself is only a fallback
     because it rate-limits hard (a shared venue network gets 429s quickly). Results are cached per idea.
  3. a cheap model keeps the most relevant papers
The agents get the list and must cite as [arXiv:ID]; deliberation/report.py checks every citation against it."""
import asyncio
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import httpx

from deliberation import openrouter as orr
from deliberation import prompts, settings

ARXIV = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
CITE = re.compile(r"arXiv[:\s]*([0-9]{4}\.[0-9]{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/[0-9]{7})", re.I)


def parse_atom(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    out = []
    for e in root.findall("a:entry", NS):
        url = (e.findtext("a:id", default="", namespaces=NS) or "").strip()
        m = re.search(r"abs/(.+?)(v\d+)?$", url)
        if not m:
            continue
        cat = e.find("arxiv:primary_category", NS)
        out.append({
            "id": m.group(1),
            "title": re.sub(r"\s+", " ", e.findtext("a:title", default="", namespaces=NS)).strip(),
            "authors": [a.findtext("a:name", default="", namespaces=NS) for a in e.findall("a:author", NS)][:3],
            "year": (e.findtext("a:published", default="", namespaces=NS) or "")[:4],
            "url": f"https://arxiv.org/abs/{m.group(1)}",
            "category": cat.get("term") if cat is not None else None,
            "abstract": re.sub(r"\s+", " ", e.findtext("a:summary", default="", namespaces=NS)).strip(),
        })
    return out


def as_prompt(papers: list[dict]) -> str:
    if not papers:
        return ""
    lines = [f"[arXiv:{p['id']}] {p['title']} ({p['year']}; {', '.join(p['authors'])}{' et al.' if len(p['authors']) >= 3 else ''}). "
             f"{p['abstract'][:320]}" for p in papers]
    return ("Papers from arXiv found for this idea. These are the only papers you may cite, as [arXiv:ID]. If you "
            "know a relevant paper that is not listed, describe it without inventing an id.\n" + "\n".join(lines))


def citations(text: str) -> list[str]:
    return [m.group(1) for m in CITE.finditer(text or "")]


OPENALEX = "https://api.openalex.org/works"
OPENALEX_ARXIV = "S4306400194"  # OpenAlex source id of arXiv (Cornell University)
CACHE = os.path.join("data", "sources_cache.json")


def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words = sorted((i, w) for w, idx in inv.items() for i in idx)
    return " ".join(w for _, w in words)


def parse_openalex(data: dict) -> list[dict]:
    out = []
    for w in data.get("results", []):
        url = next((l.get("landing_page_url") for l in w.get("locations") or [] if "arxiv.org/abs/" in (l.get("landing_page_url") or "")), None)
        m = re.search(r"arxiv\.org/abs/(.+?)(v\d+)?$", url or "")
        if not m:
            continue
        out.append({"id": m.group(1), "title": re.sub(r"\s+", " ", w.get("title") or "").strip(),
                    "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])[:3] if a.get("author")],
                    "year": str(w.get("publication_year") or ""), "url": f"https://arxiv.org/abs/{m.group(1)}",
                    "category": ((w.get("primary_topic") or {}).get("field") or {}).get("display_name"),
                    "abstract": _abstract(w.get("abstract_inverted_index"))})
    return out


async def _search(queries: list[str]) -> tuple[list[dict], str]:
    """OpenAlex restricted to arXiv (fast, generous limits); the arXiv API is only a fallback (it rate-limits hard)."""
    headers = {"User-Agent": "research-deliberation/1.0 (hackathon demo)"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as c:
        try:
            rs = await asyncio.gather(*[c.get(OPENALEX, params={
                "search": q, "filter": f"locations.source.id:{OPENALEX_ARXIV}", "per-page": 10,
                "select": "id,title,publication_year,authorships,locations,abstract_inverted_index,primary_topic"}) for q in queries])
            found, seen = [], set()
            for r in rs:
                r.raise_for_status()
                for p in parse_openalex(r.json()):
                    if p["id"] not in seen:
                        seen.add(p["id"])
                        found.append(p)
            if found:
                return found, "openalex"
        except Exception:
            pass
        r = await c.get(ARXIV, params={"search_query": " OR ".join(f"all:({q})" for q in queries), "max_results": 20}, timeout=8)
        r.raise_for_status()
        return parse_atom(r.text), "arxiv"


def _cache_get(idea: str) -> dict | None:
    try:
        with open(CACHE) as f:
            hit = json.load(f).get(idea.strip().lower())
        return hit if hit and time.time() - hit.get("at", 0) < 7 * 86400 else None
    except Exception:
        return None


def _cache_put(idea: str, result: dict) -> None:
    try:
        try:
            with open(CACHE) as f:
                data = json.load(f)
        except Exception:
            data = {}
        data[idea.strip().lower()] = {**result, "at": time.time()}
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


async def find(idea: str, s: dict, budget: orr.RunBudget | None = None) -> dict:
    cached = _cache_get(idea)
    if cached:
        return {k: v for k, v in cached.items() if k != "at"} | {"cached": True}
    cfg = s["sources"]
    key = settings.resolve_key("", s)
    kw = dict(max_tokens=600, reasoning_effort="none", budget=budget)

    def valid_queries(o):
        q = o.get("queries")
        return None if isinstance(q, list) and 1 <= len(q) <= 5 and all(isinstance(x, str) and x.strip() for x in q) else "need 1-5 query strings"
    qobj, _ = await orr.chat_json(cfg["model"], [{"role": "user", "content": prompts.system("sources_queries", IDEA=idea)}], key, valid_queries, **kw)
    queries = [re.sub(r'["()]', " ", q).strip() for q in qobj["queries"]][:3]
    found, provider = await _search(queries)
    if not found:
        return {"queries": queries, "papers": [], "candidates": 0, "provider": provider}
    cands = "\n".join(f"{p['id']}: {p['title']} — {p['abstract'][:200]}" for p in found)
    ids = {p["id"] for p in found}

    def valid_keep(o):
        k = o.get("keep")
        return None if isinstance(k, list) and all(i in ids for i in k) else "keep must list ids from the candidates"
    try:
        kobj, _ = await orr.chat_json(cfg["model"], [{"role": "user", "content": prompts.system(
            "sources_rank", IDEA=idea, CANDIDATES=cands, MAX=str(cfg["max_papers"]))}], key, valid_keep, **kw)
        keep = kobj["keep"][: cfg["max_papers"]]
    except Exception:
        keep = [p["id"] for p in found[: cfg["max_papers"]]]
    by_id = {p["id"]: p for p in found}
    result = {"queries": queries, "papers": [by_id[i] for i in keep], "candidates": len(found), "provider": provider}
    if result["papers"]:
        _cache_put(idea, result)
    return result


async def find_safely(idea: str, s: dict, budget=None, timeout: float = 25) -> dict:
    """Never let source finding break or stall a run."""
    try:
        return await asyncio.wait_for(find(idea, s, budget), timeout)
    except Exception as e:
        return {"queries": [], "papers": [], "candidates": 0, "error": f"{type(e).__name__}: {e}"[:200]}
