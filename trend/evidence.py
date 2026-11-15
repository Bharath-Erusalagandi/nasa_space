"""Published evidence for each indicator, found with SerpApi.

For every indicator this asks Google Scholar and Google News, through SerpApi, what has been published about that
change in Zambia, and writes the titles, sources and links to public/evidence/index.json. The mission view lists them
under "What others have found". The search runs here, at build time: the key never reaches the website, and the
website still makes no outside calls.

    SERPAPI_API_KEY=... python trend/evidence.py

Raw responses are cached in trend/cache/serpapi/, so a second run costs no searches. Only titles, sources, years and
links are kept, not the text of the results.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

SERPAPI_URL = "https://serpapi.com/search.json"
REGION = "Zambia"
KEEP = 4

# one plain query per indicator; the region is added to each
QUERIES = {
    "wet_season_rain_mm": "rainfall trend",
    "wet_days": "number of rainy days trend",
    "heavy_rain_days": "heavy rainfall events trend",
    "wettest_day_mm": "extreme daily rainfall trend",
    "rain_onset_day": "onset of the rainy season trend",
    "wet_season_temp_c": "temperature trend rainy season",
    "october_temp_c": "hot season temperature warming trend",
    "wet_season_humidity_pct": "relative humidity trend rainy season",
    "wet_season_soil_wetness_pct": "soil moisture trend rainy season",
}

ENGINES = ("google_scholar", "google_news")


def query_for(key):
    return f"{QUERIES[key]} {REGION}"


def fetch_serpapi(engine, query, api_key, timeout=60):
    params = {"engine": engine, "q": query, "api_key": api_key, "hl": "en"}
    if engine == "google_scholar":
        params["num"] = 10
    with urllib.request.urlopen(f"{SERPAPI_URL}?{urllib.parse.urlencode(params)}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def payload_problem(payload):
    if not isinstance(payload, dict):
        return "the response is not a JSON object"
    if payload.get("error"):
        return str(payload["error"])[:200]
    return None


def _year(text):
    for word in str(text or "").replace(",", " ").replace("-", " ").split():
        if len(word) == 4 and word.isdigit() and 1900 <= int(word) <= 2100:
            return int(word)
    return None


def _clean(text):
    return " ".join(str(text or "").split())


def parse_scholar(payload, keep=KEEP):
    out = []
    for row in payload.get("organic_results") or []:
        title, link = _clean(row.get("title")), row.get("link")
        if not title or not isinstance(link, str) or not link.startswith("http"):
            continue
        summary = _clean((row.get("publication_info") or {}).get("summary"))
        out.append({"title": title, "link": link, "source": summary or None, "year": _year(summary)})
        if len(out) == keep:
            break
    return out


def parse_news(payload, keep=KEEP):
    out = []
    for row in payload.get("news_results") or []:
        # a result can be a group of stories; take its first story
        if not row.get("link") and row.get("stories"):
            row = row["stories"][0]
        title, link = _clean(row.get("title")), row.get("link")
        if not title or not isinstance(link, str) or not link.startswith("http"):
            continue
        source = row.get("source")
        name = _clean(source.get("name") if isinstance(source, dict) else source)
        # iso_date is "2025-11-02T08:00:00Z"; the plain date field is in a longer local format
        when = _clean(row.get("iso_date"))[:10] or _clean(row.get("date"))
        out.append({"title": title, "link": link, "source": name or None, "date": when or None})
        if len(out) == keep:
            break
    return out


PARSERS = {"google_scholar": parse_scholar, "google_news": parse_news}


def cached_search(engine, query, cache_dir, fetch, api_key, pause):
    path = Path(cache_dir) / f"{engine}-{urllib.parse.quote(query, safe='')}.json"
    try:
        payload = json.loads(path.read_text())
        if payload_problem(payload) is None:
            return payload, "cached"
    except (OSError, ValueError):
        pass
    if not api_key:
        raise RuntimeError("no SerpApi key: set SERPAPI_API_KEY")
    try:
        payload = fetch(engine, query, api_key)
    finally:
        if pause > 0:
            time.sleep(pause)
    problem = payload_problem(payload)
    if problem:
        raise ValueError(problem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return payload, "searched"


def build(cache_dir, out_path, api_key=None, fetch=fetch_serpapi, pause=1.0, today=None, keys=None):
    today = today or date.today()
    indicators, failed = {}, []
    counts = {"searched": 0, "cached": 0}
    for key in keys or QUERIES:
        query = query_for(key)
        entry = {"query": query, "google_scholar": [], "google_news": []}
        for engine in ENGINES:
            try:
                payload, how = cached_search(engine, query, cache_dir, fetch, api_key, pause)
            except Exception as error:  # one failed search must not lose the others
                failed.append(f"{engine} {key}: {type(error).__name__}: {error}"[:200])
                continue
            counts[how] += 1
            entry[engine] = PARSERS[engine](payload)
        indicators[key] = entry
    found = sum(len(e[engine]) for e in indicators.values() for engine in ENGINES)
    for line in failed:
        print(f"failed {line}", flush=True)
    print(f"{found} results: {counts['searched']} searched, {counts['cached']} cached, {len(failed)} failed", flush=True)
    if not found:
        # nothing to show: leave any earlier file alone and do not write an empty one
        return None
    index = {
        "generated": today.isoformat(),
        "source": "Google Scholar and Google News, searched through SerpApi",
        "region": REGION,
        "indicators": indicators,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="public/evidence/index.json")
    parser.add_argument("--cache", default="trend/cache/serpapi")
    args = parser.parse_args(argv)
    index = build(args.cache, args.out, api_key=os.environ.get("SERPAPI_API_KEY"))
    if index is None:
        print("nothing written", file=sys.stderr)
        return 1
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
