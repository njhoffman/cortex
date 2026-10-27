"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys

from cortex import __version__
from cortex.config import Paths, load
from cortex.lookup import (
    SHORT_ID,
    command_table,
    commands,
    find_by_id,
    load_snapshot,
    render,
    search,
    show,
)
from cortex.manage import Exclusions, add
from cortex.model import CortexError, Example
from cortex.progress import SyncDisplay, clean, style, summary, use_color
from cortex.status import collect, detail, table
from cortex.sync import run


def parser() -> argparse.ArgumentParser:
    color = argparse.ArgumentParser(add_help=False)
    color.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="terminal colors (default: auto; honors NO_COLOR and TERM=dumb)",
    )
    rebuild = argparse.ArgumentParser(add_help=False)
    rebuild.add_argument(
        "--no-sync",
        action="store_true",
        help="skip the offline rebuild; run `cortex sync --offline` later",
    )
    root = argparse.ArgumentParser(
        prog="cortex", description="Merge locally available Linux command cheatsheets."
    )
    root.add_argument("-v", "--version", action="version", version=f"cortex {__version__}")
    root.add_argument(
        "--config", help="configuration file (default: XDG_CONFIG_HOME/cortex/config.toml)"
    )
    subcommands = root.add_subparsers(dest="command", required=True)
    sync = subcommands.add_parser(
        "sync", parents=[color], help="refresh sources and publish a local command collection"
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
    sources = subcommands.add_parser(
        "sources",
        parents=[color],
        help="show configured sources and their last sync status (offline)",
    )
    sources.add_argument("id", nargs="?", help="show one source with rejection reasons")
    sources.add_argument("--json", action="store_true", help="write source status as JSON")

    listing = subcommands.add_parser(
        "list", parents=[color], help="list catalog commands with example counts"
    )
    listing.add_argument("--category", help="only commands with examples in this category")
    listing.add_argument("--json", action="store_true", help="write commands as JSON")
    showing = subcommands.add_parser("show", parents=[color], help="show a command's examples")
    showing.add_argument("name", metavar="command")
    showing.add_argument("subcommand", nargs="?", help="only this subcommand, e.g. `git commit`")
    searching = subcommands.add_parser(
        "search", parents=[color], help="search commands, descriptions, and templates"
    )
    searching.add_argument("terms", nargs="+", help="every term must match")
    searching.add_argument(
        "--limit", type=int, default=50, help="maximum examples to show (default: 50)"
    )
    for lookup in (showing, searching):
        lookup.add_argument(
            "--origins", action="store_true", help="show sources, locations, and licenses"
        )
        lookup.add_argument("--json", action="store_true", help="write examples as JSON")

    adding = subcommands.add_parser(
        "add", parents=[color, rebuild], help="add a personal example to custom/<command>.cheat"
    )
    adding.add_argument("template", metavar="command", help="the command line, quoted")
    adding.add_argument("-d", "--description", required=True, help="one-line description")
    removing = subcommands.add_parser(
        "remove", parents=[color, rebuild], help="remember the removal of an example or command"
    )
    restoring = subcommands.add_parser(
        "restore",
        parents=[color, rebuild],
        help="undo a remembered removal; without arguments, list removals",
    )
    for manage in (removing, restoring):
        target = manage.add_mutually_exclusive_group(required=manage is removing)
        target.add_argument("id", nargs="?", help="example ID or unique prefix (6+ characters)")
        target.add_argument("--command", dest="name", metavar="NAME", help="a whole command")
    return root


def show_sources(config, args: argparse.Namespace) -> int:
    rows = collect(config)
    if args.id:
        rows = [row for row in rows if row["id"] == args.id]
        if not rows:
            raise CortexError(f"Unknown source: {args.id}")
    if args.json:
        print(json.dumps(rows[0] if args.id else rows, indent=2, sort_keys=True))
        return 0
    colored = use_color(sys.stdout, args.color)
    print(detail(rows[0], colored=colored) if args.id else table(rows, colored=colored))
    return 0


def lookup(config, args: argparse.Namespace) -> int:
    snapshot = load_snapshot(config)
    colored = use_color(sys.stdout, args.color)
    if args.command == "list":
        rows = commands(snapshot.examples, args.category)
        print(json.dumps(rows, indent=2) if args.json else command_table(rows, colored=colored))
        return 0
    if args.command == "show":
        examples = show(snapshot.examples, args.name, args.subcommand)
        if not examples:
            target = f"{args.name} {args.subcommand or ''}".strip()
            raise CortexError(f"No examples for {target}; try `cortex search {args.name}`.")
    else:
        if args.limit < 1:
            raise CortexError("--limit must be at least 1.")
        examples = search(snapshot.examples, args.terms, args.limit)
        if not examples and not args.json:
            print("No matches.", file=sys.stderr)
            return 1
    if args.json:
        print(json.dumps([example.to_dict() for example in examples], indent=2, sort_keys=True))
    else:
        print(render(examples, colored=colored, origins=args.origins))
    return 0 if examples else 1


def change(config, args: argparse.Namespace) -> int:
    colored = use_color(sys.stdout, args.color)
    if args.command == "add":
        path, missing = add(config, args.template, args.description)
        print(f"Added to {path}")
        if missing:
            print(
                style(
                    "cortex: warning: not installed, so sync will skip it: " + ", ".join(missing),
                    "warning",
                    use_color(sys.stderr, args.color),
                ),
                file=sys.stderr,
            )
        return rebuild(config, args)
    exclusions = Exclusions.read(config)
    if args.command == "restore" and not args.id and not args.name:
        known = {example.id: example for example in load_snapshot(config).excluded}
        if not exclusions.ids and not exclusions.commands:
            print("No remembered removals.")
        for name in sorted(exclusions.commands):
            print(f"{style('command', 'dim', colored)}  {name}")
        for identifier in sorted(exclusions.ids):
            example = known.get(identifier)
            text = f"{example.command}: {example.description}" if example else "(not in catalog)"
            print(f"{style(identifier[:SHORT_ID], 'dim', colored)}  {text}")
        return 0
    if args.name:
        names = exclusions.commands
        if args.command == "remove":
            if args.name in names:
                print(f"{args.name} is already removed.")
                return 0
            if not show(load_snapshot(config).examples, args.name):
                raise CortexError(f"No examples for {args.name} in the catalog.")
            names.add(args.name)
            message = f"Removed command {args.name}"
        else:
            if args.name not in names:
                raise CortexError(f"{args.name} is not a removed command.")
            names.remove(args.name)
            message = f"Restored command {args.name}"
    elif args.command == "remove":
        if any(identifier.startswith(args.id.lower()) for identifier in exclusions.ids):
            print(f"{args.id} is already removed.")
            return 0
        example = find_by_id(args.id, load_snapshot(config).examples)
        exclusions.ids.add(example.id)
        message = f"Removed {example.id[:SHORT_ID]} ({example.command}: {example.description})"
    else:
        known = {example.id: example for example in load_snapshot(config).excluded}
        # Removed IDs may no longer exist upstream; match them even without a record.
        candidates = [known.get(item) or Example("", "", [], id=item) for item in exclusions.ids]
        identifier = find_by_id(args.id, candidates).id
        exclusions.ids.remove(identifier)
        message = f"Restored {identifier[:SHORT_ID]}"
    exclusions.write()
    print(message)
    return rebuild(config, args)


def rebuild(config, args: argparse.Namespace) -> int:
    if args.no_sync:
        print("Run `cortex sync --offline` to apply the change.")
        return 0
    return synchronize(config, args, offline=True, show_path=False)


def synchronize(
    config,
    args: argparse.Namespace,
    *,
    offline: bool,
    source_ids: list[str] | None = None,
    force: bool = False,
    show_path: bool = True,
) -> int:
    json_output = getattr(args, "json", False)
    with SyncDisplay(
        [source.id for source in config.sources if source.enabled],
        color=args.color,
        json_output=json_output,
    ) as display:
        status, report = run(
            config,
            source_ids=source_ids,
            offline=offline,
            force=force,
            progress=display.update,
        )
        display.finish(status)
    for warning in report.get("warnings", []):
        print(
            style(f"cortex: warning: {clean(warning)}", "warning", display.colored),
            file=sys.stderr,
        )
    if "error" in report:
        print(
            style(f"cortex: {clean(report['error'])}", "error", display.colored),
            file=sys.stderr,
        )
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["published"]:
        print(summary(report, colored=use_color(sys.stdout, args.color)))
        if show_path:
            print(config.paths.data / "current/commands.md")
    return status


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    json_output = getattr(args, "json", False)
    try:
        config = load(Paths.discover(args.config))
        if args.command == "sources":
            status = show_sources(config, args)
        elif args.command in {"list", "show", "search"}:
            status = lookup(config, args)
        elif args.command in {"add", "remove", "restore"}:
            status = change(config, args)
        else:
            status = synchronize(
                config, args, offline=args.offline, source_ids=args.source, force=args.force
            )
        # Flush here so a closed pipe is handled below instead of at interpreter exit.
        sys.stdout.flush()
        return status
    except BrokenPipeError:  # before OSError, its base class
        # A pager or `head` closed the pipe; stop quietly like other filters.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141
    except (CortexError, OSError) as exc:
        if json_output and args.command == "sync":
            print(json.dumps({"published": False, "error": str(exc)}))
        print(
            style(
                f"cortex: {clean(str(exc))}",
                "error",
                use_color(sys.stderr, args.color, json_output=json_output),
            ),
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("cortex: interrupted; active snapshot retained", file=sys.stderr)
        return 130
