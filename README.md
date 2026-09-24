[![English](https://img.shields.io/badge/English-555555?style=flat)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-555555?style=flat)](README.zh-CN.md)

# safari-mcp

Control your real Safari.app session on macOS through an MCP server, CLI, or Python library. The project uses Apple's JavaScript for Automation (JXA) to navigate tabs, read pages, run JavaScript, click CSS-selected elements, and fill forms.

**This is your existing signed-in browser, not an isolated automation profile.** Actions can affect real accounts and pages. Connect only trusted agents and review consequential actions before execution.

## Install and permissions

Requires macOS, Safari, and Python 3.10+. pip installs the MCP dependency.

```bash
git clone https://github.com/zhuhroscar-tech/safari-mcp.git
cd safari-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Enable both permissions:

1. Allow the launching terminal/app to control Safari under **System Settings → Privacy & Security → Automation** when prompted.
2. In Safari Settings → Advanced, enable **Show features for web developers**, then select **Develop → Allow JavaScript from Apple Events**. This is required for page JavaScript operations; tab listing, opening, and closing do not require it.

## Connect an MCP host

For hosts using `mcpServers` configuration:

```json
{
  "mcpServers": {
    "safari": {
      "command": "/absolute/path/to/safari-mcp/.venv/bin/safari-mcp-server"
    }
  }
}
```

Replace the path with your installation's executable. The server uses stdio and exposes `safari_tabs`, `safari_open`, `safari_close`, `safari_read`, `safari_js`, `safari_click`, `safari_fill`, `safari_element_exists`, and `safari_wait_for`.

## CLI and Python

```bash
safari-mcp tabs
safari-mcp open "https://example.com" --new-tab
safari-mcp read --json
safari-mcp read --window 1 --tab 1
```

Targeted commands default to the frontmost window's current tab. Window and tab indices are one-based; use `--help` for supported targeting flags.

```python
from safari_mcp.core import list_tabs, read_page

print(list_tabs())
page = read_page()
print(page.title, page.text[:100])
```

## Boundaries

This is DOM automation, not screenshot or coordinate-based interaction. There is no sandbox or incognito isolation, and no Linux/Windows support. The wrapper has no telemetry or separate network client, but browser navigation and page actions can send network requests and change account state. Page content passed to an agent is subject to that host's data handling.

## Preview and development

[Example output](docs/images/example-output.png) · [Demo video](docs/demo.mp4)

```bash
python -m pip install -e ".[dev]"
python -m pytest -v
# Optional: real Safari; requires permissions and an open browser
python tests/e2e_mcp_roundtrip.py
```

[CI](.github/workflows/ci.yml) tests mocked Safari interaction and packaging; it does not establish live Safari behavior. [API implementation](src/safari_mcp/core.py) · [Release history](CHANGELOG.md) · [MIT license](LICENSE)
