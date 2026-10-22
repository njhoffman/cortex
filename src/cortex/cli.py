"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from cortex import __version__
from cortex.config import Paths, load
from cortex.model import CortexError
from cortex.sync import run


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="cortex", description="Merge locally available Linux command cheatsheets."
    )
    root.add_argument("-v", "--version", action="version", version=f"cortex {__version__}")
    root.add_argument(
        "--config", help="configuration file (default: XDG_CONFIG_HOME/cortex/config.toml)"
    )
    commands = root.add_subparsers(dest="command", required=True)
    sync = commands.add_parser(
        "sync", help="refresh sources and publish a local command collection"
    )
    sync.add_argument("-v", "--version", action="version", version=f"cortex {__version__}")
    sync.add_argument(
        "--source",
        action="append",
        metavar="ID",
        help="refresh only this enabled source (repeatable)",
    )
    sync.add_argument(
        "--offline", action="store_true", help="rebuild cached sources without network access"
    )
    sync.add_argument("--force", action="store_true", help="bypass fetch/reparse shortcuts")
    sync.add_argument("--json", action="store_true", help="write a JSON report to stdout")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load(Paths.discover(args.config))
        status, report = run(
            config,
            source_ids=args.source,
            offline=args.offline,
            force=args.force,
            progress=lambda message: print(message, file=sys.stderr, flush=True),
        )
        for source in report["sources"]:
            suffix = f" — {source['message']}" if source["message"] else ""
            print(
                f"{source['id']:<16} {source['status']:<10} {source['parsed']:>6} examples{suffix}",
                file=sys.stderr,
            )
        if "error" in report:
            print(f"cortex: {report['error']}", file=sys.stderr)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        elif report["published"]:
            counts = report["counts"]
            print(
                f"Published {counts['retained']} examples for {report['commands']} commands "
                f"({counts['duplicate']} duplicates, {counts['unavailable']} unavailable, "
                f"{counts['unsupported']} unsupported, {counts['excluded']} excluded)."
            )
            print(config.paths.data / "current/commands.md")
        return status
    except (CortexError, OSError) as exc:
        if args.json:
            print(json.dumps({"published": False, "error": str(exc)}))
        print(f"cortex: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("cortex: interrupted; active snapshot retained", file=sys.stderr)
        return 130
