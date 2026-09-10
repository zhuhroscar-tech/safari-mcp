# safari-mcp

Drive Safari.app on macOS — navigate, read page content, click, and fill
forms — from an MCP-capable agent (Claude, Hermes, any MCP host), a CLI,
or a plain Python library. Uses Apple's own JavaScript for Automation
(JXA), so it drives your **real, already-logged-in Safari window**:
existing cookies, sessions, extensions, and tabs — not a separate
automation profile you'd have to log into again.

## Why this exists

Every popular browser-automation stack (Playwright, Puppeteer, Selenium,
`browser-use`) targets Chromium's DevTools Protocol or WebDriver. Safari
has neither. If your default browser is Safari, or you specifically want
an agent to act *as you, in your actual signed-in session* rather than
spin up an isolated Chromium profile, none of those tools apply. Apple
ships a real, supported automation surface for exactly this —
`osascript -l JavaScript` driving `Application("Safari")` — but it's raw
AppleScript/JXA with no MCP wrapper. This project is that wrapper.

## What this does NOT do

- **No screenshotting / pixel-level interaction.** JXA drives the DOM via
  JavaScript, not the rendered pixels — there's no `click_at_xy` here.
  If you need visual/pixel automation, pair this with `screencapture` and
  a separate coordinate-clicking tool (e.g. `cliclick`), which this
  project deliberately does not bundle to stay focused.
- **No sandboxed/incognito session.** By design, this reuses your real
  Safari session. If you want isolation, use a Chromium-based automation
  tool instead — that's a feature, not a gap, but state it up front so
  nobody is surprised their real cookies are visible to the agent.
- **macOS + Safari only.** JXA is an Apple-only automation technology;
  there is no equivalent way to drive Safari from Linux/Windows.

## Install

Requires macOS and Python 3.10+.

```bash
pip install --user safari-mcp
```

or from source:

```bash
git clone https://github.com/zhuhroscar-tech/safari-mcp
cd safari-mcp
pip install --user .
```

### One-time macOS permissions

Two separate permission grants are required, each a normal macOS system
dialog the first time you run a command:

1. **Automation permission** (System Settings → Privacy & Security →
   Automation): the app/terminal running `safari-mcp` needs "Allow" next
   to Safari. macOS prompts for this automatically on first use.
2. **"Allow JavaScript from Apple Events"** in Safari itself: Safari menu
   → Settings → Advanced → enable "Show features for web developers",
   then Safari's Develop menu → check "Allow JavaScript from Apple
   Events". This is required for `read`, `js`, `click`, `fill`, `exists`,
   and `wait` (anything that runs JavaScript in the page) — `open`,
   `tabs`, and `close` work without it.

Every command here raises a clear, actionable error naming exactly which
of these two permissions is missing, rather than a bare AppleEvent error
number.

## Use as an MCP server

Add to your MCP host's config (Claude Desktop, Hermes, etc.) as a stdio
server:

```json
{
  "mcpServers": {
    "safari": {
      "command": "safari-mcp-server"
    }
  }
}
```

Tools exposed: `safari_tabs`, `safari_open`, `safari_close`, `safari_read`,
`safari_js`, `safari_click`, `safari_fill`, `safari_element_exists`,
`safari_wait_for`. Every tool's docstring (visible to the calling agent)
documents its exact behavior and return shape.

## Use as a CLI

```bash
safari-mcp tabs                                    # list every open tab
safari-mcp open "https://example.com"               # navigate current tab
safari-mcp open "https://example.com" --new-tab     # open in a new tab
safari-mcp read                                     # print URL/title/visible text
safari-mcp read --html                              # also include full outerHTML
safari-mcp js "document.title"                      # run arbitrary JS, print result
safari-mcp click "#submit"                          # click a CSS selector
safari-mcp fill "#email" "me@example.com"           # fill an input
safari-mcp exists ".error-banner"                   # check a selector
safari-mcp wait ".results" --timeout 5              # poll for a selector
```

All read/click/fill/exists/wait commands accept `--window N --tab M` to
target a specific tab instead of the frontmost window's current tab.

## Use as a Python library

```python
from safari_mcp.core import open_url, read_page, click, fill

tab = open_url("https://example.com")
page = read_page()
print(page.title, page.text[:100])

click("#menu-button")
fill("#search", "hello world")
```

Every function accepts an injectable `runner` (defaults to
`subprocess.run`) for testing without a real Safari instance.

## A real navigation race this project fixes (and why it matters)

Safari's `tab.name()`/`tab.url()` AppleScript properties, and even
`document.readyState`, report stale/placeholder values for a brief window
immediately after navigation: a brand-new tab's `about:blank` placeholder
document already has a `<body>` and already reports `readyState ===
'complete'` *before* the real page has loaded. A naive
`wait_for_selector("body")` after opening a URL will very often return
immediately against the blank placeholder, and the caller gets `title:
"Untitled"` even though the real page loads correctly moments later.

`open_url()` instead polls until `document.readyState === 'complete'`
**and** the URL differs from the pre-navigation URL (or `about:blank` for
a new tab), so the title and content you get back are always for the
actual destination page. This was caught by hands-on testing against real
Safari, not assumed from the API docs — the fix and its regression tests
are in `src/safari_mcp/core.py` (`wait_for_page_load`).

## Privacy / permissions

No network access of its own, no telemetry. Every function is a thin
wrapper around `osascript -l JavaScript` calling either AppleScript-level
Safari properties (`tabs`, `windows`, `url`, `name`) or
`Safari.doJavaScript()` to run JS in the page you already have open. It
never installs a browser extension, never modifies Safari's settings
beyond what you explicitly ask it to do on a page, and never touches any
tab other than the one you target.

## Development

```bash
git clone https://github.com/zhuhroscar-tech/safari-mcp
cd safari-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v                              # unit tests, no real Safari needed
python3 tests/e2e_mcp_roundtrip.py     # real MCP client <-> real Safari (requires Safari open + permissions granted)
```

CI (`.github/workflows/ci.yml`) runs on `macos-latest` GitHub Actions
runners and covers unit tests (all Safari interaction mocked), CLI
`--help`/`--version` smoke tests, the MCP server module importing
cleanly, and a built-wheel install-and-run check. It does **not** run the
live Safari e2e test above: a fresh CI runner has never granted the
Automation/"Allow JavaScript from Apple Events" permissions (they require
an interactive dialog), so CI cannot prove live Safari behavior — that
verification is manual, done on a real macOS machine with Safari open and
permissions already granted (see this project's own development history
for exactly which bugs that caught, e.g. the navigation race below).

## License

MIT — see [LICENSE](LICENSE).
