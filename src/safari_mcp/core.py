"""Core Safari-automation logic for safari-mcp.

Drives Apple's Safari.app via JavaScript for Automation (JXA) -- the same
`osascript -l JavaScript` mechanism System Events and every "Script Editor"
recipe for Safari has used for years. This module contains zero MCP/CLI
imports so it is independently testable and usable as a plain library.

Why JXA and not a browser-automation protocol (CDP/WebDriver): Safari does
not expose a debugging port the way Chromium browsers do. JXA's
`Safari.doJavaScript(script, {in: document})` is Apple's own supported
automation surface for driving an already-open, already-logged-in Safari
window -- it reuses the user's real cookies/sessions rather than spinning
up an isolated automation profile, which is the whole point of automating
Safari specifically instead of using a Chromium browser tool.

Two one-time macOS permissions are required (System Settings > Privacy &
Security > Automation): this process needs "Allow" for Safari, and Safari
needs "Allow JavaScript from Apple Events" enabled in Safari's own
Develop menu (or Safari > Settings > Advanced > "Show features for web
developers", then Develop > Allow JavaScript from Apple Events). Every
function here raises a clear, actionable error when either is missing
rather than a bare AppleEvent error number.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


class SafariNotAvailable(RuntimeError):
    """Safari itself, or the OS automation permission, is unavailable."""


class SafariScriptError(RuntimeError):
    """The JXA script ran but Safari/AppleEvents reported an error."""


@dataclass
class TabInfo:
    window_index: int
    tab_index: int
    url: str
    title: str
    is_current: bool


@dataclass
class PageContent:
    url: str
    title: str
    text: Optional[str] = None
    html: Optional[str] = None


def _osascript(script: str, runner=subprocess.run, timeout: int = 30) -> str:
    """Run a JXA script via osascript, returning stdout. Raises
    SafariScriptError with the real stderr message on any failure so
    callers see e.g. an actionable permission-denied message instead of a
    bare nonzero exit code."""
    osascript_bin = shutil.which("osascript")
    if not osascript_bin:
        raise SafariNotAvailable(
            "osascript not found -- this tool only works on macOS with the "
            "standard Apple Developer Tools/Xcode Command Line Tools installed."
        )
    try:
        proc = runner(
            [osascript_bin, "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SafariScriptError(
            f"Safari did not respond within {timeout}s. It may be showing a "
            "blocking dialog (e.g. a save/print sheet, or a permission "
            "prompt) -- check Safari directly."
        ) from exc
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if "1743" in stderr or "not allowed to send Apple events" in stderr.lower():
            raise SafariNotAvailable(
                "macOS blocked this automation request. Grant permission in "
                "System Settings > Privacy & Security > Automation: allow "
                "the app running this tool to control Safari. If you just "
                "granted it, you may need to re-run the command once."
            )
        if "not allowed to send apple events for javascript" in stderr.lower() or "-10000" in stderr:
            raise SafariNotAvailable(
                "Safari refused a JavaScript automation command. In Safari, "
                "enable Settings > Advanced > 'Show features for web "
                "developers', then Develop menu > 'Allow JavaScript from "
                "Apple Events'."
            )
        raise SafariScriptError(stderr or f"osascript exited {proc.returncode} with no stderr output")
    return proc.stdout.rstrip("\n")


def _js_string_literal(text: str) -> str:
    """Safely embed arbitrary text as a JS string literal inside a JXA
    -e script (which is itself embedded in a shell argv list -- no shell
    quoting concerns since we pass argv directly, but the JS string still
    needs its own escaping)."""
    return json.dumps(text)


# ---------------------------------------------------------------------------
# Tab / window enumeration and selection
# ---------------------------------------------------------------------------


def list_tabs(runner=subprocess.run) -> list:
    """Return every open tab across every Safari window, in window/tab
    order, each tagged with whether it's that window's current tab."""
    script = """
    (() => {
      const safari = Application("Safari");
      const out = [];
      const windows = safari.windows();
      for (let w = 0; w < windows.length; w++) {
        const win = windows[w];
        let currentIdx = -1;
        try { currentIdx = win.currentTab.index(); } catch (e) {}
        const tabs = win.tabs();
        for (let t = 0; t < tabs.length; t++) {
          const tab = tabs[t];
          out.push({
            window_index: w + 1,
            tab_index: t + 1,
            url: tab.url() || "",
            title: tab.name() || "",
            is_current: tab.index() === currentIdx,
          });
        }
      }
      return JSON.stringify(out);
    })()
    """
    raw = _osascript(script, runner=runner)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SafariScriptError(f"Unexpected osascript output: {raw!r}") from exc
    return [TabInfo(**row) for row in data]


def _target_clause(window_index: Optional[int], tab_index: Optional[int]) -> str:
    """JS snippet that resolves `doc` to the requested window/tab, or the
    frontmost document's tab when both are omitted."""
    if window_index is None and tab_index is None:
        return "const doc = safari.documents[0];"
    win = window_index or 1
    if tab_index is None:
        return f"const doc = safari.windows[{win - 1}].currentTab;"
    return f"const doc = safari.windows[{win - 1}].tabs[{tab_index - 1}];"


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


