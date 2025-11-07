# app.py
import asyncio
import sys
import time
from datetime import datetime, timedelta
from scraper.cache_manager import load_cache, save_cache, is_fresh
from scraper.futbin_scraper import fetch_squads, scrape_squad_players, fetch_player_stats
from scraper.analyzer import print_top5
from scraper.constants import SQUADS_URL, SQUAD_CACHE_FILE, PLAYER_STATS_FILE

async def main():
    start_time = time.time()
    cutoff_time = datetime.now() - timedelta(hours=24)

    scan_all = len(sys.argv) > 1 and sys.argv[1].strip().lower() == "scan_all"
    if scan_all:
        print("⚡ Running in scan_all mode (will attempt to update all squads).")

    squads_cache = load_cache(SQUAD_CACHE_FILE)
    players_cache = load_cache(PLAYER_STATS_FILE)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()

        # If no squads cached or scan_all requested -> fetch squads
        if not squads_cache:
            print("🔍 No cached squads found — fetching from Futbin...")
            squads_cache = await fetch_squads(context, SQUADS_URL)
            save_cache(SQUAD_CACHE_FILE, squads_cache)
            print(f"✅ Found {len(squads_cache)} squads.")

        # scan_all mode: update all squads (respecting cache freshness)
        if scan_all:
            for squad_name, squad_info in squads_cache.items():
                print(f"\n🔁 Updating squad: {squad_name}")
                if is_fresh(squad_info) and squad_name in players_cache:
                    print(f"📂 Cached and fresh — skipping {squad_name}")
                    continue

                player_urls = await scrape_squad_players(context, squad_info["url"])
                tasks = [fetch_player_stats(context, pinfo, cutoff_time) for pinfo in player_urls]
                squad_players = [r for r in await asyncio.gather(*tasks) if r]

                players_cache[squad_name] = squad_players
                squad_info["last_checked"] = datetime.now().isoformat()
                save_cache(PLAYER_STATS_FILE, players_cache)
                save_cache(SQUAD_CACHE_FILE, squads_cache)
                print(f"✅ Squad {squad_name} updated.")
            await browser.close()
            print("\n⚡ scan_all finished.")
            elapsed = time.time() - start_time
            print(f"\n⏱ Total execution time: {int(elapsed//60)}m {elapsed%60:.2f}s")
            return

        # Interactive mode
        available = list(squads_cache.keys())
        print("\nAvailable TOTW squads:")
        for i, n in enumerate(available, 1):
            print(f"{i}. {n}")
        try:
            choice = int(input("Enter the number of the squad to check: "))
            selected = available[choice - 1]
        except Exception:
            print("Invalid selection. Exiting.")
            await browser.close()
            return

        squad_info = squads_cache[selected]
        if is_fresh(squad_info) and selected in players_cache:
            print(f"📂 Using cached stats for {selected}")
            squad_players = players_cache[selected]
        else:
            print(f"🔍 Scraping latest 24h prices for squad {selected}...")
            player_urls = await scrape_squad_players(context, squad_info["url"])
            tasks = [fetch_player_stats(context, pinfo, cutoff_time) for pinfo in player_urls]
            squad_players = [r for r in await asyncio.gather(*tasks) if r]
            [selected] = squad_players
            squad_info["last_checked"] = datetime.now().isoformat()
            save_cache(PLAYER_STATS_FILE, players_cache)
            save_cache(SQUAD_CACHE_FILE, squads_cache)

        await browser.close()

    # Show top 5
    show_top = input("Do you want to see the top 5 players by profit margin? (y/n): ").strip().lower()
    if show_top == "y":
        print_top5(squad_players)

    elapsed = time.time() - start_time
    print(f"\n⏱ Total execution time: {int(elapsed//60)}m {elapsed%60:.2f}s")

if __name__ == "__main__":
    # import here to avoid top-level playwright import in module (keeps package import clean)
    from playwright.async_api import async_playwright
    asyncio.run(main())