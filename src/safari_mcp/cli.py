"""safari-mcp CLI: drive Safari from the command line."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import (
    SafariNotAvailable,
    SafariScriptError,
    click as safari_click,
    close_tab,
    element_exists,
    fill,
    list_tabs,
    open_url,
    read_page,
    run_js,
    wait_for_selector,
)


def _target_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--window", type=int, default=None, help="1-based window index (default: frontmost)")
    p.add_argument("--tab", type=int, default=None, help="1-based tab index within --window (default: current tab)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="safari-mcp",
        description=(
            "Drive Safari.app on macOS: navigate, read page content, click, "
            "and fill forms, via Apple's JavaScript for Automation (JXA). "
            "Reuses your real, already-logged-in Safari session -- no "
            "separate automation profile."
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    p_tabs = sub.add_parser("tabs", help="List every open tab across every Safari window")
    p_tabs.add_argument("--json", action="store_true")

    p_open = sub.add_parser("open", help="Navigate to a URL")
    p_open.add_argument("url")
    p_open.add_argument("--new-tab", action="store_true", help="Open in a new tab instead of the current one")
    p_open.add_argument("--no-wait", action="store_true", help="Don't wait for the page to finish loading")
    p_open.add_argument("--json", action="store_true")

    p_close = sub.add_parser("close", help="Close a tab")
    _target_args(p_close)

    p_read = sub.add_parser("read", help="Read the target tab's URL, title, and visible text")
    _target_args(p_read)
    p_read.add_argument("--html", action="store_true", help="Also include full outerHTML")
    p_read.add_argument("--json", action="store_true")

    p_js = sub.add_parser("js", help="Evaluate arbitrary JavaScript in the target tab and print the result")
    _target_args(p_js)
    p_js.add_argument("code", help="JavaScript source to evaluate")

    p_click = sub.add_parser("click", help="Click the first element matching a CSS selector")
    _target_args(p_click)
    p_click.add_argument("selector")

    p_fill = sub.add_parser("fill", help="Set an input/textarea's value via CSS selector")
    _target_args(p_fill)
    p_fill.add_argument("selector")
    p_fill.add_argument("value")

    p_exists = sub.add_parser("exists", help="Check whether a CSS selector matches any element")
    _target_args(p_exists)
    p_exists.add_argument("selector")

    p_wait = sub.add_parser("wait", help="Poll until a CSS selector matches, or time out")
    _target_args(p_wait)
    p_wait.add_argument("selector")
    p_wait.add_argument("--timeout", type=float, default=10.0, help="Seconds to wait (default 10)")

    return p


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except SafariNotAvailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except SafariScriptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _dispatch(args) -> int:
    if args.command == "tabs":
        tabs = list_tabs()
        if args.json:
            print(json.dumps([t.__dict__ for t in tabs], indent=2))
            return 0
        if not tabs:
            print("No Safari tabs are open.")
            return 0
        for t in tabs:
            marker = "*" if t.is_current else " "
            print(f"{marker} [{t.window_index}:{t.tab_index}] {t.title!r} -- {t.url}")
        return 0

    if args.command == "open":
        tab = open_url(args.url, new_tab=args.new_tab, wait_for_load=not args.no_wait)
        if args.json:
            print(json.dumps(tab.__dict__, indent=2))
        else:
            print(f"[{tab.window_index}:{tab.tab_index}] {tab.title!r} -- {tab.url}")
        return 0

    if args.command == "close":
        close_tab(window_index=args.window, tab_index=args.tab)
        print("Closed.")
        return 0

    if args.command == "read":
        page = read_page(window_index=args.window, tab_index=args.tab, include_html=args.html)
        if args.json:
            print(json.dumps(page.__dict__, indent=2))
        else:
            print(f"URL:   {page.url}")
            print(f"Title: {page.title}")
            print()
            print(page.text or "")
            if args.html:
                print()
                print("--- HTML ---")
                print(page.html or "")
        return 0

    if args.command == "js":
        result = run_js(args.code, window_index=args.window, tab_index=args.tab)
        print(result)
        return 0

    if args.command == "click":
        found = safari_click(args.selector, window_index=args.window, tab_index=args.tab)
        print("clicked" if found else "not found")
        return 0 if found else 1

    if args.command == "fill":
        found = fill(args.selector, args.value, window_index=args.window, tab_index=args.tab)
        print("filled" if found else "not found")
        return 0 if found else 1

    if args.command == "exists":
        found = element_exists(args.selector, window_index=args.window, tab_index=args.tab)
        print("yes" if found else "no")
        return 0 if found else 1

    if args.command == "wait":
        found = wait_for_selector(
            args.selector, timeout_seconds=args.timeout, window_index=args.window, tab_index=args.tab
        )
        print("found" if found else "timed out")
        return 0 if found else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
