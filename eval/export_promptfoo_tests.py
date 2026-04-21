#!/usr/bin/env python3
"""Generate eval/promptfoo_tests.yaml from eval/dataset.py.

Promptfoo supports per-test asserts (contains / not-contains / regex / equals).
We translate the Python ground truth into those primitives so the eval can be
run either via `npx promptfoo eval` or via the Python runner in
`eval/run_eval.py` — both read from the same authoritative dataset.
"""

from __future__ import annotations

import json
from pathlib import Path

from dataset import CASES


def emit(case: dict) -> dict:
    test = {
        "description": f"#{case['id']:02d} [{case['category']}] {case['query'][:60]}",
        "vars": {"query": case["query"]},
    }
    asserts: list[dict] = []
    expect = case["expect"]
    if isinstance(expect, str):
        asserts.append({"type": "equals", "value": expect})
    else:
        for token in expect.get("required", []):
            asserts.append({"type": "icontains", "value": token})
        for token in expect.get("forbidden", []):
            asserts.append({"type": "not-icontains", "value": token})
        for pattern in expect.get("regex", []):
            asserts.append({"type": "regex", "value": pattern})
    test["assert"] = asserts
    return test


def dump_yaml(data: list[dict]) -> str:
    # We hand-roll minimal YAML to avoid a PyYAML dependency.
    def yaml_str(s: str) -> str:
        if any(ch in s for ch in ":#-?!&*|>'\"{}[]%@`") or s.strip() != s or "\n" in s:
            escaped = s.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return s

    lines: list[str] = []
    for test in data:
        lines.append(f"- description: {yaml_str(test['description'])}")
        lines.append(f"  vars:")
        lines.append(f"    query: {yaml_str(test['vars']['query'])}")
        lines.append(f"  assert:")
        for a in test["assert"]:
            lines.append(f"    - type: {a['type']}")
            lines.append(f"      value: {yaml_str(a['value'])}")
    return "\n".join(lines) + "\n"


def main() -> None:
    out_yaml = Path(__file__).with_name("promptfoo_tests.yaml")
    out_json = Path(__file__).with_name("dataset.json")
    tests = [emit(c) for c in CASES]
    out_yaml.write_text(dump_yaml(tests), encoding="utf-8")
    out_json.write_text(json.dumps(CASES, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_yaml.relative_to(out_yaml.parent.parent)} ({len(tests)} tests)")
    print(f"Wrote {out_json.relative_to(out_json.parent.parent)}")


if __name__ == "__main__":
    main()
