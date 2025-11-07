import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ---------------- CONFIG ----------------
SQUADS_URL = "https://www.futbin.com/squads"
SQUAD_CACHE_FILE = "squads.json"
PLAYER_STATS_FILE = "players_24h_stats.json"
SQUAD_EXPIRY_MINUTES = 30  # squad cache threshold in minutes

# FUTBIN SELECTORS
SELECTOR_SQUAD_LINKS = "a.squad-box.text-ellipsis.xs-column"
SELECTOR_PLAYER_CARD = "div[id^='cardlid']"

# Terminal Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


# ---------------- UTILITIES ----------------
def parse_numeric_price(s: str):
    """Convert FUTBIN-style coin strings like '15K' or '1.2M' to integers."""
    if not s or s.strip() in ("", "--", "0"):
        return None
    s = s.strip().upper().replace(",", "").replace("COINS", "").replace("COIN", "")
    if s.endswith("K"):
        return int(float(s[:-1]) * 1000)
    if s.endswith("M"):
        return int(float(s[:-1]) * 1_000_000)
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def format_mk(value):
    """Format numbers like 150000 -> '150K' or 2000000 -> '2M'."""
    if not value:
        return None
    if value >= 1_000_000:
        return f"{round(value / 1_000_000)}M"
    elif value >= 1000:
        return f"{round(value / 1000)}K"
    return str(value)


def parse_futbin_datetime(date_str: str):
    """Parse FUTBIN-style dates like 'Oct 25, 2:30 PM'."""
    try:
        dt = datetime.strptime(date_str.strip(), "%b %d, %I:%M %p")
        dt = dt.replace(year=datetime.now().year)
        return dt
    except Exception:
        return None


