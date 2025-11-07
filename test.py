import asyncio
import sys
import time
from datetime import datetime, timedelta
from scraper.cache_manager import load_cache, save_cache, is_fresh, is_recent
from scraper.constants import SQUAD_CACHE_FILE, SQUAD_EXPIRY_MINUTES, SQUADS_URL, PLAYER_STATS_FILE
from scraper.analyzer import print_top5
from scraper.futbin_scraper import fetch_player_stats, fetch_squads, scrape_squad_players, fetch_player_stats_test
from scraper.utils import format_mk, parse_numeric_price

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static, Header, Footer, DataTable, Input, ListView, ListItem
from textual.containers import Horizontal, Vertical
from playwright.async_api import async_playwright

async def test ():
        data = "Ultimate Scream"
        Squads = load_cache(SQUAD_CACHE_FILE)
        players = load_cache(PLAYER_STATS_FILE)
        selSquad = players[data]
        CacheAge = Squads[data]["last_checked"]

        if is_recent(CacheAge) is False and data in players:
            
            print("Loading prices from futbin...")
        
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)
                context = await browser.new_context()

                playerUrl = await scrape_squad_players(context,Squads[data]["url"])
                print(playerUrl)
                Squads[data]["players"] = playerUrl
                save_cache(SQUAD_CACHE_FILE, Squads)
                fetchedStats = [fetch_player_stats_test(context, p, data, Squads, players) for p in playerUrl]
                selSquad = [p for p in await asyncio.gather(*fetchedStats) if p]

        filtered = [p for p in selSquad if p.get("stats", {},).get("profit_margin")]
        playersSorted = sorted(
            filtered,
            key=lambda p: parse_numeric_price(p["stats"]["profit_margin"]),
            reverse=True
        )[:5]

        print(playersSorted)

asyncio.run(test())