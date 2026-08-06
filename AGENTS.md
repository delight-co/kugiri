# AGENTS.md

> AGENTS.md is the canonical instruction file for AI agents working in this repo; `CLAUDE.md` is a symlink to it. **Edit AGENTS.md** — tools refuse writes through the symlink.

## This is a public repository

Everything here is visible to the world. Act accordingly.

## Language

All external communication in English: commits, issues, PRs, comments, code comments, docs. An example or test fixture that only carries meaning in a particular language is written in that language — this repo is *about* full-width scripts, so the corpus is full of them by design.

## Information Hygiene

Never write: private repository names or issue numbers, Slack IDs, session URLs, internal architecture details, internal project names or codenames. Org names (`delight-co`) and public user names (`carrotRakko`, `iku-min`) are fine. GitHub keeps history (PR edits, dangling SHAs) — the only safe strategy is never writing it in the first place.

## Signature

AI-authored commits, PRs, issues, and comments end with:

```
✍️ Author: Claude Code with @{GitHub username of the human} (AI-written, human-approved)
```

This line discloses AI authorship and marks human approval — it is an instruction for agents working in this repo, not a requirement on human contributors.

## The corpus is the spec

`corpus/cases.jsonl` pins behavior **including deliberate losses**. Changing an expectation is a spec change, not a test fix: it must be argued against [SPEC.md](SPEC.md)'s principles (visible failure over silent misdirection) and called out explicitly in the PR.

## No hard-wrapping in prose

One paragraph (or list item) per line — docs are read with soft wrap.
