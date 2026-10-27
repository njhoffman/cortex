"""Offline source status from the last sync report, source caches, and the active catalog."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from cortex.config import Config, Source
from cortex.model import CortexError
from cortex.progress import style

COLUMNS = (
    ("SOURCE", "id"),
    ("ON", "on"),
    ("ADAPTER", "adapter"),
    ("LICENSE", "license"),
    ("STATUS", "status"),
    ("REVISION", "short_revision"),
    ("CHECKED", "checked"),
    ("PARSED", "parsed"),
    ("REJECTED", "rejected"),
    ("KEPT", "kept"),
)
NUMERIC = {"parsed", "rejected", "kept"}


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, UnicodeError, ValueError) as exc:
        raise CortexError(f"Cannot read {path}: {exc}") from exc


def collect(config: Config) -> list[dict]:
    cache = config.paths.cache
    last = read_json(cache / "last-sync.json") or {}
    reports = {item["id"]: item for item in last.get("sources", [])}
    reasons: dict[str, Counter] = defaultdict(Counter)
    missing: dict[str, Counter] = defaultdict(Counter)
    samples: dict[tuple[str, str], str] = {}
    for item in read_json(cache / "diagnostics.json") or []:
        reason, _, detail = item["reason"].partition(": ")
        reasons[item["source"]][reason] += 1
        samples.setdefault((item["source"], reason), f"{item['path']}:{item['line']}")
        if reason == "unavailable":
            missing[item["source"]].update(name.strip() for name in detail.split(","))
    kept: Counter = Counter()
    catalog = config.paths.data / "current" / "catalog.jsonl"
    if catalog.exists():
        for line in catalog.read_text().splitlines():
            kept.update({origin["source"] for origin in json.loads(line)["origins"]})
    custom = Source(
        "custom",
        str(config.paths.data / "custom"),
        "custom",
        transport="local",
        license="personal",
        priority=0,
    )
    rows = []
    for source in [custom, *config.sources]:
        pointer = read_json(cache / "sources" / source.id / "current.json") or {}
        report = reports.get(source.id, {})
        if source.id == "custom":
            status = "local"
        else:
            status = report.get("status") or ("cached" if pointer else "never synced")
        revision = report.get("revision") or pointer.get("revision", "")
        checked = report.get("checked_at") or pointer.get("checked_at", "")
        rows.append(
            {
                "id": source.id,
                "enabled": source.enabled,
                "adapter": source.adapter,
                "license": source.license,
                "url": source.url,
                "status": status,
                "revision": revision,
                "checked_at": checked,
                "parsed": report.get("parsed"),
                "rejected": report.get("rejected"),
                "kept": kept.get(source.id, 0),
                "message": report.get("message", ""),
                "reasons": [
                    {"reason": reason, "count": count, "sample": samples[(source.id, reason)]}
                    for reason, count in sorted(
                        reasons[source.id].items(), key=lambda item: (-item[1], item[0])
                    )
                ],
                "missing_commands": [
                    {"command": name, "count": count}
                    for name, count in sorted(
                        missing[source.id].items(), key=lambda item: (-item[1], item[0])
                    )[:10]
                ],
            }
        )
    return rows


def status_color(status: str) -> str:
    if status in {"failed", "missing", "never synced"}:
        return "error"
    if status in {"stale", "cached"}:
        return "warning"
    return "success"


def cells(row: dict) -> dict[str, str]:
    def number(value: int | None) -> str:
        return "-" if value is None else str(value)

    return {
        "id": row["id"],
        "on": "yes" if row["enabled"] else "no",
        "adapter": row["adapter"],
        "license": row["license"],
        "status": row["status"],
        "short_revision": row["revision"][:12] or "-",
        "checked": row["checked_at"][:16].replace("T", " ") or "-",
        "parsed": number(row["parsed"]),
        "rejected": number(row["rejected"]),
        "kept": str(row["kept"]),
    }


def table(rows: list[dict], *, colored: bool) -> str:
    values = [cells(row) for row in rows]
    widths = {
        key: max(len(title), *(len(value[key]) for value in values)) for title, key in COLUMNS
    }

    def line(value: dict[str, str], row: dict | None) -> str:
        parts = []
        for _, key in COLUMNS:
            text = (
                value[key].rjust(widths[key]) if key in NUMERIC else value[key].ljust(widths[key])
            )
            if row is not None and key == "status":
                text = style(text, status_color(row["status"]), colored)
            elif row is not None and key == "on" and not row["enabled"]:
                text = style(text, "warning", colored)
            parts.append(text)
        return "  ".join(parts).rstrip()

    header = line({key: title for title, key in COLUMNS}, None)
    return "\n".join(
        [style(header, "accent", colored), *(line(v, r) for v, r in zip(values, rows))]
    )


def detail(row: dict, *, colored: bool) -> str:
    value = cells(row)
    fields = [
        ("enabled", value["on"]),
        ("adapter", row["adapter"]),
        ("url", row["url"]),
        ("license", row["license"]),
        ("status", style(row["status"], status_color(row["status"]), colored)),
        ("revision", row["revision"] or "-"),
        ("checked", value["checked"]),
        ("examples", f"{value['parsed']} parsed, {value['rejected']} rejected, {row['kept']} kept"),
    ]
    if row["message"]:
        fields.append(("message", row["message"]))
    output = [style(row["id"], "accent", colored)]
    output += [f"  {name:<9} {text}" for name, text in fields]
    if row["reasons"]:
        width = max(len(str(item["count"])) for item in row["reasons"])
        output.append(style("Skipped examples by reason (last sync)", "accent", colored))
        output += [
            f"  {str(item['count']).rjust(width)}  {item['reason']}  ({item['sample']})"
            for item in row["reasons"]
        ]
    if row["missing_commands"]:
        width = max(len(str(item["count"])) for item in row["missing_commands"])
        output.append(style("Most common missing commands", "accent", colored))
        output += [
            f"  {str(item['count']).rjust(width)}  {item['command']}"
            for item in row["missing_commands"]
        ]
    return "\n".join(output)
