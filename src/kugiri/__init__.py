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

- ``GREEDY`` trusts the URL: nothing but whitespace ends it. Paths
  carrying full-width brackets and punctuation survive; prose that
  resumes without a space is swallowed. This is roughly what chat
  platforms and linkify libraries do today, and for their job —
  never breaking ``/wiki/日本語`` — it is the right call.
- ``BALANCED`` trusts prose at the punctuation line: full-width
  *punctuation* ends the URL, full-width *letters* do not. Its
  trade-offs are documented per character class below.
- ``STRICT`` trusts the prose completely: any non-ASCII character ends
  the URL. The right call when the URLs on your side are known to be
  ASCII-only (percent-encoded), which many services guarantee.

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
]

__version__ = "0.1.0"

# Full-width punctuation that ends a URL on sight, scanned from the
# front: prose in these scripts resumes without a space ("…/2、あとで"),
# so a scan back from the tail never reaches the boundary.
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
# Two characters Unicode files as punctuation stay out of the set,
# because the languages that use them put them *inside* words: 「・」
# (U+30FB) joins the parts of a compound ("…/ドナルド・トランプ") and
# U+2019 doubles as the typographic apostrophe ("…/L’Étranger",
# "…/Rock_’n’_Roll"). Cutting at either yields a URL that still
# resolves — to a different page — which hides the break instead of
# showing it. The cost is that two URLs joined by 「・」 fuse into one.
WIDE_STOP = frozenset("。、，．！？：；…‥　｡､"
                      "（）［］｛｝「」『』【】〈〉《》〔〕｢｣“”‘")

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
# and common, and no unescaped URL carries them.
URL_RE = re.compile(r"https?://[^\s<>]+")


@dataclass(frozen=True)
class Policy:
    """Where a URL ends, as three knobs.

    ``wide_stop`` characters end the URL on sight (scanned from the
    front); ``trail`` characters are peeled from the end; ``closers``
    are peeled only when unbalanced against the head. ``ascii_only``
    ends the URL at the first non-ASCII character of any kind — the
    stance that URLs on this side are percent-encoded.

    Policies are frozen; derive variants with :meth:`but`.
    """

    wide_stop: frozenset = frozenset()
    trail: frozenset = frozenset()
    closers: dict = field(default_factory=dict)
    ascii_only: bool = False

    def but(self, **changes) -> "Policy":
        """A copy of this policy with the given knobs replaced."""
        return _replace(self, **changes)


GREEDY = Policy(trail=TRAIL, closers=dict(CLOSERS))
BALANCED = Policy(wide_stop=WIDE_STOP, trail=TRAIL, closers=dict(CLOSERS))
STRICT = Policy(wide_stop=WIDE_STOP, trail=TRAIL, closers=dict(CLOSERS),
                ascii_only=True)


@dataclass(frozen=True)
class Decision:
    """How an extent was decided: the end index, the front-scan stop
    (index and character) if one fired, and whatever the tail peel
    removed, in peel order."""

    end: int
    stop: tuple | None
    peeled: str


def explain(candidate: str, policy: Policy = BALANCED) -> Decision:
    """The extent of the URL at the start of ``candidate``, with its
    reasons. ``candidate`` is text from the scheme onward, as cut by
    whitespace (what :data:`URL_RE` matches)."""
    end = len(candidate)
    stop = None
    for i, c in enumerate(candidate):
        if c in policy.wide_stop or (policy.ascii_only and ord(c) > 127):
            end, stop = i, (i, c)
            break
    # counted once rather than per peel step: peeling only ever removes
    # trailing characters, and no opener can be one
    head = candidate[:end]
    opens = {c: head.count(o) for c, o in policy.closers.items()}
    closes = {c: head.count(c) for c in policy.closers}
    peeled = []
    while end:
        c = candidate[end - 1]
        if c in policy.trail:
            pass
        elif c in policy.closers and closes[c] > opens[c]:
            closes[c] -= 1
        else:
            break
        peeled.append(c)
        end -= 1
    return Decision(end=end, stop=stop, peeled="".join(peeled))


def url_end(candidate: str, policy: Policy = BALANCED) -> int:
    """Index one past the last character that belongs to the URL at the
    start of ``candidate``."""
    return explain(candidate, policy).end


def find_urls(text: str, policy: Policy = BALANCED) -> list:
    """Spans ``(start, end)`` of every URL in ``text`` under ``policy``.

    A match that keeps nothing after its scheme (``https://.``) is not
    a URL and yields no span."""
    spans = []
    for m in URL_RE.finditer(text):
        end = m.start() + url_end(m.group(), policy)
        if text[m.start():end].partition("://")[2]:
            spans.append((m.start(), end))
    return spans


def extract(text: str, policy: Policy = BALANCED) -> list:
    """The URLs themselves, in order of appearance."""
    return [text[s:e] for s, e in find_urls(text, policy)]
