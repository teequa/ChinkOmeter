import json
import os
import re

# ---------- CONFIG ----------
PLAYER_STATS_FILE = "players_24h_stats.json"
SQUAD_CACHE_FILE = "squads.json"
# ----------------------------

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

# ---------- UTILITIES ----------
def load_json(file):
    if not os.path.exists(file):
        return {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def mk_to_int(s):
    """Convert formatted K/M values to integers"""
    if not s: return 0
    s = s.upper().replace(",", "").strip()
    if s.endswith("M"): return int(float(s[:-1]) * 1_000_000)
    if s.endswith("K"): return int(float(s[:-1]) * 1_000)
    try:
        return int(s)
    except:
        return 0

def format_mk(value):
    """Format integer values into K or M"""
    if not value:
        return "N/A"
    if value >= 1_000_000:
        return f"{round(value / 1_000_000, 1)}M"
    elif value >= 1000:
        return f"{round(value / 1000)}K"
    return str(value)

# ---------- MAIN ----------
def main():
    # Load caches
    player_stats_cache = load_json(PLAYER_STATS_FILE)
    squads_cache = load_json(SQUAD_CACHE_FILE)

    if not squads_cache or not player_stats_cache:
        print("⚠️ No cached data found. Please run the main scraper first.")
        return

    available_squads = list(squads_cache.keys())
    print("\nAvailable TOTW squads:")
    for i, name in enumerate(available_squads, 1):
        print(f"{i}. {name}")

    try:
        choice = int(input("Enter the number of the squad to analyze: "))
        selected_squad = available_squads[choice - 1]
    except (ValueError, IndexError):
        print("❌ Invalid choice.")
        choice = int(input("Enter the number of the squad to analyze: "))
        selected_squad = available_squads[choice - 1]
        
    if selected_squad not in player_stats_cache:
        print(f"⚠️ No cached stats found for {selected_squad}. Run the main scraper first.")
        return

    players = player_stats_cache[selected_squad]
    low_trend_players = []
    for p in players:
        stats = p.get("stats", {})
        trend_value = mk_to_int(stats.get("trend_value"))
        if trend_value and trend_value < 100_000:
            low_trend_players.append(p)

    if not low_trend_players:
        print(f"❌ No players under 100K trend value found for squad {selected_squad}.")
        return

    # Sort by profit margin
    filtered = [p for p in low_trend_players if p["stats"].get("profit_margin")]
    top5 = sorted(filtered, key=lambda p: mk_to_int(p["stats"]["profit_margin"]), reverse=True)[:5]

    print(f"\n🏆 Top 5 Low-Trend Players by Profit Margin ({selected_squad}, Trend < 100K):")
    for idx, player in enumerate(top5, 1):
        stats = player["stats"]
        trend_pct = stats.get("trend_pct")
        trend_display = (
            f"{GREEN}🔺 {trend_pct}%{RESET}" if trend_pct and trend_pct > 0
            else (f"{RED}🔻 {abs(trend_pct)}%{RESET}" if trend_pct else "N/A")
        )
        profit_pct = stats.get("profit_margin_pct")
        profit_display = (
            f"{GREEN}🔺 {profit_pct}%{RESET}" if profit_pct and profit_pct > 0
            else (f"{RED}🔻 {abs(profit_pct)}%{RESET}" if profit_pct else "N/A")
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

    print(f"\n✅ Found {len(low_trend_players)} players under 100K trend value in {selected_squad}.")
    print("📊 Displayed top 5 by profit margin.")

# ---------- RUN ----------
if __name__ == "__main__":
    main()