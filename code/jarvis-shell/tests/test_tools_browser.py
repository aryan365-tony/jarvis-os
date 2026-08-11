"""Tests for Phase C Browser tools."""

from jarvis.tools import browser


def test_browser_check_domain():
    assert browser._check_domain("https://bank.com/login") is not None
    assert browser._check_domain("https://my.bank/account") is not None
    assert browser._check_domain("https://safe.com") is None


def test_browser_tools(monkeypatch):
    # Mock _run_browser to just execute the closure with a dummy page
    class DummyPage:
        url = "https://example.com"
        def title(self): return "Example"
        def goto(self, url, **k): self.url = url
        def evaluate(self, script): return "page text"
        def click(self, sel, **k): pass
        def fill(self, sel, txt, **k): pass
        def wait_for_load_state(self, *a, **k): pass
        def screenshot(self, **k): pass
        def inner_text(self, sel, **k): return "inner"
    
    def dummy_run_browser(func, *args):
        try:
            return str(func(DummyPage(), *args))
        except Exception as e:
            return f"error: {e}"
            
    monkeypatch.setattr(browser, "_run_browser", dummy_run_browser)
    
    assert "Navigated to" in browser.browser_navigate("https://example.com")
    assert "error" in browser.browser_navigate("https://bank.com")
    
    assert browser.browser_read_page() == "page text"
    
    assert browser.browser_click_type("#btn", "hello") == "ok"
    
    assert "error" not in browser.browser_submit_form("#submit")   
    assert "Screenshot saved" in browser.browser_screenshot("/tmp/shot.png")
    
    assert browser.browser_extract_text("#content") == "inner"