def open_url(
    url: str,
    new_tab: bool = False,
    wait_for_load: bool = True,
    load_timeout_seconds: float = 15.0,
    runner=subprocess.run,
) -> TabInfo:
    """Open `url`. With new_tab=True, opens a new tab in the frontmost
    window (creating a window first if none exists); otherwise navigates
    the frontmost window's current tab in place.

    By default waits for the page to finish loading (document.readyState
    == 'complete') before returning, so the returned title reflects the
    new page rather than a stale AppleEvent-cached title from before
    navigation (Safari's `tab.name()` property does not update until some
    time after `tab.url = ...` is set, independent of whether the page
    has actually loaded).
    """
    url_lit = _js_string_literal(url)
    previous_url = "about:blank"
    if new_tab:
        script = f"""
        (() => {{
          const safari = Application("Safari");
          safari.activate();
          if (safari.windows.length === 0) {{
            safari.Document().make();
          }}
          const win = safari.windows[0];
          const tab = safari.Tab({{url: {url_lit}}});
          win.tabs.push(tab);
          win.currentTab = tab;
          return JSON.stringify({{
            window_index: 1, tab_index: win.tabs.length,
          }});
        }})()
        """
    else:
        if wait_for_load:
            try:
                previous_url = read_page(runner=runner).url or "about:blank"
            except (SafariNotAvailable, SafariScriptError):
                # No existing tab to read from (e.g. Safari has zero
                # windows) -- about:blank is the correct assumption then.
                previous_url = "about:blank"
        script = f"""
        (() => {{
          const safari = Application("Safari");
          safari.activate();
          if (safari.windows.length === 0) {{
            safari.Document().make();
          }}
          const win = safari.windows[0];
          win.currentTab.url = {url_lit};
          return JSON.stringify({{
            window_index: 1, tab_index: win.currentTab.index(),
          }});
        }})()
        """
    raw = _osascript(script, runner=runner)
    try:
        target = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SafariScriptError(f"Unexpected osascript output: {raw!r}") from exc
    window_index, tab_index = target["window_index"], target["tab_index"]

    if wait_for_load:
        wait_for_page_load(
            timeout_seconds=load_timeout_seconds,
            window_index=window_index,
            tab_index=tab_index,
            previous_url=previous_url,
            runner=runner,
        )

    page = read_page(window_index=window_index, tab_index=tab_index, runner=runner)
    return TabInfo(
        window_index=window_index,
        tab_index=tab_index,
        url=page.url or url,
        title=page.title,
        is_current=True,
    )


def close_tab(window_index: Optional[int] = None, tab_index: Optional[int] = None, runner=subprocess.run) -> None:
    target = _target_clause(window_index, tab_index)
    script = f"""
    (() => {{
      const safari = Application("Safari");
      {target}
      doc.close();
    }})()
    """
    _osascript(script, runner=runner)


# ---------------------------------------------------------------------------
# Reading page content
# ---------------------------------------------------------------------------


def run_js(
    code: str,
    window_index: Optional[int] = None,
    tab_index: Optional[int] = None,
    runner=subprocess.run,
) -> str:
    """Evaluate arbitrary JavaScript in the target tab's page context via
    Safari's doJavaScript, returning its string-coerced result.

    Requires Safari > Develop menu > 'Allow JavaScript from Apple Events'
    (see module docstring) -- raises SafariNotAvailable with instructions
    if that's not enabled.
    """
    target = _target_clause(window_index, tab_index)
    code_lit = _js_string_literal(code)
    script = f"""
    (() => {{
      const safari = Application("Safari");
      {target}
      const result = safari.doJavaScript({code_lit}, {{in: doc}});
      return String(result);
    }})()
    """
    return _osascript(script, runner=runner)


_READ_TEXT_JS = "document.body ? document.body.innerText : ''"
_READ_HTML_JS = "document.documentElement ? document.documentElement.outerHTML : ''"


def read_page(
    window_index: Optional[int] = None,
    tab_index: Optional[int] = None,
    include_html: bool = False,
    runner=subprocess.run,
) -> PageContent:
    """Read the target tab's URL, title, and visible text (and optionally
    full HTML) in one round trip."""
    target = _target_clause(window_index, tab_index)
    html_snippet = f'html: safari.doJavaScript({_js_string_literal(_READ_HTML_JS)}, {{in: doc}})' if include_html else "html: null"
    script = f"""
    (() => {{
      const safari = Application("Safari");
      {target}
      const text = safari.doJavaScript({_js_string_literal(_READ_TEXT_JS)}, {{in: doc}});
      const result = {{
        url: doc.url() || "",
        title: doc.name() || "",
        text: text,
        {html_snippet}
      }};
      return JSON.stringify(result);
    }})()
    """
    raw = _osascript(script, runner=runner)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SafariScriptError(f"Unexpected osascript output: {raw!r}") from exc
    return PageContent(**data)


