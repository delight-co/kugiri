# kugiri

**Status: experiment** — built for our own use; issues welcome, response not guaranteed.

Where does a URL end when it is embedded in Japanese or Chinese prose? Auto-linkers answer with rules tuned on space-separated text, and the result is the everyday broken link:

> （詳細はこちら: https://example.com/pr/183）

— linkified with the closing `）` swallowed in, a URL that leads nowhere.

kugiri (区切り, "delimitation") is a **corpus and reference implementation** for URL *extent detection* in full-width-punctuation scripts. It is not a linkifier: linkify libraries are deliberately permissive so that `/wiki/日本語` never breaks, and for their job that is correct. kugiri exists for the other side — code that *posts* text to platforms whose auto-linkers it does not control, and must decide the extent before the platform guesses wrong.

## The one idea

The end of a URL is **not decidable from the text alone**: `…/a（b）` (brackets in the path) and `…/a（注）` (prose right after the URL) are indistinguishable to a scanner. So kugiri does not ship a "correct" answer; it ships **policies** on one axis — *who do you trust?* — with the losses of each stated as executable corpus cases.

| Policy | Stance | What it loses |
|---|---|---|
| `GREEDY` | Trust the URL: only whitespace ends it | Swallows prose that resumes without a space |
| `BALANCED` | Full-width *punctuation* ends it, full-width *letters* don't | Paths carrying literal full-width brackets; URLs fused by `・` |
| `STRICT` | Any non-ASCII ends it (your URLs are percent-encoded) | Every non-ASCII path |

Tie-breaks follow one principle: **prefer the visible failure.** A URL cut at `【` fails loudly; a URL cut inside `ドナルド・トランプ` resolves to a *different page* and hides the break. That is why `・` (U+30FB) and `’` (U+2019) never end a URL here. The full reasoning per character class is in [SPEC.md](SPEC.md).

## Quick start

A single stdlib-only module — vendor the file or install from git:

```
pip install git+https://github.com/delight-co/kugiri
```

```python
from kugiri import extract, explain, STRICT, BALANCED

extract("（会話はこちら: https://example.com/?session=s1）")
# ['https://example.com/?session=s1']

extract("https://a.example/x・https://b.example/y", STRICT)
# ['https://a.example/x']

explain("https://x.example/doc（PDF）です")
# Decision(end=21, stop=(21, '（'), peeled='')
```

Custom knobs derive from a preset:

```python
lenient = BALANCED.but(wide_stop=BALANCED.wide_stop - frozenset("【】"))
```

## The corpus is the spec

[`corpus/cases.jsonl`](corpus/cases.jsonl) states, for every case, what every policy extracts — **including the cases a policy deliberately loses**. An implementation in any language is conformant when it passes the corpus; the Python module here is the reference. [SPEC.md](SPEC.md) is the decision record behind each character class.

## License

MIT
