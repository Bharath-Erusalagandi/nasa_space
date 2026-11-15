import json
from datetime import date

import evidence as ev

SCHOLAR = {"organic_results": [
    {"title": "Rainfall  trends in Zambia", "link": "https://example.org/a", "snippet": "long text we do not keep",
     "publication_info": {"summary": "A Banda, B Phiri - Journal of Climate, 2019 - Wiley"}},
    {"title": "", "link": "https://example.org/untitled"},
    {"title": "A citation with no link"},
    {"title": "Second paper", "link": "https://example.org/b", "publication_info": {"summary": "C Zulu - 2021"}},
]}
NEWS = {"news_results": [
    {"title": "Late rains worry farmers", "link": "https://news.example/1", "source": {"name": "Daily Mail Zambia"}, "date": "11/02/2025, 08:00 AM, +0000 UTC"},
    {"title": "Grouped", "stories": [{"title": "First story", "link": "https://news.example/2", "source": {"name": "ZNBC"}}]},
    {"title": "Bad link", "link": "javascript:alert(1)"},
]}


def fake(calls):
    def fetch(engine, query, api_key):
        calls.append((engine, query, api_key))
        return SCHOLAR if engine == "google_scholar" else NEWS
    return fetch


def test_parse_scholar_keeps_title_link_source_and_year_only():
    rows = ev.parse_scholar(SCHOLAR)
    assert rows == [
        {"title": "Rainfall trends in Zambia", "link": "https://example.org/a",
         "source": "A Banda, B Phiri - Journal of Climate, 2019 - Wiley", "year": 2019},
        {"title": "Second paper", "link": "https://example.org/b", "source": "C Zulu - 2021", "year": 2021},
    ]
    assert all("snippet" not in row for row in rows)


def test_parse_news_takes_the_first_story_of_a_group_and_drops_unsafe_links():
    rows = ev.parse_news(NEWS)
    assert [r["link"] for r in rows] == ["https://news.example/1", "https://news.example/2"]
    assert rows[0]["source"] == "Daily Mail Zambia"
    assert rows[1] == {"title": "First story", "link": "https://news.example/2", "source": "ZNBC", "date": None}


def test_parsers_survive_an_empty_response():
    assert ev.parse_scholar({}) == [] and ev.parse_news({}) == []


def test_keep_limits_the_list():
    many = {"organic_results": [{"title": f"t{i}", "link": f"https://example.org/{i}"} for i in range(9)]}
    assert len(ev.parse_scholar(many)) == ev.KEEP


def test_build_writes_one_entry_per_indicator_and_names_the_region(tmp_path):
    calls = []
    out = tmp_path / "public" / "evidence" / "index.json"
    index = ev.build(tmp_path / "cache", out, api_key="k", fetch=fake(calls), pause=0, today=date(2026, 11, 14))
    assert set(index["indicators"]) == set(ev.QUERIES)
    assert len(calls) == 2 * len(ev.QUERIES)
    assert all("Zambia" in query for _, query, _ in calls)
    written = json.loads(out.read_text())
    assert written["generated"] == "2026-11-14"
    assert written["indicators"]["wet_days"]["google_scholar"][0]["title"] == "Rainfall trends in Zambia"


def test_second_run_reads_the_cache_and_needs_no_key(tmp_path):
    calls = []
    out = tmp_path / "index.json"
    ev.build(tmp_path / "cache", out, api_key="k", fetch=fake(calls), pause=0)
    first = len(calls)
    again = ev.build(tmp_path / "cache", out, api_key=None, fetch=fake(calls), pause=0)
    assert len(calls) == first
    assert again["indicators"]["october_temp_c"]["google_news"]


def test_the_key_is_never_written_to_the_output_or_the_cache(tmp_path):
    out = tmp_path / "index.json"
    ev.build(tmp_path / "cache", out, api_key="SECRET-KEY-123", fetch=fake([]), pause=0)
    for path in [out, *(tmp_path / "cache").iterdir()]:
        assert "SECRET-KEY-123" not in path.read_text()


def test_without_a_key_or_cache_nothing_is_written(tmp_path):
    out = tmp_path / "index.json"
    assert ev.build(tmp_path / "cache", out, api_key=None, fetch=fake([]), pause=0) is None
    assert not out.exists()


def test_an_api_error_is_reported_and_not_cached(tmp_path):
    def broken(engine, query, api_key):
        return {"error": "Invalid API key."}
    out = tmp_path / "index.json"
    assert ev.build(tmp_path / "cache", out, api_key="bad", fetch=broken, pause=0) is None
    assert not (tmp_path / "cache").exists() or not list((tmp_path / "cache").iterdir())


def test_one_failed_search_keeps_the_rest(tmp_path):
    def flaky(engine, query, api_key):
        if engine == "google_news":
            raise TimeoutError("slow")
        return SCHOLAR
    index = ev.build(tmp_path / "cache", tmp_path / "index.json", api_key="k", fetch=flaky, pause=0)
    entry = index["indicators"]["wet_days"]
    assert entry["google_scholar"] and entry["google_news"] == []


def test_every_indicator_of_the_trend_engine_has_a_query():
    from trend_detective import INDICATORS
    assert set(ev.QUERIES) == set(INDICATORS)