# ---------------------------------------------------------------------------
# Interaction: click, type, fill forms
# ---------------------------------------------------------------------------


def click(
    selector: str,
    window_index: Optional[int] = None,
    tab_index: Optional[int] = None,
    runner=subprocess.run,
) -> bool:
    """Click the first element matching a CSS selector. Returns True if an
    element was found and clicked, False if the selector matched nothing
    (never raises for a missing element -- that's a normal outcome to
    check, not an automation failure)."""
    selector_lit = _js_string_literal(selector)
    js = (
        f"(() => {{ const el = document.querySelector({selector_lit}); "
        "if (!el) return 'false'; el.click(); return 'true'; })()"
    )
    result = run_js(js, window_index=window_index, tab_index=tab_index, runner=runner)
    return result.strip() == "true"


def fill(
    selector: str,
    value: str,
    window_index: Optional[int] = None,
    tab_index: Optional[int] = None,
    runner=subprocess.run,
) -> bool:
    """Set an <input>/<textarea>'s value via its CSS selector and dispatch
    real 'input' and 'change' events (so frameworks like React that listen
    for those events observe the change, not just the raw DOM property).
    Returns True if an element was found and filled, False otherwise."""
    selector_lit = _js_string_literal(selector)
    value_lit = _js_string_literal(value)
    js = f"""
    (() => {{
      const el = document.querySelector({selector_lit});
      if (!el) return 'false';
      const proto = Object.getPrototypeOf(el);
      const setter = Object.getOwnPropertyDescriptor(proto, 'value');
      if (setter && setter.set) {{ setter.set.call(el, {value_lit}); }}
      else {{ el.value = {value_lit}; }}
      el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      el.dispatchEvent(new Event('change', {{ bubbles: true }}));
      return 'true';
    }})()
    """
    result = run_js(js, window_index=window_index, tab_index=tab_index, runner=runner)
    return result.strip() == "true"


def element_exists(
    selector: str,
    window_index: Optional[int] = None,
    tab_index: Optional[int] = None,
    runner=subprocess.run,
) -> bool:
    selector_lit = _js_string_literal(selector)
    js = f"document.querySelector({selector_lit}) !== null"
    result = run_js(js, window_index=window_index, tab_index=tab_index, runner=runner)
    return result.strip() == "true"


def wait_for_selector(
    selector: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.5,
    window_index: Optional[int] = None,
    tab_index: Optional[int] = None,
    runner=subprocess.run,
    sleep=None,
) -> bool:
    """Poll until an element matching `selector` appears, or timeout.
    Returns True if found in time, False on timeout (never raises for a
    timeout -- that's a normal, checkable outcome)."""
    import time as _time

    sleep = sleep or _time.sleep
    deadline = _time.monotonic() + timeout_seconds
    while True:
        if element_exists(selector, window_index=window_index, tab_index=tab_index, runner=runner):
            return True
        if _time.monotonic() >= deadline:
            return False
        sleep(poll_interval)


_PAGE_LOADED_JS_TEMPLATE = "document.readyState === 'complete' && document.URL !== {excluded_url}"


def wait_for_page_load(
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.2,
    window_index: Optional[int] = None,
    tab_index: Optional[int] = None,
    previous_url: str = "about:blank",
    runner=subprocess.run,
    sleep=None,
) -> bool:
    """Poll until the target tab has actually navigated away from
    `previous_url` and finished loading, or timeout.

    This is NOT the same check as wait_for_selector("body"): a page's
    <body> exists and readyState already reports 'complete' for the OLD
    document (a brand-new tab's about:blank placeholder, or the
    previously-loaded page before an in-place navigation starts) before
    the real navigation has begun -- polling for "body" alone races and
    can return before the target URL has loaded at all. This instead
    requires readyState to be 'complete' AND the URL to differ from
    `previous_url` (the blank placeholder for a new tab, or the prior
    page's URL for an in-place navigation).

    Returns True if the page loaded in time, False on timeout (never
    raises for a timeout -- open_url() treats a timeout as "proceed
    anyway and let the caller see whatever state is there", not a fatal
    error, since the page may simply be slow rather than broken).
    """
    import time as _time

    sleep = sleep or _time.sleep
    js = _PAGE_LOADED_JS_TEMPLATE.format(excluded_url=_js_string_literal(previous_url))
    deadline = _time.monotonic() + timeout_seconds
    while True:
        result = run_js(js, window_index=window_index, tab_index=tab_index, runner=runner)
        if result.strip() == "true":
            return True
        if _time.monotonic() >= deadline:
            return False
        sleep(poll_interval)
