import asyncio
import sys
import time
from datetime import datetime, timedelta
from scraper.cache_manager import load_cache, save_cache, is_recent
from scraper.constants import SQUAD_CACHE_FILE, SQUAD_EXPIRY_MINUTES, SQUADS_URL, PLAYER_STATS_FILE
from scraper.analyzer import print_top5
from scraper.futbin_scraper import fetch_player_stats, fetch_squads, scrape_squad_players, fetch_player_stats_test
from scraper.utils import format_mk, parse_numeric_price, format_top5_by_profit

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static, Header, Footer, DataTable, Input, ListView, ListItem
from textual.containers import Horizontal, Vertical

# -------------------------
# Define Screens / Pages
# -------------------------

class HomeScreen(Screen):
    """Home page with navigation buttons."""
    def compose(self) -> ComposeResult:
        yield Static("Welcome to chinkerinens Futbin Trade-cheese \n Select script:", id="title")
        with Horizontal():
            yield Button("Promo players", id="promo")
            yield Button("Scan all (slow)", id="scan_all")
            yield Button("Squad", id="squad")
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "promo":
            self.app.push_screen("promo")
        elif event.button.id == "scan_all":
            self.app.push_screen("scan_all")
        elif event.button.id == "squad":
            self.app.push_screen(Squad("hello World"))


class PromoScreen(Screen):
    """Data page with back button."""
    def compose(self) -> ComposeResult:
        self.table = DataTable()
        self.table.add_columns("ID", "Squad Name")

        yield Header(show_clock=True)
        yield Static("📊 Current Promo Squads \n Select one to show price data", id="title")
        self.userIn = Input(placeholder="Please select squad ID (1, 2, 3 ...)")
        self.status = Static("loading squads ...")
        yield Vertical(self.userIn,
                       self.table,
                       Button("Back to home", id="home")
                       )
        yield Footer()

    async def on_mount(self) -> None:
        asyncio.create_task(self.load_data())
    async def load_data(self) -> None:
        # 1️⃣ Try load from cache (sync)
        Squads = load_cache("data/squads.json")

        if not Squads:
            self.table.add_row("1", "📂 No cached squad files, loading squads from Futbin")
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)
                context = await browser.new_context()

                Squads = await fetch_squads(context, SQUADS_URL)
                save_cache(SQUAD_CACHE_FILE, Squads)

                await context.close()
                await browser.close()

        self.table.clear()
        for e, i in enumerate(Squads, start=1):
            self.table.add_row(str(e), i, key=str(e))


    def on_input_submitted(self, event: Input.Submitted) -> None:
        rows = self.table.row_count

        try:
            userInput = int(event.value)

            if userInput <= rows:
                rowKey = self.table.get_row(event.value.strip())
                screen_inst = Squad(rowKey[1])
                screen_name = "Squad"
                self.app.install_screen(screen_inst, name=screen_name)
                self.app.push_screen(screen_name)
            else:
                self.userIn.placeholder = f"invalid ID {event.value} - try again"
                self.userIn.value =""
        
        except ValueError:
            self.userIn.placeholder = f"invalid ID {event.value} - try again"
            self.userIn.value = ""


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "home":
            self.app.pop_screen()

