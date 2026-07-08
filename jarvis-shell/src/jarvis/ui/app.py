from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
import asyncio

class JarvisApp(App):
    CSS_PATH = "jarvis.tcss"

    def compose(self) -> ComposeResult:
        yield Static("JARVIS", id="header")
        yield Footer()

async def confirm_async(name: str, args: dict) -> bool:
    # Minimal stub
    return False

if __name__ == "__main__":
    app = JarvisApp()
    app.run()
