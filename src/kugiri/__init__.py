"""kugiri (区切り) — URL extent detection for full-width scripts.

Auto-linkers decide where a bare URL ends by their own rules, and most
of them were tuned on text that separates words with spaces. Prose in
Japanese and Chinese does not: it resumes right after a URL with a
full-width character, and a linkifier that reads that character as part
of the URL produces a link that leads nowhere — the everyday shape is a
URL inside 「（…）」 losing its closing bracket to the link.

The uncomfortable truth this library is built around: **the end of a
URL is not decidable from the text alone.** ``…/a（b）`` (brackets in
the path) and ``…/a（注）`` (prose opening right after the URL) are the
same string of character classes. Every reader loses something; the
choice of what to lose is a policy, not a bug. So kugiri ships
policies — three presets on one axis, each knob overridable — and a
corpus that states, case by case, what each policy gives up.

The axis is who you trust:

- ``GREEDY`` trusts the URL: no full-width punctuation ends it (the
  ASCII tail peel still applies, and whitespace — including the
  ideographic space — always ends the candidate itself). Paths carrying
  full-width brackets and punctuation survive; prose that resumes
  without a space is swallowed. This is roughly what chat platforms and
  linkify libraries do today, and for their job — never breaking
  ``/wiki/日本語`` — it is the right call.
- ``BALANCED`` trusts prose at the punctuation line: the curated
  full-width punctuation set ends the URL, full-width letters do not.
  Its trade-offs are documented per character class below and pinned in
  the corpus — including the ones where it loses.
- ``STRICT`` trusts the prose completely: any non-ASCII character ends
  the URL. The right call when the URLs on your side are known to be
  ASCII-only (percent-encoded), which many services guarantee.

For any candidate the presets are monotone: the extent under ``GREEDY``
is never shorter than under ``BALANCED``, which is never shorter than
under ``STRICT`` (the stop sets only grow along that direction and the
tail peel is common).

One principle drives the tie-breaks: **prefer failures that are
visible.** A URL cut at a full-width bracket fails loudly (404, or a
path that obviously stops short). A URL cut inside 「ドナルド・トランプ」
resolves — to a different page — and nobody notices the break. Where
both readings lose something, kugiri picks the loss you can see.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace as _replace

__all__ = [
    "Policy", "Decision", "GREEDY", "BALANCED", "STRICT",
    "url_end", "explain", "find_urls", "extract",
    "WIDE_STOP", "DEBRIS", "TRAIL", "CLOSERS", "URL_RE",
]

__version__ = "0.1.0"

# Full-width punctuation that ends a URL on sight, scanned from the
# front: prose in these scripts resumes without a space ("…/2、あとで"),
# so a scan back from the tail never reaches the boundary.
#
# This is a curated list, not a Unicode category: the 36 characters
# here are the punctuation that everyday horizontal Japanese and
# Chinese prose actually puts right after a URL. Unicode files many
# more code points as CJK punctuation (vertical presentation forms,
# 〖〗-class brackets, ※, 〜, …); they are deliberately *not* here
# until a corpus case argues them in — see SPEC.md "Known gaps".
#
# Brackets and quotes are in this set rather than under the balance
# test below, because a forward scan cannot tell their two positions
# apart: "…/a（b）" (inside a path) and "…/a（注）" (prose opening right
# after the URL) look identical to it. Both readings lose something;
# this takes the cheaper, *visible* loss. Reading them as balanced
# swallows the bracket, its contents and the rest of the sentence into
# the link. Reading them as enders loses paths that genuinely carry
# full-width brackets — which arrive percent-encoded often enough to
# survive, and fail visibly when they do not.
#
# Two characters Unicode files as punctuation are deliberately
# excluded, because the languages that use them put them *inside*
# words: 「・」 (U+30FB) joins the parts of a compound
# ("…/ドナルド・トランプ") and U+2019 doubles as the typographic
# apostrophe ("…/L’Étranger", "…/Rock_’n’_Roll"). Cutting at either
# yields a URL that still resolves — to a different page — which hides
# the break instead of showing it. The cost is that two URLs joined by
# 「・」 fuse into one.
#
# The ideographic space U+3000 is listed for defense in depth only:
# Python's \s already matches it, so the candidate regex ends there
# first and this entry is normally unreachable.
WIDE_STOP = frozenset("。、，．！？：；…‥　｡､"
                      "（）［］｛｝「」『』【】〈〉《》〔〕｢｣“”‘")

# Invisible format characters that reach text only as copy-paste
# debris: zero-width space, word joiner, BOM, soft hyphen. Left inside
# a URL they produce a string that *looks* identical to the real URL
# and is not — the exact invisible failure this library exists to
# prevent — so the prose-trusting presets stop at them. GREEDY, true
# to its stance, keeps them.
DEBRIS = frozenset("\u200b\u2060\ufeff\u00ad")

# ASCII punctuation does occur inside URLs, so it counts only at the
# very end, peeled back while it lasts. Quotes are here because a URL
# is quoted far more often than it ends in one; * and ~ because chat
# markup wraps URLs in emphasis markers, and an emphasised URL would
# otherwise bake its closing marker into the link.
TRAIL = frozenset(".,;:!?*~\"'")

# ASCII closing brackets are peeled only when unbalanced: "…/Foo_(bar)"
# is one URL, while a URL inside (parentheses) is not. Their full-width
# counterparts cannot use this test, for the reason above.
CLOSERS = {")": "(", "]": "[", "}": "{"}

# A URL candidate: scheme up to whitespace. < and > stay out because
# the angle-bracket convention for delimiting URLs in plain text is old
# and common, and no unescaped URL carries them. The scheme letters are
# spelled as explicit ASCII classes rather than re.IGNORECASE: RFC 3986
# §3.1 makes schemes case-insensitive over ASCII ALPHA only, while the
# flag would also fold Unicode look-alikes (U+017F httpſ://) into a
# scheme. The extracted text keeps the original casing.
URL_RE = re.compile(r"[hH][tT][tT][pP][sS]?://[^\s<>]+")
_SCHEME_RE = re.compile(r"[hH][tT][tT][pP][sS]?://")


@dataclass(frozen=True)
class Policy:
    """Where a URL ends, as three knobs.

    ``wide_stop`` characters end the URL on sight (scanned from the
    front); ``trail`` characters are peeled from the end; ``closers``
    are peeled only when unbalanced against the head. ``ascii_only``
    ends the URL at the first non-ASCII character of any kind — the
    stance that URLs on this side are percent-encoded.

    ``wide_stop`` and ``trail`` normalise to frozensets and ``closers``
    to a per-instance dict copy, so a derived policy never aliases a
    preset's state and instances pickle and deep-copy cleanly. Treat
    the presets as read-only constants. (A policy is not hashable — it
    carries a mapping.) Derive variants with :meth:`but`; note that
    ``Policy()`` with no arguments cuts nothing at all — even laxer
    than ``GREEDY``.
    """

    wide_stop: frozenset = frozenset()
    trail: frozenset = frozenset()
    closers: dict = field(default_factory=dict)
    ascii_only: bool = False

    def __post_init__(self):
        if not isinstance(self.ascii_only, bool):
            raise TypeError("ascii_only must be a bool")
        object.__setattr__(self, "wide_stop", frozenset(self.wide_stop))
        object.__setattr__(self, "trail", frozenset(self.trail))
        object.__setattr__(self, "closers", dict(self.closers))

    def but(self, **changes) -> "Policy":
        """A copy of this policy with the given knobs replaced."""
        return _replace(self, **changes)


GREEDY = Policy(trail=TRAIL, closers=CLOSERS)
BALANCED = Policy(wide_stop=WIDE_STOP | DEBRIS, trail=TRAIL, closers=CLOSERS)
# STRICT keeps the full stop set even though ascii_only subsumes it:
# STRICT.but(ascii_only=False) then degrades exactly to BALANCED
# instead of to something laxer.
STRICT = Policy(wide_stop=WIDE_STOP | DEBRIS, trail=TRAIL, closers=CLOSERS,
                ascii_only=True)


@dataclass(frozen=True)
class Decision:
    """How an extent was decided: the end index, the front-scan stop
    (index and character) if one fired, and whatever the tail peel
    removed, in peel order."""

    end: int
    stop: tuple | None
    peeled: str


def _extent(text: str, start: int, limit: int, policy: Policy) -> tuple:
    """The decision for the candidate ``text[start:limit]``, computed in
    place — no substring is materialised, which keeps :func:`find_urls`
    linear even when one unbroken run holds many URLs."""
    end = limit
    stop = None
    for i in range(start, limit):
        c = text[i]
        if c in policy.wide_stop or (policy.ascii_only and ord(c) > 127):
            end, stop = i, (i - start, c)
            break
    # counted once rather than per peel step: peeling only ever removes
    # trailing characters, and no opener can be one. The window is the
    # head (everything before the front stop), not the whole candidate:
    # brackets beyond the stop belong to prose and must not vote.
    opens = {c: text.count(o, start, end) for c, o in policy.closers.items()}
    closes = {c: text.count(c, start, end) for c in policy.closers}
    peeled = []
    while end > start:
        c = text[end - 1]
        if c in policy.trail:
            pass
        elif c in policy.closers and closes[c] > opens[c]:
            closes[c] -= 1
        else:
            break
        peeled.append(c)
        end -= 1
    return end, stop, "".join(peeled)


def explain(candidate: str, policy: Policy = BALANCED) -> Decision:
    """The extent of the URL at the start of ``candidate``, with its
    reasons. ``candidate`` is text from the scheme onward, as cut by
    whitespace (what :data:`URL_RE` matches)."""
    end, stop, peeled = _extent(candidate, 0, len(candidate), policy)
    return Decision(end=end, stop=stop, peeled=peeled)


def url_end(candidate: str, policy: Policy = BALANCED) -> int:
    """Index one past the last character that belongs to the URL at the
    start of ``candidate``."""
    return explain(candidate, policy).end


def find_urls(text: str, policy: Policy = BALANCED) -> list:
    """Spans ``(start, end)`` of every URL in ``text`` under ``policy``.

    Scanning resumes at each decided end, not at the end of the regex
    match: when a policy cuts a candidate short, whatever follows the
    cut is examined again, so ``…/x、https://…/y`` yields both URLs
    rather than silently dropping the second. Spans never overlap and
    come in order of appearance.

    A match that keeps nothing after its scheme (``https://.``) is not
    a URL and yields no span."""
    spans = []
    # the outer scan consumes each character once; the inner scan walks
    # a single whitespace-delimited run, resuming at every cut, so the
    # whole pass stays linear
    for m in URL_RE.finditer(text):
        pos, run_end = m.start(), m.end()
        while (s := _SCHEME_RE.search(text, pos, run_end)):
            start = s.start()
            end, _, _ = _extent(text, start, run_end, policy)
            if text[start:end].partition("://")[2]:
                spans.append((start, end))
            pos = max(end, start + 1)
    return spans


def extract(text: str, policy: Policy = BALANCED) -> list:
    """The URLs themselves, in order of appearance."""
    return [text[s:e] for s, e in find_urls(text, policy)]
