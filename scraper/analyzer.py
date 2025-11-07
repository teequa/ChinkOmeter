GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def mk_to_int(s):
    if not s: return 0
    s = s.upper().replace(",","").strip()
    if s.endswith("M"): return int(float(s[:-1])*1_000_000)
    if s.endswith("K"): return int(float(s[:-1])*1000)
    try: return int(s)
    except: return 0

def print_top5(players):
    filtered = [p for p in players if p.get("stats", {}).get("profit_margin")]
    top5 = sorted(filtered, key=lambda p: mk_to_int(p["stats"]["profit_margin"]), reverse=True)[:5]

    print("\n🏆 Top 5 Players by Profit Margin:")
    for idx, player in enumerate(top5,1):
        stats = player["stats"]
        trend_pct = stats.get("trend_pct")
        trend_display = f"{GREEN}🔺 {trend_pct}%{RESET}" if trend_pct and trend_pct>0 else (f"{RED}🔻 {abs(trend_pct)}%{RESET}" if trend_pct else "N/A")
        profit_pct = stats.get("profit_margin_pct")
        profit_display = f"{GREEN}🔺 {profit_pct}%{RESET}" if profit_pct and profit_pct>0 else (f"{RED}🔻 {abs(profit_pct)}%{RESET}" if profit_pct else "N/A")

        print(f"\n{idx}. ⚽ {player['player']}")
        print(f"   📈 Trend Value       : {stats.get('trend_value','N/A')} | {trend_display}")
        print(f"   💰 Avg Buy Now       : {stats.get('average_buy_now','N/A')}")
        print(f"   🥇 Highest Price     : {stats.get('highest','N/A')}")
        print(f"   🥉 Lowest Price      : {stats.get('lowest','N/A')}\n")
        print(f"   ⬇️ Avg Below Trend   : {stats.get('avg_below_trend','N/A')}")
        print(f"   ⬆️ Avg Above Trend   : {stats.get('avg_above_trend','N/A')}")
        print(f"   💸 Profit Margin     : {stats.get('profit_margin','N/A')}")
        print(f"   📊 Profit Margin %   : {profit_display}")