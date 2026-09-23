import json
import subprocess
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility for tests.
    import tomli as tomllib

import pytest

from safari_mcp.core import (
    PageContent,
    SafariNotAvailable,
    SafariScriptError,
    TabInfo,
    _osascript,
    click,
    close_tab,
    element_exists,
    fill,
    list_tabs,
    open_url,
    read_page,
    run_js,
    wait_for_page_load,
    wait_for_selector,
)


def fake_runner(stdout: str = "", returncode: int = 0, stderr: str = ""):
    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return runner


def test_osascript_raises_not_available_on_automation_permission_denied():
    runner = fake_runner(returncode=1, stderr="osascript: not allowed to send Apple events. (-1743)")
    with pytest.raises(SafariNotAvailable, match="Automation"):
        _osascript("1+1", runner=runner)


def test_osascript_raises_not_available_on_javascript_permission_denied():
    runner = fake_runner(
        returncode=1,
        stderr="Error: Safari got an error: Not allowed to send Apple events for JavaScript. (-10000)",
    )
    with pytest.raises(SafariNotAvailable, match="Allow JavaScript from Apple Events"):
        _osascript("1+1", runner=runner)


def test_osascript_raises_script_error_on_other_failure():
    runner = fake_runner(returncode=1, stderr="some other applescript error")
    with pytest.raises(SafariScriptError, match="some other applescript error"):
        _osascript("1+1", runner=runner)


def test_osascript_strips_trailing_newline():
    runner = fake_runner(stdout="hello\n")
    assert _osascript("x", runner=runner) == "hello"


def test_list_tabs_parses_json():
    sample = [
        {"window_index": 1, "tab_index": 1, "url": "https://a.com", "title": "A", "is_current": True},
        {"window_index": 1, "tab_index": 2, "url": "https://b.com", "title": "B", "is_current": False},
    ]
    runner = fake_runner(stdout=json.dumps(sample))
    tabs = list_tabs(runner=runner)
    assert len(tabs) == 2
    assert tabs[0] == TabInfo(1, 1, "https://a.com", "A", True)
    assert tabs[1].is_current is False


def test_list_tabs_raises_on_garbage_output():
    runner = fake_runner(stdout="not json")
    with pytest.raises(SafariScriptError):
        list_tabs(runner=runner)


def test_run_js_returns_stdout_as_string():
    runner = fake_runner(stdout="42")
    assert run_js("21*2", runner=runner) == "42"


def test_read_page_parses_content():
    sample = {"url": "https://x.com", "title": "X", "text": "hello world", "html": None}
    runner = fake_runner(stdout=json.dumps(sample))
    page = read_page(runner=runner)
    assert page == PageContent("https://x.com", "X", "hello world", None)


def test_read_page_raises_on_garbage_output():
    runner = fake_runner(stdout="{not valid json")
    with pytest.raises(SafariScriptError):
        read_page(runner=runner)


def test_click_returns_true_when_found():
    runner = fake_runner(stdout="true")
    assert click("#submit", runner=runner) is True


def test_click_returns_false_when_not_found():
    runner = fake_runner(stdout="false")
    assert click(".missing", runner=runner) is False


def test_fill_returns_true_when_found():
    runner = fake_runner(stdout="true")
    assert fill("#email", "a@b.com", runner=runner) is True


def test_fill_returns_false_when_not_found():
    runner = fake_runner(stdout="false")
    assert fill(".missing", "x", runner=runner) is False


def test_element_exists_true_false():
    assert element_exists("#x", runner=fake_runner(stdout="true")) is True
    assert element_exists("#x", runner=fake_runner(stdout="false")) is False


def test_wait_for_selector_returns_true_immediately_when_present():
    runner = fake_runner(stdout="true")
    assert wait_for_selector("#x", timeout_seconds=5, runner=runner, sleep=lambda s: None) is True


def test_wait_for_selector_times_out_and_returns_false():
    runner = fake_runner(stdout="false")
    calls = {"n": 0}
    fake_time_values = iter([0.0, 0.1, 0.2, 100.0])

    def fake_sleep(_):
        calls["n"] += 1

    import safari_mcp.core as core_mod

    class FakeMonotonic:
        def __call__(self):
            return next(fake_time_values, 100.0)

    orig = __import__("time").monotonic
    __import__("time").monotonic = FakeMonotonic()
    try:
        result = wait_for_selector(
            "#x", timeout_seconds=0.2, poll_interval=0.01, runner=runner, sleep=fake_sleep
        )
    finally:
        __import__("time").monotonic = orig
    assert result is False


def test_open_url_navigates_and_reads_fresh_title(monkeypatch):
    calls = []

    def runner(cmd, **kwargs):
        script = cmd[-1]
        calls.append(script)
        if "win.currentTab.url" in script:
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"window_index": 1, "tab_index": 3}), stderr="")
        if "url: doc.url()" in script:
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout=json.dumps({"url": "https://example.com/", "title": "Example Domain", "text": "hi", "html": None}),
                stderr="",
            )
        # readiness check (readyState/URL) and the pre-navigation
        # previous_url read via read_page both go through this branch
        return subprocess.CompletedProcess(cmd, 0, stdout="true", stderr="")

    tab = open_url("https://example.com", runner=runner)
    assert tab.url == "https://example.com/"
    assert tab.title == "Example Domain"
    assert tab.window_index == 1
    assert tab.tab_index == 3


def test_open_url_skips_wait_when_disabled():
    call_scripts = []

    def runner(cmd, **kwargs):
        script = cmd[-1]
        call_scripts.append(script)
        if "win.currentTab.url" in script:
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"window_index": 1, "tab_index": 1}), stderr="")
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout=json.dumps({"url": "https://example.com/", "title": "", "text": "", "html": None}),
            stderr="",
        )

    open_url("https://example.com", wait_for_load=False, runner=runner)
    # No script should be the readyState/about:blank page-load poll.
    assert not any("readyState" in s for s in call_scripts)


def test_wait_for_page_load_waits_past_blank_placeholder():
    """Regression test for the exact race this function exists to fix:
    a brand-new tab's about:blank document already reports readyState
    'complete', so the check must require the URL to differ from the
    placeholder too, not just readyState alone."""
    responses = iter(["false", "false", "true"])  # blank, blank, loaded

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=next(responses), stderr="")

    result = wait_for_page_load(
        timeout_seconds=5, poll_interval=0.01, runner=runner, sleep=lambda s: None
    )
    assert result is True


def test_wait_for_page_load_times_out_on_persistent_blank():
    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="false", stderr="")

    import time as time_mod

    values = iter([0.0, 0.05, 0.1, 100.0])
    orig = time_mod.monotonic
    time_mod.monotonic = lambda: next(values, 100.0)
    try:
        result = wait_for_page_load(
            timeout_seconds=0.05, poll_interval=0.01, runner=runner, sleep=lambda s: None
        )
    finally:
        time_mod.monotonic = orig
    assert result is False


def test_project_metadata_uses_current_spdx_license_format():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text())["project"]

    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert not any(c.startswith("License ::") for c in project.get("classifiers", []))
    build_requires = tomllib.loads(pyproject.read_text())["build-system"]["requires"]
    assert "setuptools>=77" in build_requires


def test_close_tab_runs_without_error():
    runner = fake_runner(stdout="")
    close_tab(window_index=1, tab_index=2, runner=runner)  # must not raise
