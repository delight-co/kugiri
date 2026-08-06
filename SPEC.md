# kugiri — the decision record

This document explains every character-class decision the corpus encodes. The corpus ([`corpus/cases.jsonl`](corpus/cases.jsonl)) is the executable half of this spec: an implementation is **conformant** when, for every case, it extracts exactly the listed URLs under each policy.

## The problem

Auto-linkers decide where a bare URL ends. Their rules were tuned on text that separates words with spaces — and prose in Japanese and Chinese does not. It resumes right after a URL with a full-width character:

> （この件はここで進めてます: https://example.com/pr/183）

A linkifier that reads `）` as part of the URL produces `…/183%EF%BC%89` — a link that leads nowhere. The reader copies the URL by hand and trims the tail. This is the everyday failure this project exists to state precisely.

## The central claim: extent is not decidable from text alone

`…/a（b）` (full-width brackets in the path) and `…/a（注）` (a parenthetical opening right after the URL) are the same sequence of character classes. No scanner can tell them apart. Every reader therefore loses something, and the choice of **what** to lose is a policy, not a bug. kugiri refuses to ship a single "correct" answer; it ships named policies with their losses stated as corpus cases.

## The policy axis: who do you trust?

- **GREEDY** — trust the URL. No full-width character ends it; the ASCII tail peel (trailing punctuation, unbalanced closers) still applies. This is approximately what chat platforms and linkify libraries do, and for their job — never breaking `/wiki/日本語` — it is right. Its loss: prose that resumes without a space is swallowed (the incident above).
- **BALANCED** — trust prose at the punctuation line. Full-width *punctuation* ends the URL; full-width *letters* do not. Its losses are per-class, below.
- **STRICT** — trust the prose completely. Any non-ASCII character ends the URL. Correct when your side guarantees percent-encoded (ASCII-only) URLs, which many services do.

A knob-level custom policy derives from any preset (`BALANCED.but(...)`).

## Tie-break principle: prefer the visible failure

A URL cut at `【` fails loudly — 404, or a path that obviously stops short. A URL cut inside `ドナルド・トランプ` **resolves, to a different page**, and nobody notices the break. Where both readings lose, kugiri picks the loss you can see. This single principle decides the two exclusions below.

## Character classes (BALANCED)

### `WIDE_STOP` — ends the URL on sight, scanned from the front

Full-width sentence punctuation (`。、，．！？：；…‥`), the ideographic space, halfwidth-kana punctuation (`｡､｢｣`), and **all full-width brackets and quotes** (`（）「」『』【】〈〉《》〔〕“”‘` …).

Brackets are *stops*, not balance-tested pairs, because a forward scan cannot distinguish path-internal pairs from a parenthetical opening after the URL (the central claim). Treating them as balanced swallows the bracket, its contents, **and the rest of the sentence** — the mirror image of the incident, and the more common shape by far. Treating them as stops loses paths that carry literal full-width brackets; those arrive percent-encoded often enough to survive, and fail visibly when they do not (corpus: `fullwidth-brackets-in-path`, `percent-encoded-brackets`).

The scan runs from the **front** because prose in these scripts resumes without a space — a tail scan never reaches the boundary.

### Deliberate exclusions: `・` (U+30FB) and `’` (U+2019)

Unicode files both as punctuation. The languages that use them put them **inside words**: `・` joins the parts of a compound (`…/ドナルド・トランプ`), `’` doubles as the typographic apostrophe (`…/L’Étranger`, `…/Rock_’n’_Roll`). Cutting at either yields a URL that still resolves — to a different page — which hides the break instead of showing it. Three conditions justified each exclusion: Unicode calls it punctuation; the language uses it word-internally; cutting produces a resolving-but-wrong URL. The paid cost: two URLs joined by `・` fuse into one (corpus: `nakaguro-fusion`).

### `TRAIL` — ASCII punctuation peeled from the end

`. , ; : ! ? * ~ " '` — these occur inside URLs, so they count only at the very end, peeled while they last. Quotes are here because a URL is quoted far more often than it ends in one; `*` and `~` because chat markup wraps URLs in emphasis markers, and the closing marker must not bake into the link. The paid cost: a query value genuinely ending in a quote loses it (corpus: `quote-in-query-lost`).

### `CLOSERS` — ASCII brackets peeled only when unbalanced

`…/Foo_(bar)` is one URL; a URL inside `(parentheses)` is not. The balance test works for ASCII because ASCII prose separates with spaces; the full-width counterparts cannot use it, for the reason above.

## What kugiri is not

- **Not a linkifier.** Libraries like linkify-it and twitter-text find URLs permissively so that non-ASCII paths never break — the same trade-off, deliberately taken from the other side. kugiri exists for code that *posts* text to platforms whose auto-linkers it does not control, and must fix the extent before the platform guesses wrong.
- **Not a markup parser.** Code spans, existing `<url|label>` links, Markdown — recognising and skipping those is adapter territory. The core operates on plain text.
- **No re-scan of shortened matches (v0).** When a policy cuts a candidate short, the remainder is not re-scanned for further URLs (corpus: `nakaguro-fusion` under STRICT states this).

## Corpus format

One JSON object per line:

```json
{"id": "…", "text": "…", "expect": {"greedy": ["…"], "balanced": ["…"], "strict": ["…"]}, "note": "…"}
```

Every case lists **all** policies — a case that omits one hides a trade-off — and carries a note saying what it demonstrates. Cases that pin a *loss* are part of the spec on purpose: a later change that trades the other way must show up as a visible decision, not an accident.
