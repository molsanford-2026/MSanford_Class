#!/usr/bin/env python3
"""Forecast assistant for meeting-driven planning.

Loads JSON + Markdown meeting files, discovers refresh sources from explicit
instructions, and produces a prioritized set of requirement questions.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PRIORITY_HINTS = {
    "must": 4,
    "critical": 4,
    "high": 3,
    "important": 2,
    "should": 2,
    "nice to have": 1,
}


@dataclass
class MeetingRecord:
    path: Path
    last_updated: datetime
    instructions: list[str]
    requirements: list[str]
    questions: list[str]
    refresh_source: bool


def _parse_dt(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return fallback


def _extract_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return []


def load_json_record(path: Path) -> MeetingRecord:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fallback_ts = datetime.fromtimestamp(path.stat().st_mtime)

    instructions = _extract_list(payload.get("instructions"))
    requirements = _extract_list(payload.get("requirements"))
    questions = _extract_list(payload.get("questions"))

    refresh_source = bool(
        payload.get("use_for_refresh")
        or payload.get("refresh_source")
        or any("refresh" in i.lower() for i in instructions)
    )

    last_updated = _parse_dt(payload.get("last_updated"), fallback_ts)

    return MeetingRecord(
        path=path,
        last_updated=last_updated,
        instructions=instructions,
        requirements=requirements,
        questions=questions,
        refresh_source=refresh_source,
    )


def load_markdown_record(path: Path) -> MeetingRecord:
    text = path.read_text(encoding="utf-8")
    fallback_ts = datetime.fromtimestamp(path.stat().st_mtime)

    instructions = []
    requirements = []
    questions = []

    section = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            heading = line.lstrip("#").strip().lower()
            if "instruction" in heading:
                section = "instructions"
            elif "requirement" in heading:
                section = "requirements"
            elif "question" in heading:
                section = "questions"
            else:
                section = None
            continue

        bullet = re.sub(r"^[-*]\s+", "", line)
        if not bullet or bullet == line and not line.endswith("?"):
            continue

        if section == "instructions":
            instructions.append(bullet)
        elif section == "requirements":
            requirements.append(bullet)
        elif section == "questions":
            questions.append(bullet)
        elif line.endswith("?"):
            questions.append(line)

    refresh_source = "[refresh-source]" in text.lower() or any(
        "refresh" in i.lower() for i in instructions
    )

    return MeetingRecord(
        path=path,
        last_updated=fallback_ts,
        instructions=instructions,
        requirements=requirements,
        questions=questions,
        refresh_source=refresh_source,
    )


def load_records(base_dir: Path) -> list[MeetingRecord]:
    records: list[MeetingRecord] = []
    for path in sorted(base_dir.rglob("*.json")):
        records.append(load_json_record(path))
    for path in sorted(base_dir.rglob("*.md")):
        records.append(load_markdown_record(path))
    return records


def _score_question(question: str, requirements: list[str]) -> int:
    q = question.lower()
    score = 1
    for hint, weight in PRIORITY_HINTS.items():
        if hint in q:
            score += weight
    for requirement in requirements:
        low = requirement.lower()
        if any(tok in q for tok in re.findall(r"[a-z0-9]+", low)):
            score += 1
    return score


def build_forecast(records: list[MeetingRecord], top_n: int = 5) -> dict[str, Any]:
    usable = [r for r in records if r.refresh_source] or records
    usable.sort(key=lambda r: r.last_updated, reverse=True)

    requirements = [req for r in usable for req in r.requirements]
    question_counter: Counter[str] = Counter()
    for record in usable:
        question_counter.update(record.questions)

    ranked_questions = sorted(
        question_counter,
        key=lambda q: (question_counter[q], _score_question(q, requirements)),
        reverse=True,
    )[:top_n]

    return {
        "refreshed_from": [str(r.path) for r in usable],
        "latest_source": str(usable[0].path) if usable else None,
        "requirements": requirements,
        "top_questions": [
            {
                "question": q,
                "mentions": question_counter[q],
                "score": _score_question(q, requirements),
            }
            for q in ranked_questions
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Meeting-based forecast helper")
    parser.add_argument(
        "workspace",
        type=Path,
        help="Folder containing meeting .json/.md files",
    )
    parser.add_argument("--top", type=int, default=5, help="Number of top questions")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("forecast_output.json"),
        help="Output JSON path",
    )

    args = parser.parse_args()

    records = load_records(args.workspace)
    result = build_forecast(records, top_n=args.top)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote forecast output to {args.out}")


if __name__ == "__main__":
    main()
