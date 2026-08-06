# kugiri — the decision record

This document explains every character-class decision the corpus encodes. The corpus ([`corpus/cases.jsonl`](corpus/cases.jsonl)) is the executable half of this spec: an implementation is **conformant** when, for every case, it extracts exactly the listed URLs under each policy.

## The problem

Auto-linkers decide where a bare URL ends. Their rules were tuned on text that separates words with spaces — and prose in Japanese and Chinese does not. It resumes right after a URL with a full-width character:

> （この件はここで進めてます: https://example.com/pr/4207）

A linkifier that reads `）` as part of the URL produces `…/4207%EF%BC%89` — a link that leads nowhere. The reader copies the URL by hand and trims the tail. This is the everyday failure this project exists to state precisely.

## The central claim: extent is not decidable from text alone

`…/a（b）` (full-width brackets in the path) and `…/a（注）` (a parenthetical opening right after the URL) are the same sequence of character classes. No scanner can tell them apart. Every reader therefore loses something, and the choice of **what** to lose is a policy, not a bug. kugiri refuses to ship a single "correct" answer; it ships named policies with their losses stated as corpus cases.

## What is a candidate

Everything downstream operates on a **candidate**: text from a scheme (`https://` or `http://`, case-insensitive per RFC 3986 §3.1 — the extraction preserves the original casing) up to the first whitespace, `<`, or `>`. Consequences the corpus pins:

- The ideographic space U+3000 is whitespace, so it ends the candidate before any policy runs (`ideographic-space`).
- `<` and `>` never belong to a candidate — the old plain-text convention for delimiting URLs (`angle-bracket-adjacent`).
- A candidate that keeps nothing after its scheme once a policy has spoken yields no span (`bare-scheme`, `bare-scheme-fullwidth`).
- **Scanning resumes at the decided end**, not at the end of the regex match: when a policy cuts a candidate short, whatever follows the cut is examined again, so `…/x、https://…/y` yields both URLs instead of silently deleting the second (`comma-separated-urls`, `nakaguro-fusion` under STRICT).

## The policy axis: who do you trust?

- **GREEDY** — trust the URL. No full-width punctuation ends it; the ASCII tail peel (trailing punctuation, unbalanced closers) still applies. This is approximately what chat platforms and linkify libraries do, and for their job — never breaking `/wiki/日本語` — it is right. Its loss: prose that resumes without a space is swallowed (the incident above), and copy-paste debris stays baked in.
- **BALANCED** — trust prose at the punctuation line. A **curated set** of full-width punctuation ends the URL; full-width *letters* do not. Its losses are per-class, below — each pinned as a corpus case.
- **STRICT** — trust the prose completely. Any non-ASCII character ends the URL. Correct when your side guarantees percent-encoded (ASCII-only) URLs, which many services do. Its sharp edges are stated below.

For any candidate the presets are monotone: `GREEDY` never yields a shorter extent than `BALANCED`, which never yields a shorter extent than `STRICT` (the stop sets only grow in that direction and the tail peel is common to all three).

A knob-level custom policy derives from any preset (`BALANCED.but(...)`). `STRICT` keeps the full stop set even though `ascii_only` subsumes it, so that `STRICT.but(ascii_only=False)` degrades exactly to `BALANCED` rather than to something laxer.

## Tie-break principle: prefer the visible failure

A URL cut at `【` fails loudly — 404, or a path that obviously stops short. A URL cut inside `ドナルド・トランプ` **resolves, to a different page**, and nobody notices the break. Where both readings lose, kugiri picks the loss you can see.

## Character classes (BALANCED)

### `WIDE_STOP` — ends the URL on sight, scanned from the front

**This is a curated 36-character list, not a Unicode category.** In full:

- Sentence punctuation: `。 、 ， ． ！ ？ ： ； … ‥`
- Ideographic space: `　` (U+3000 — defense in depth; whitespace ends the candidate first)
- Halfwidth-kana punctuation: `｡ ､ ｢ ｣`
- Brackets and quotes: `（ ） ［ ］ ｛ ｝ 「 」 『 』 【 】 〈 〉 《 》 〔 〕 “ ” ‘`

Brackets are *stops*, not balance-tested pairs, because a forward scan cannot distinguish path-internal pairs from a parenthetical opening after the URL (the central claim). Treating them as balanced swallows the bracket, its contents, **and the rest of the sentence** — the mirror image of the incident, and the more common shape by far. Treating them as stops loses paths that carry literal full-width brackets; those arrive percent-encoded often enough to survive, and fail visibly when they do not (corpus: `fullwidth-brackets-in-path`, `percent-encoded-brackets`).

The scan runs from the **front** because prose in these scripts resumes without a space — a tail scan never reaches the boundary.

**BALANCED's pinned losses** (each a corpus case, per the corpus contract):

