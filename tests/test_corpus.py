"""The corpus is the spec: every case states what every policy
extracts, and the reference implementation must agree on all of it."""

import json
from pathlib import Path

import pytest

from kugiri import BALANCED, GREEDY, STRICT, extract

POLICIES = {"greedy": GREEDY, "balanced": BALANCED, "strict": STRICT}

CASES = [
    json.loads(line)
    for line in (Path(__file__).parent.parent / "corpus" / "cases.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case):
    for name, policy in POLICIES.items():
        got = extract(case["text"], policy)
        assert got == case["expect"][name], (
            f"policy={name}: {got!r} != {case['expect'][name]!r}")


def test_every_case_states_every_policy():
    """A case that omits a policy hides a trade-off; the corpus keeps
    them all explicit."""
    for case in CASES:
        assert set(case["expect"]) == set(POLICIES), case["id"]
        assert case.get("note"), case["id"]


def test_ids_are_unique():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
