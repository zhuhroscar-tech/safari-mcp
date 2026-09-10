"""safari-mcp MCP server: expose Safari automation as MCP tools.

Supports both mcp<2 (FastMCP) and mcp>=2 (MCPServer, renamed) SDK majors.
"""
from __future__ import annotations

from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP

from . import core

mcp = FastMCP("safari-mcp")


def _guard(fn, *args, **kwargs):
    """Convert our domain exceptions into a plain error string instead of
    letting them propagate as an MCP tool-call failure with a raw
    traceback -- the calling agent gets an actionable message either way,
    but a clean string is easier for it to read and relay to the user."""
    try:
        return fn(*args, **kwargs)
    except (core.SafariNotAvailable, core.SafariScriptError) as exc:
        return {"error": str(exc)}


@mcp.tool()
def safari_tabs() -> list:
    """List every open tab across every Safari window. Each entry has
    window_index, tab_index, url, title, and is_current (whether it's
    that window's frontmost tab)."""
    result = _guard(core.list_tabs)
    if isinstance(result, dict):
        return result
    return [t.__dict__ for t in result]


@mcp.tool()
def safari_open(url: str, new_tab: bool = False, wait_for_load: bool = True) -> dict:
    """Navigate Safari to a URL. Reuses the real, already-logged-in Safari
    session (cookies, extensions, everything) rather than a separate
    automation profile. With new_tab=True opens a new tab; otherwise
    navigates the frontmost window's current tab in place. Waits for the
    page to finish loading by default so the returned title is accurate."""
    result = _guard(core.open_url, url, new_tab=new_tab, wait_for_load=wait_for_load)
    if isinstance(result, dict):
        return result
    return result.__dict__


@mcp.tool()
def safari_close(window: Optional[int] = None, tab: Optional[int] = None) -> dict:
    """Close a Safari tab. Omit both arguments to close the frontmost
    window's current tab."""
    result = _guard(core.close_tab, window_index=window, tab_index=tab)
    if isinstance(result, dict):
        return result
    return {"closed": True}


@mcp.tool()
def safari_read(window: Optional[int] = None, tab: Optional[int] = None, include_html: bool = False) -> dict:
    """Read a Safari tab's URL, title, and visible text (document.body's
    innerText). Set include_html=True to also get the full outerHTML.
    Omit window/tab to read the frontmost window's current tab."""
    result = _guard(core.read_page, window_index=window, tab_index=tab, include_html=include_html)
    if isinstance(result, dict):
        return result
    return result.__dict__


@mcp.tool()
def safari_js(code: str, window: Optional[int] = None, tab: Optional[int] = None) -> dict:
    """Evaluate arbitrary JavaScript in a Safari tab's page context and
    return the string-coerced result. Requires Safari's Develop menu >
    'Allow JavaScript from Apple Events' to be enabled."""
    result = _guard(core.run_js, code, window_index=window, tab_index=tab)
    if isinstance(result, dict):
        return result
    return {"result": result}


@mcp.tool()
def safari_click(selector: str, window: Optional[int] = None, tab: Optional[int] = None) -> dict:
    """Click the first element matching a CSS selector in a Safari tab.
    Returns found=False (not an error) if nothing matched the selector."""
    result = _guard(core.click, selector, window_index=window, tab_index=tab)
    if isinstance(result, dict):
        return result
    return {"found": result}


@mcp.tool()
def safari_fill(selector: str, value: str, window: Optional[int] = None, tab: Optional[int] = None) -> dict:
    """Set an <input>/<textarea>'s value via a CSS selector, dispatching
    real 'input'/'change' events so JS-framework-backed forms (React,
    Vue, ...) observe the change. Returns found=False (not an error) if
    nothing matched the selector."""
    result = _guard(core.fill, selector, value, window_index=window, tab_index=tab)
    if isinstance(result, dict):
        return result
    return {"found": result}


@mcp.tool()
def safari_element_exists(selector: str, window: Optional[int] = None, tab: Optional[int] = None) -> dict:
    """Check whether a CSS selector matches any element in a Safari tab."""
    result = _guard(core.element_exists, selector, window_index=window, tab_index=tab)
    if isinstance(result, dict):
        return result
    return {"exists": result}


@mcp.tool()
def safari_wait_for(
    selector: str,
    timeout_seconds: float = 10.0,
    window: Optional[int] = None,
    tab: Optional[int] = None,
) -> dict:
    """Poll a Safari tab until a CSS selector matches an element, or
    time out. Useful after a click/navigation that loads content
    asynchronously. Returns found=False (not an error) on timeout."""
    result = _guard(
        core.wait_for_selector, selector, timeout_seconds=timeout_seconds, window_index=window, tab_index=tab
    )
    if isinstance(result, dict):
        return result
    return {"found": result}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