class Scan_allScreen(Screen):
    """Settings page with back button."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("⚙️ Settings Page\n\n(Change preferences here)", id="title", classes="button")
        yield Button("⬅ Back to Home", id="home", classes="button")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "home":
            self.app.pop_screen()

class Squad(Screen):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.Player_list = None
        self.playerTable = ListView()

    def compose(self) -> ComposeResult:
        Player = Static(self.data)
        self.status = Static("")
        yield Header(show_clock=False)
        yield Vertical (
            Static(f"Top 5 most profitable players for {self.data}", id="title"),
                self.status,
            Horizontal(
                Button ("show players under 100k", id="affordable")
            ),
            self.playerTable
        )
    async def on_mount(self):
        asyncio.create_task(self.load_data())

    async def load_data(self):
        Squads = load_cache(SQUAD_CACHE_FILE)
        players = load_cache(PLAYER_STATS_FILE)
        selSquad = players[self.data]
        chacheAge = Squads[self.data]["last_checked"]


        if is_recent(chacheAge) is False and self.data in players:

            self.status.update("Loading players from futbin...")
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)
                context = await browser.new_context()

                playerUrl = None

                if Squads[self.data]["url"] is None: 
                    playerUrl = await scrape_squad_players(context,Squads[self.data]["url"])
                    Squads[self.data]["players"] = playerUrl
                    save_cache(SQUAD_CACHE_FILE, Squads)
                else: 
                    playerUrl = Squads[self.data]["players"]
                    
                self.status.update("fetching current prices for each player...")
                fetchedStats = [fetch_player_stats_test(context, p, self.data, Squads, players) for p in playerUrl]
                selSquad = [p for p in await asyncio.gather(*fetchedStats) if p]

        filtered = [p for p in selSquad if p.get("stats", {},).get("profit_margin")]
        
        playersSorted = sorted(
            filtered,
            key=lambda p: parse_numeric_price(p["stats"]["profit_margin"]),
            reverse=True
        )[:5]

        for idx, player in enumerate(playersSorted, 1):
            stats = player["stats"]
            trend_pct = stats.get("trend_pct")
            profit_pct = stats.get("profit_margin_pct")
            trend_display = (
                f"[green]🔺 {trend_pct}% [/green]"
                if trend_pct and trend_pct > 0
                else f"[red]🔻 {abs(trend_pct)}% [/red]"
                if trend_pct
                else "N/A"
            )
            profit_display = (
                f"[green]🔺 {profit_pct}% [/green]"
                if profit_pct and profit_pct > 0
                else f"[red]🔻 {abs(profit_pct)}% [/red]"
                if profit_pct
                else "N/A"
            )

            text = (
                f"\n{idx}. ⚽ {player['player']}\n"
                f"   📈 Trend Value       : {stats.get('trend_value', 'N/A')} | {trend_display}\n"
                f"   💰 Avg Buy Now       : {stats.get('average_buy_now', 'N/A')}\n"
                f"   🥇 Highest Price     : {stats.get('highest', 'N/A')}\n"
                f"   🥉 Lowest Price      : {stats.get('lowest', 'N/A')}\n"
                f"   ⬇️ Avg Below Trend   : {stats.get('avg_below_trend', 'N/A')}\n"
                f"   ⬆️ Avg Above Trend   : {stats.get('avg_above_trend', 'N/A')}\n"
                f"   💸 Profit Margin     : {stats.get('profit_margin', 'N/A')}\n"
                f"   📊 Profit Margin %   : {profit_display}\n"
            )
            self.playerTable.append(Static(text))
            self.status.update("")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "affordable":
            """under 100k price lookup"""
            self.status.update("affordable")
            playerStats = load_cache(PLAYER_STATS_FILE)

            affordablePlayers = [
                p for p in playerStats[self.data]
                if  parse_numeric_price(p["stats"]["trend_value"]) < 100_000
            ]

            top5 = format_top5_by_profit(playerStats[self.data], True)
            self.status.update("affordable")
            self.playerTable.remove_children()

            for p in format_top5_by_profit(playerStats[self.data], True):
                self.playerTable.append(Static(p))


# -------------------------
# Main App
# -------------------------

class MultiScreenApp(App):
    """App with three screens and Ctrl+C quit."""

    # Bind Ctrl+C to quit
    BINDINGS = [("c", "quit", "Quit the app")]

    CSS = """
    #title {
        padding: 1;
        text-align: center;
    }
    Horizontal {
        align-horizontal: center;
        align-vertical: middle;
        height: auto;
        padding: 1;
    }
    Button {
        margin: 0 1;
        text-align:center;
    }
    """

    def on_mount(self) -> None:
        # Register all screens
        self.install_screen(HomeScreen(), name="home")
        self.install_screen(PromoScreen, name="promo")
        self.install_screen(Scan_allScreen(), name="scan_all")
        
        # Start at the Home screen
        self.push_screen("home")

    def action_quit(self) -> None:
        """Quit the app cleanly."""
        self.exit()


# -------------------------
# Run the App
# -------------------------

if __name__ == "__main__":
    from playwright.async_api import async_playwright
    MultiScreenApp().run()