def load_json(file):
    """Load a JSON file safely, returning {} if missing or invalid."""
    if not os.path.exists(file):
        return {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️ Warning: Corrupt JSON file detected ({file}). Resetting...")
        return {}


def save_json(file, data):
    """Save JSON with pretty formatting."""
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def squad_is_fresh(squad_info):
    """Check if the squad cache is recent."""
    last_checked = squad_info.get("last_checked")
    if not last_checked:
        return False
    try:
        last_time = datetime.fromisoformat(last_checked)
    except ValueError:
        return False
    return (datetime.now() - last_time).total_seconds() < SQUAD_EXPIRY_MINUTES * 60


# ---------------- SCRAPING FUNCTIONS ----------------
async def scrape_squad_players(context, squad_url):
    """Scrape all player URLs from a squad page."""
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
    """Scrape player price history and compute stats."""
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
        if sold_prices
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


# ---------------- MAIN ----------------
async def main():
    start_time = time.time()
    cutoff_time = datetime.now() - timedelta(hours=24)

    # Detect launch param
    scan_all_mode = len(sys.argv) > 1 and sys.argv[1].strip().lower() == "scan_all"
    if scan_all_mode:
        print("⚡ scan_all mode activated — scraping all squads...")

    # Load caches
    squads_cache = load_json(SQUAD_CACHE_FILE)
    player_stats_cache = load_json(PLAYER_STATS_FILE)

    # Fetch squads if missing
    if not squads_cache:
        print("🔍 No cached squads found — fetching from Futbin...")
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(SQUADS_URL, timeout=60000)
            await page.wait_for_selector(SELECTOR_SQUAD_LINKS)
            squad_elements = await page.query_selector_all(SELECTOR_SQUAD_LINKS)

            squads_cache = {}
            for a in squad_elements:
                href = await a.get_attribute("href")
                if href and "/26/totw" in href:
                    div = await a.query_selector("div.squads-header.bold")
                    if div:
                        name = (await div.inner_text()).strip()
                        squads_cache[name] = {
                            "url": "https://www.futbin.com" + href,
                            "last_checked": None,
                            "players": [],
                        }

            await page.close()
            await browser.close()
            save_json(SQUAD_CACHE_FILE, squads_cache)
            print(f"✅ Found {len(squads_cache)} squads.")

    # --- SCAN ALL MODE ---
    if scan_all_mode:
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            context = await browser.new_context()

            for squad_name, squad_info in squads_cache.items():
                print(f"\n🔍 Processing squad: {squad_name}")
                if squad_is_fresh(squad_info) and squad_name in player_stats_cache:
                    print(f"📂 Cached data for {squad_name} is still fresh. Skipping...")
                    continue

                player_urls = await scrape_squad_players(context, squad_info["url"])
                tasks = [fetch_player_stats(context, pinfo, cutoff_time) for pinfo in player_urls]
                squad_players = [r for r in await asyncio.gather(*tasks) if r]

                player_stats_cache[squad_name] = squad_players
                squad_info["last_checked"] = datetime.now().isoformat()
                save_json(PLAYER_STATS_FILE, player_stats_cache)
                save_json(SQUAD_CACHE_FILE, squads_cache)
                print(f"✅ Squad {squad_name} updated successfully.")

            await browser.close()
        print("\n⚡ scan_all mode complete.")
        return

    # --- INTERACTIVE MODE ---
    available_squads = list(squads_cache.keys())
    print("\nAvailable TOTW squads:")
    for i, name in enumerate(available_squads, 1):
        print(f"{i}. {name}")

    choice = int(input("Enter the number of the squad to check: "))
    selected_squad = available_squads[choice - 1]
    squad_info = squads_cache[selected_squad]

    squad_fresh = squad_is_fresh(squad_info) and selected_squad in player_stats_cache
    if squad_fresh:
        print(f"📂 Using cached stats for {selected_squad}")
        squad_players = player_stats_cache[selected_squad]
    else:
        print(f"🔍 Fetching latest data for {selected_squad}...")
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            context = await browser.new_context()
            player_urls = await scrape_squad_players(context, squad_info["url"])
            tasks = [fetch_player_stats(context, pinfo, cutoff_time) for pinfo in player_urls]
            squad_players = [r for r in await asyncio.gather(*tasks) if r]
            await browser.close()

        player_stats_cache[selected_squad] = squad_players
        squad_info["last_checked"] = datetime.now().isoformat()
        save_json(PLAYER_STATS_FILE, player_stats_cache)
        save_json(SQUAD_CACHE_FILE, squads_cache)

    # --- DISPLAY TOP 5 ---
    show_top = input("Do you want to see the top 5 players by profit margin? (y/n): ").strip().lower()
    if show_top == "y":
        filtered = [p for p in squad_players if p["stats"].get("profit_margin")]
        top5 = sorted(filtered, key=lambda p: parse_numeric_price(p["stats"]["profit_margin"]), reverse=True)[:5]

        print("\n🏆 Top 5 Players by Profit Margin:")
        for idx, player in enumerate(top5, 1):
            stats = player["stats"]
            trend_pct = stats.get("trend_pct")
            trend_display = f"{GREEN}🔺 {trend_pct}%{RESET}" if trend_pct and trend_pct > 0 else (
                f"{RED}🔻 {abs(trend_pct)}%{RESET}" if trend_pct else "N/A"
            )
            profit_pct = stats.get("profit_margin_pct")
            profit_display = f"{GREEN}🔺 {profit_pct}%{RESET}" if profit_pct and profit_pct > 0 else (
                f"{RED}🔻 {abs(profit_pct)}%{RESET}" if profit_pct else "N/A"
            )

            print(f"\n{idx}. ⚽ {player['player']}")
            print(f"   📈 Trend Value       : {stats.get('trend_value','N/A')} | {trend_display}")
            print(f"   💰 Avg Buy Now       : {stats.get('average_buy_now','N/A')}")
            print(f"   🥇 Highest Price     : {stats.get('highest','N/A')}")
            print(f"   🥉 Lowest Price      : {stats.get('lowest','N/A')}\n")
            print(f"   ⬇️ Avg Below Trend   : {stats.get('avg_below_trend','N/A')}")
            print(f"   ⬆️ Avg Above Trend   : {stats.get('avg_above_trend','N/A')}")
            print(f"   💸 Profit Margin     : {stats.get('profit_margin','N/A')}")
            print(f"   📊 Profit Margin %   : {profit_display}")

    elapsed = time.time() - start_time
    minutes, seconds = divmod(elapsed, 60)
    print(f"\n⏱ Total execution time: {int(minutes)}m {seconds:.2f}s")


# ---------------- RUN ----------------
if __name__ == "__main__":
    asyncio.run(main())