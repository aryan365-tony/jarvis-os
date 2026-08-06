"""Browser automation (browser).

Design note
-----------
Uses Playwright to navigate and interact with web pages.
State is maintained via a dedicated background thread to satisfy Playwright's thread affinity requirements.
"""

from __future__ import annotations

import queue
import threading
from urllib.parse import urlparse

from .registry import register


_SENSITIVE_DOMAINS = {"bank.com", "paypal.com", "my.bank"}

_browser_queue: queue.Queue = queue.Queue()
_browser_thread: threading.Thread | None = None


def _browser_worker():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        while True:
            func, args, result_queue = _browser_queue.get()
            if func is None:
                break
            try:
                res = func(page, *args)
                result_queue.put(("ok", res))
            except Exception as e:
                result_queue.put(("error", str(e)))


def _run_browser(func, *args) -> str:
    global _browser_thread
    if _browser_thread is None:
        _browser_thread = threading.Thread(target=_browser_worker, daemon=True)
        _browser_thread.start()
    
    result_queue: queue.Queue = queue.Queue()
    _browser_queue.put((func, args, result_queue))
    status, result = result_queue.get()
    if status == "error":
        return f"error: {result}"
    return str(result)


def _check_domain(url: str) -> str | None:
    domain = urlparse(url).netloc.lower()
    for sensitive in _SENSITIVE_DOMAINS:
        if domain == sensitive or domain.endswith(f".{sensitive}"):
            return f"error: navigation to sensitive domain {domain} is blocked"
    return None


@register(
    "browser_navigate",
    risk="low",
    domain="browser",
    description="Navigate the browser to a URL.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
        },
        "required": ["url"],
    },
)
def browser_navigate(url: str) -> str:
    err = _check_domain(url)
    if err:
        return err
    
    def _do(page, u):
        page.goto(u, timeout=15000)
        return f"Navigated to {page.url} (Title: {page.title()})"
    return _run_browser(_do, url)


@register(
    "browser_read_page",
    risk="low",
    domain="browser",
    description="Read the text content of the current page.",
)
def browser_read_page() -> str:
    def _do(page):
        # Extract readable text
        return page.evaluate("document.body.innerText")[:8000]
    return _run_browser(_do)


@register(
    "browser_click_type",
    risk="medium",
    domain="browser",
    description="Click an element and optionally type text.",
    parameters={
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS or text selector."},
            "text": {"type": "string", "description": "Text to type after clicking."},
        },
        "required": ["selector"],
    },
)
def browser_click_type(selector: str, text: str = "") -> str:
    def _do(page, sel, txt):
        page.click(sel, timeout=5000)
        if txt:
            page.fill(sel, txt, timeout=5000)
        return "ok"
    return _run_browser(_do, selector, text)


@register(
    "browser_submit_form",
    risk="high",
    domain="browser",
    description="Submit a form on the current page (requires confirm phrase).",
    parameters={
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "Selector for the submit button."},
            "confirm_phrase": {"type": "string", "description": "Must be exactly: 'I confirm form submission'"},
        },
        "required": ["selector", "confirm_phrase"],
    },
)
def browser_submit_form(selector: str, confirm_phrase: str) -> str:
    if confirm_phrase != "I confirm form submission":
        return "error: missing or incorrect confirm_phrase"
    
    def _do(page, sel):
        err = _check_domain(page.url)
        if err:
            raise Exception(err)
        page.click(sel, timeout=5000)
        page.wait_for_load_state("networkidle", timeout=10000)
        return f"Submitted. New URL: {page.url}"
    return _run_browser(_do, selector)


@register(
    "browser_screenshot",
    risk="low",
    domain="browser",
    description="Take a screenshot of the current page and save it to a path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to save the screenshot."},
        },
        "required": ["path"],
    },
)
def browser_screenshot(path: str) -> str:
    def _do(page, p):
        page.screenshot(path=p)
        return f"Screenshot saved to {p}"
    return _run_browser(_do, path)


@register(
    "browser_extract_text",
    risk="low",
    domain="browser",
    description="Extract text from a specific element.",
    parameters={
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
        },
        "required": ["selector"],
    },
)
def browser_extract_text(selector: str) -> str:
    def _do(page, sel):
        return page.inner_text(sel, timeout=5000)[:8000]
    return _run_browser(_do, selector)