- Real titles carry sentence punctuation: `…/君の名は。` loses its final character (`sentence-final-fullstop-title`), `…/機動戦士ガンダム：閃光のハサウェイ` loses its subtitle (`fullwidth-colon-subtitle`). Pasted URLs are not percent-encoded, so the percent-encoding mitigation does not apply here; GREEDY is the preset that preserves such paths.
- Prose that resumes with a **letter** is swallowed: `…URLを見てください` (`particle-after-url`). BALANCED's premise is the punctuation line; only STRICT survives this shape.
- Two URLs joined by `・` fuse (`nakaguro-fusion` — see the exclusions below).

### Known gaps (not in the curated set)

Unicode files many more code points as CJK-adjacent punctuation than this list carries. Deliberately not included until a corpus case argues them in — inclusion is a visible spec change, not drift:

- `※` (reference mark) and `〜` (wave dash) — everyday Japanese characters, but they also appear inside path-like text and their post-URL frequency is unproven here; `reference-mark` pins the current behavior.
- Rare bracket families `〖〗 〘〙 〚〛 〝〞〟 ｟｠` and the vertical presentation forms U+FE35–FE44 — vertical-text conventions that chat and web prose almost never put after a URL.
- Dashes and bullets (`– ‼ •` and friends).

### Deliberate exclusions: `・` (U+30FB) and `’` (U+2019)

Unicode files both as punctuation. The languages that use them put them **inside words**: `・` joins the parts of a compound (`…/ドナルド・トランプ`), `’` doubles as the typographic apostrophe (`…/L’Étranger`, `…/Rock_’n’_Roll`). Cutting at either yields a URL that still resolves — to a different page — which hides the break instead of showing it. Three conditions justified each exclusion: Unicode calls it punctuation; the language uses it word-internally; cutting produces a resolving-but-wrong URL.

The paid costs, pinned: URLs joined by `・` fuse (`nakaguro-fusion`); a URL closed by a curly quote swallows the quote and the prose after it (`curly-quote-asymmetry` — note the deliberate asymmetry: `‘` U+2018, which no word carries internally, remains a stop).

### `DEBRIS` — invisible copy-paste artifacts

Zero-width space (U+200B), word joiner (U+2060), BOM (U+FEFF), soft hyphen (U+00AD). An invisible character baked into a URL produces a string that *looks* identical to the real URL and is not — the exact invisible failure the tie-break principle exists to prevent — so the prose-trusting presets stop at them (`zwsp-debris`). GREEDY, true to its stance, keeps them.

### `TRAIL` — ASCII punctuation peeled from the end

`. , ; : ! ? * ~ " '` — these occur inside URLs, so they count only at the very end, peeled while they last. Quotes are here because a URL is quoted far more often than it ends in one; `*` and `~` because chat markup wraps URLs in emphasis markers, and the closing marker must not bake into the link. The paid cost: a query value genuinely ending in a quote loses it (corpus: `quote-in-query-lost`).

### `CLOSERS` — ASCII brackets peeled only when unbalanced

`)` against `(`, `]` against `[`, `}` against `{`. `…/Foo_(bar)` is one URL; a URL inside `(parentheses)` is not. The balance is counted over the **head** (everything before the front stop): brackets beyond the stop belong to prose and must not vote. The test works for ASCII because ASCII prose separates with spaces; the full-width counterparts cannot use it, for the reason above.

## STRICT's sharp edges

- The boundary is the code point (`ord(c) > 127`), not the grapheme: a combining mark cuts *after* its base letter, so `…/cafe` + U+0301 yields `…/cafe` — a plausible-but-different ASCII URL (`combining-mark-strict`). Normalization is out of scope in v0.
- Latin-script paths (`é`, `»`) cut like CJK ones — STRICT is about ASCII, not about scripts.

## What kugiri is not

- **Not a linkifier.** Libraries like linkify-it and twitter-text find URLs permissively so that non-ASCII paths never break — the same trade-off, deliberately taken from the other side. kugiri exists for code that *posts* text to platforms whose auto-linkers it does not control, and must fix the extent before the platform guesses wrong.
- **Not a markup parser.** Code spans, existing `<url|label>` links, Markdown — recognising and skipping those is adapter territory. The core operates on plain text.
- **Not a scheme zoo.** `ftp://`, `mailto:`, and the full-width `ｈｔｔｐｓ://` that some IMEs emit are out of scope in v0.

## Corpus format

One JSON object per line:

```json
{"id": "…", "text": "…", "expect": {"greedy": ["…"], "balanced": ["…"], "strict": ["…"]}, "note": "…"}
```

Every case lists **all** policies — a case that omits one hides a trade-off — and carries a note saying what it demonstrates. Cases that pin a *loss* are part of the spec on purpose: a later change that trades the other way must show up as a visible decision, not an accident. The reference test suite additionally sweeps every character of `WIDE_STOP`, `DEBRIS`, `TRAIL`, and `CLOSERS` mechanically, so no character is unpinned even where the corpus tells no story about it.
