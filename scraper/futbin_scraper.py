# scraper/futbin_scraper.py
import asyncio
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from .utils import parse_numeric_price, parse_futbin_datetime, format_mk
from.cache_manager import save_cache, load_cache
from .constants import PLAYER_STATS_FILE, SQUAD_CACHE_FILE, SQUAD_EXPIRY_MINUTES, SQUADS_URL

SELECTOR_SQUAD_LINKS = "a.squad-box.text-ellipsis.xs-column"
SELECTOR_PLAYER_CARD = "div[id^='cardlid']"

async def fetch_squads(context, squads_url):
    page = await context.new_page()
    await page.goto(squads_url, timeout=60000)
    await page.wait_for_selector(SELECTOR_SQUAD_LINKS)
    squad_elements = await page.query_selector_all(SELECTOR_SQUAD_LINKS)
    squads = {}
    for a in squad_elements:
        href = await a.get_attribute("href")
        if href and "/26/totw" in href:
            div = await a.query_selector("div.squads-header.bold")
            if div:
                name = (await div.inner_text()).strip()
                squads[name] = {"url": "https://www.futbin.com" + href, "last_checked": None, "players": []}
    await page.close()
    return squads

async def scrape_squad_players(context, squad_url):
    """Scrape all player URLs from a squad page (returns list of {Player, URL})."""
    page = await context.new_page()
    await page.goto(squad_url)
    await page.wait_for_selector(SELECTOR_PLAYER_CARD)
    player_urls = []
    for i in range(1, 12):
        card = await page.query_selector(f"div#cardlid{i} a")
        if not card:
            continue
        href = await card.get_attribute("href")
        name_div = await card.query_selector("div.playercard-26.playercard-m.pointer-events-none")
        name = await name_div.get_attribute("title") if name_div else f"Player {i}"
        player_urls.append({"Player": name, "URL": "https://www.futbin.com" + href})
    await page.close()
    return player_urls

async def fetch_player_stats(context, player_info, cutoff_time):
    """Scrape the player's sales page for the last 24h and compute stats."""
    player_name = player_info["Player"]
    player_url = player_info["URL"].replace("/player/", "/sales/") + "?platform=pc"

    page = await context.new_page()
    try:
        await page.goto(player_url, timeout=60000)
        await page.wait_for_selector("table", timeout=30000)
        html = await page.content()
    except Exception:
        await page.close()
        return None
    await page.close()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return None

    headers = [th.get_text(strip=True).lower() for th in table.select("thead th")]
    date_idx = headers.index("date") if "date" in headers else None
    sold_idx = headers.index("sold for") if "sold for" in headers else None

    sold_prices = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        date_value = None
        if date_idx is not None and date_idx < len(tds):
            span = tds[date_idx].find("span")
            if span:
                date_value = parse_futbin_datetime(span.get_text(strip=True))
        if not date_value or date_value < cutoff_time:
            continue

        if sold_idx is not None and sold_idx < len(tds):
            sold_value = parse_numeric_price(tds[sold_idx].get_text(strip=True))
            if sold_value:
                sold_prices.append(sold_value)

    if not sold_prices:
        return None

    # Compute stats
    trend_value = sum(sold_prices) // len(sold_prices)
    highest_price = max(sold_prices)
    lowest_price = min(sold_prices)
    below_prices = [p for p in sold_prices if p < trend_value]
    above_prices = [p for p in sold_prices if p > trend_value]
    avg_below = sum(below_prices) // len(below_prices) if below_prices else None
    avg_above = sum(above_prices) // len(above_prices) if above_prices else None
    profit_margin = int(avg_above - avg_below * 1.05) if avg_above and avg_below else None
    profit_margin_pct = (
        round(((avg_above - avg_below * 1.05) / (avg_below * 1.05) * 100), 2)
        if avg_above and avg_below
        else None
    )
    trend_pct = (
        round(((sold_prices[-1] - sold_prices[0]) / sold_prices[0]) * 100, 2)
        if sold_prices and sold_prices[0] != 0
        else None
    )

    return {
        "player": player_name,
        "stats": {
            "trend_value": format_mk(trend_value),
            "average_buy_now": format_mk(avg_above),
            "highest": format_mk(highest_price),
            "lowest": format_mk(lowest_price),
            "avg_below_trend": format_mk(avg_below),
            "avg_above_trend": format_mk(avg_above),
            "profit_margin": format_mk(profit_margin),
            "profit_margin_pct": profit_margin_pct,
            "trend_pct": trend_pct,
        },
    }

    async def fetch_squads(context, squads_url):
        page = await context.new_page()
        await page.goto(squads_url, timeout=60000)
        await page.wait_for_selector(SELECTOR_SQUAD_LINKS)
        squad_elements = await page.query_selector_all(SELECTOR_SQUAD_LINKS)
        squads = {}
        for a in squad_elements:
            href = await a.get_attribute("href")
            if href and "/26/totw" in href:
                div = await a.query_selector("div.squads-header.bold")
                if div:
                    name = (await div.inner_text()).strip()
                    squads[name] = {"url": "https://www.futbin.com" + href, "last_checked": None, "players": []}
        await page.close()
        return squads

