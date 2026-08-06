"""The API around the corpus: spans, decisions, derived policies."""

from kugiri import BALANCED, GREEDY, STRICT, Decision, explain, find_urls, url_end


def test_find_urls_returns_spans():
    text = "PR https://g.example/2、それと https://g.example/3。"
    spans = find_urls(text)
    assert [text[s:e] for s, e in spans] == [
        "https://g.example/2", "https://g.example/3"]


def test_url_end_is_an_index_into_the_candidate():
    cand = "https://example.com/doc（PDF）です"
    assert cand[:url_end(cand)] == "https://example.com/doc"


def test_explain_reports_the_front_stop():
    d = explain("https://example.com/doc（PDF）です")
    assert isinstance(d, Decision)
    assert d.stop == (23, "（")
    assert d.peeled == ""


def test_explain_reports_the_peel_in_order():
    d = explain("https://example.com/a?!")
    assert d.stop is None
    assert d.peeled == "!?"
    assert d.end == len("https://example.com/a")


def test_policies_disagree_where_they_should():
    cand = "https://ja.example.org/wiki/日本語"
    assert url_end(cand, GREEDY) == len(cand)
    assert url_end(cand, BALANCED) == len(cand)
    assert cand[:url_end(cand, STRICT)] == "https://ja.example.org/wiki/"


def test_but_derives_a_custom_policy():
    lenient = BALANCED.but(
        wide_stop=BALANCED.wide_stop - frozenset("【】"))
    cand = "https://x.example/【重要】メモ"
    assert cand[:url_end(cand, BALANCED)] == "https://x.example/"
    assert cand[:url_end(cand, lenient)] == cand
