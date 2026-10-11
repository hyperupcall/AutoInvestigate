"""Source adapters — how the daemon reads the internet.

Each adapter takes a topic and returns a list of signals:
    {source, title, url, text, published_at}

They are deliberately fail-safe: a dead feed, a rate limit or a parse error
returns an empty list rather than raising, so one bad source never stops a cycle.
Official/free APIs are preferred (arXiv, Hacker News Algolia, Reddit JSON, Google
News RSS); no scraping, no keys.
"""
import hashlib
import html
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import httpx

TIMEOUT = 20
UA = "AutoInvestigate-Ideation/0.1 (+https://github.com/)"


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _hash(url: str, title: str) -> str:
    key = (url or "").strip().lower() or _clean(title).lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _signal(source: str, title: str, url: str, text: str, published: str = "") -> Dict[str, Any]:
    return {"source": source, "title": _clean(title), "url": url, "text": _clean(text),
            "published_at": published or None, "hash": _hash(url, title)}


def _query(topic: Dict[str, Any]) -> str:
    keywords = topic.get("keywords") or []
    return " OR ".join(keywords[:3]) if keywords else topic.get("name", "")


# --------------------------------------------------------------------- arXiv
def arxiv(topic: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    q = _query(topic).replace(" OR ", " ").strip() or topic.get("name", "")
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"all:{q}", "sortBy": "submittedDate",
              "sortOrder": "descending", "max_results": limit}
    try:
        r = httpx.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("a:entry", ns):
        title = entry.findtext("a:title", default="", namespaces=ns)
        summary = entry.findtext("a:summary", default="", namespaces=ns)
        link = entry.findtext("a:id", default="", namespaces=ns)
        published = entry.findtext("a:published", default="", namespaces=ns)
        out.append(_signal("arxiv", title, link, summary, published))
    return out


# ---------------------------------------------------------------- Hacker News
def hackernews(topic: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    q = _query(topic).replace(" OR ", " ").strip() or topic.get("name", "")
    url = "https://hn.algolia.com/api/v1/search_by_date"
    try:
        r = httpx.get(url, params={"query": q, "tags": "story", "hitsPerPage": limit},
                      timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception:
        return []
    out = []
    for h in hits:
        title = h.get("title") or h.get("story_title") or ""
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        text = h.get("story_text") or ""
        out.append(_signal("hackernews", title, link, text, h.get("created_at", "")))
    return out


# -------------------------------------------------------------------- Reddit
def reddit(topic: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    q = _query(topic).replace(" OR ", " ").strip() or topic.get("name", "")
    url = "https://www.reddit.com/search.json"
    try:
        r = httpx.get(url, params={"q": q, "sort": "new", "limit": limit},
                      timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        children = r.json().get("data", {}).get("children", [])
    except Exception:
        return []
    out = []
    for c in children:
        d = c.get("data", {})
        title = d.get("title", "")
        link = "https://www.reddit.com" + d.get("permalink", "")
        text = d.get("selftext", "") or d.get("url", "")
        out.append(_signal("reddit", title, link, text, ""))
    return out


# ---------------------------------------------------------------------- News
def news(topic: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    q = _query(topic).replace(" OR ", " ").strip() or topic.get("name", "")
    url = "https://news.google.com/rss/search"
    try:
        r = httpx.get(url, params={"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                      timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception:
        return []
    out = []
    for item in root.iter("item"):
        title = item.findtext("title", default="")
        link = item.findtext("link", default="")
        desc = item.findtext("description", default="")
        published = item.findtext("pubDate", default="")
        out.append(_signal("news", title, link, desc, published))
        if len(out) >= limit:
            break
    return out


ADAPTERS = {"arxiv": arxiv, "hackernews": hackernews, "reddit": reddit, "news": news}


# ------------------------------------------------------------------ trending
# Broad "what is happening right now" material for the topic finder — not tied to a
# topic. These are the same free APIs the adapters use, queried without a keyword.
def _trending_hackernews(limit: int) -> List[Dict[str, Any]]:
    url = "https://hn.algolia.com/api/v1/search"
    try:
        r = httpx.get(url, params={"tags": "front_page", "hitsPerPage": limit},
                      timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception:
        return []
    out = []
    for h in hits:
        title = h.get("title") or h.get("story_title") or ""
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        out.append(_signal("hackernews", title, link, h.get("story_text") or "", h.get("created_at", "")))
    return out


def _trending_arxiv(limit: int) -> List[Dict[str, Any]]:
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.SE OR cat:cs.DC",
              "sortBy": "submittedDate", "sortOrder": "descending", "max_results": limit}
    try:
        r = httpx.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("a:entry", ns):
        out.append(_signal("arxiv",
                           entry.findtext("a:title", default="", namespaces=ns),
                           entry.findtext("a:id", default="", namespaces=ns),
                           entry.findtext("a:summary", default="", namespaces=ns),
                           entry.findtext("a:published", default="", namespaces=ns)))
    return out


def trending(limit: int = 12) -> List[Dict[str, Any]]:
    """The newest front-page stories and papers, with no keyword — the raw material the
    topic finder reads to propose new topics. Fail-safe: a dead source contributes nothing."""
    out: List[Dict[str, Any]] = []
    for fetch in (_trending_hackernews, _trending_arxiv):
        try:
            out.extend(fetch(limit))
        except Exception:
            continue
    return out


def poll_topic(topic: Dict[str, Any], limit_per_source: int = 5) -> List[Dict[str, Any]]:
    """Poll every source the topic enables. Returns the signals found (may be empty)."""
    out: List[Dict[str, Any]] = []
    for source_id in topic.get("sources") or list(ADAPTERS):
        adapter = ADAPTERS.get(source_id)
        if adapter is None:
            continue
        try:
            out.extend(adapter(topic, limit_per_source))
        except Exception:
            continue
    return out