async def scrape_squad_players(context, squad_url):
    page = await context.new_page()
    await page.goto(squad_url)
    await page.wait_for_selector(SELECTOR_PLAYER_CARD)
    player_urls = []
    for i in range(1, 12):
        card = await page.query_selector(f"div#cardlid{i} a")
        if not card:
            continue
        href = await card.get_attribute("href")
        name_div = await card.query_selector("div.playercard-26.playercard-m.pointer-events-none")
        name = await name_div.get_attribute("title") if name_div else f"Player {i}"
        player_urls.append({"Player": name, "URL": "https://www.futbin.com" + href})
    await page.close()
    return player_urls

async def fetch_player_stats_test(context, player_info, squad_name, squads_cache, player_stats_cache):
    """Fetch player stats AND update caches automatically."""
    cutoff_time = datetime.now() - timedelta(hours=24)
    player_name = player_info["Player"]
    player_url = player_info["URL"].replace("/player/", "/sales/") + "?platform=pc"

    page = await context.new_page()
    try:
        await page.goto(player_url, timeout=60000)
        await page.wait_for_selector("table", timeout=30000)
        html = await page.content()
    except:
        await page.close()
        return None
    await page.close()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return None

    headers = [th.get_text(strip=True).lower() for th in table.select("thead th")]
    date_idx = headers.index("date") if "date" in headers else None
    sold_idx = headers.index("sold for") if "sold for" in headers else None

    sold_prices = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if not tds: continue

        date_value = None
        if date_idx is not None and date_idx < len(tds):
            span = tds[date_idx].find("span")
            if span:
                date_value = parse_futbin_datetime(span.get_text(strip=True))
        if not date_value or date_value < cutoff_time:
            continue

        if sold_idx is not None and sold_idx < len(tds):
            sold_value = parse_numeric_price(tds[sold_idx].get_text(strip=True))
            if sold_value:
                sold_prices.append(sold_value)

    if not sold_prices:
        return None

    # Compute stats
    trend_value = sum(sold_prices) // len(sold_prices)
    highest_price = max(sold_prices)
    lowest_price = min(sold_prices)
    below_prices = [p for p in sold_prices if p < trend_value]
    above_prices = [p for p in sold_prices if p > trend_value]
    avg_below = sum(below_prices) // len(below_prices) if below_prices else None
    avg_above = sum(above_prices) // len(above_prices) if above_prices else None
    profit_margin = int(avg_above - avg_below * 1.05) if avg_above and avg_below else None
    profit_margin_pct = round(((avg_above - avg_below * 1.05) / (avg_below * 1.05) * 100), 2) if avg_above and avg_below else None
    trend_pct = round(((sold_prices[-1] - sold_prices[0]) / sold_prices[0]) * 100, 2) if sold_prices and sold_prices[0] != 0 else None

    player_data = {
        "player": player_name,
        "stats": {
            "trend_value": format_mk(trend_value),
            "average_buy_now": format_mk(avg_above),
            "highest": format_mk(highest_price),
            "lowest": format_mk(lowest_price),
            "avg_below_trend": format_mk(avg_below),
            "avg_above_trend": format_mk(avg_above),
            "profit_margin": format_mk(profit_margin),
            "profit_margin_pct": profit_margin_pct,
            "trend_pct": trend_pct,
        }
    }

    # ---------------- UPDATE CACHES ----------------
    player_stats_cache[squad_name] = player_stats_cache.get(squad_name, [])
    # Remove previous entry if exists
    player_stats_cache[squad_name] = [p for p in player_stats_cache[squad_name] if p['player'] != player_name]
    player_stats_cache[squad_name].append(player_data)

    # Update squad last_checked
    if squad_name in squads_cache:
        squads_cache[squad_name]['last_checked'] = datetime.now().isoformat()

    save_cache(PLAYER_STATS_FILE, player_stats_cache)
    save_cache(SQUAD_CACHE_FILE, squads_cache)

    return player_data