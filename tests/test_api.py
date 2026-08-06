"""The API around the corpus: spans, decisions, derived policies, and
mechanical sweeps of the full character classes — the corpus tells
stories; these pin every character of every set so none is left
unguarded by a mutation."""

import pytest

from kugiri import (
    BALANCED, CLOSERS, DEBRIS, GREEDY, STRICT, TRAIL, WIDE_STOP,
    Decision, explain, find_urls, url_end,
)


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


# ------------------------------------------------- mechanical sweeps

def test_every_wide_stop_and_debris_character_ends_a_url():
    for c in sorted(WIDE_STOP | DEBRIS):
        cand = f"https://x.example/a{c}rest"
        assert cand[:url_end(cand)] == "https://x.example/a", f"U+{ord(c):04X}"


def test_every_trail_character_peels_from_the_end():
    for c in sorted(TRAIL):
        cand = f"https://x.example/a{c}"
        assert cand[:url_end(cand)] == "https://x.example/a", f"U+{ord(c):04X}"


def test_every_closer_peels_unbalanced_and_stays_balanced():
    for closer, opener in CLOSERS.items():
        unbalanced = f"https://x.example/a{closer}"
        assert unbalanced[:url_end(unbalanced)] == "https://x.example/a", closer
        matched = f"https://x.example/{opener}b{closer}"
        assert url_end(matched) == len(matched), closer


def test_strict_boundary_is_ascii_not_latin1():
    # U+00BB: above 127, below 256 — pins the exact boundary
    cand = "https://x.example/a»b"
    assert cand[:url_end(cand, STRICT)] == "https://x.example/a"


def test_peel_counts_only_the_head_window():
    # brackets beyond the front stop belong to prose and must not vote:
    # the "(" after 。 must not balance away the ")" inside the head
    cand = "https://x.example/a)。("
    assert cand[:url_end(cand, BALANCED)] == "https://x.example/a"


def test_presets_are_monotone():
    for cand in ("https://x.example/a（PDF）です",
                 "https://ja.example.org/wiki/ドナルド・トランプ",
                 "https://x.example/a※注意",
                 "https://x.example/w/Foo_(bar)"):
        g, b, s = (url_end(cand, p) for p in (GREEDY, BALANCED, STRICT))
        assert g >= b >= s, cand


# ------------------------------------------- preset immutability

def test_derived_policy_shares_no_mutable_state():
    derived = BALANCED.but(ascii_only=True)
    assert derived.closers is not BALANCED.closers
    with pytest.raises(TypeError):
        BALANCED.closers[")"] = "x"


def test_string_knobs_normalise_to_character_sets():
    p = BALANCED.but(wide_stop="。、")
    assert p.wide_stop == frozenset("。、")
