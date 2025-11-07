import re
from datetime import datetime

def parse_numeric_price(s: str):
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
    if not value:
        return None
    if value >= 1_000_000:
        return f"{round(value/1_000_000)}M"
    elif value >= 1000:
        return f"{round(value/1000)}K"
    return str(value)

def parse_futbin_datetime(date_str: str):
    try:
        dt = datetime.strptime(date_str.strip(), "%b %d, %I:%M %p")
        dt = dt.replace(year=datetime.now().year)
        return dt
    except:
        return None
    

def format_top5_by_profit(players, value):
    text = []
    filtered = ""
    filtered = [ p for p in players if p.get("stats", {},).get("profit_margin")]

    if value is None:

        sorted_players = sorted(
            filtered,
            key=lambda p: parse_numeric_price(p["stats"]["profit_margin"]),
            reverse=True
        )[:5]
    else:

        filtered = [
            p for p in players if p.get("stats", {},).get("profit_margin")
            if parse_numeric_price(p["stats"]["trend_value"]) < 100_000
            ]
        
        sorted_players = sorted(
            filtered,
            key=lambda p: parse_numeric_price(p["stats"]["profit_margin"]),
            reverse=True

        )[:5]
        
    # Pretty print output
    for idx, player in enumerate(sorted_players, 1):
        stats = player["stats"]
        trend_pct = stats.get("trend_pct")
        profit_pct = stats.get("profit_margin_pct")

        trend_display = (
            f"[green]🔺 {trend_pct}%[/green]" if trend_pct and trend_pct > 0
            else f"[red]🔻 {abs(trend_pct)}%[/red]" if trend_pct
            else "N/A"
        )

        profit_display = (
            f"[green]🔺 {profit_pct}%[/green]" if profit_pct and profit_pct > 0
            else f"[red]🔻 {abs(profit_pct)}%[/red]" if profit_pct
            else "N/A"
        )

        text.append(
            f"\n{idx}. ⚽ {player.get('player', 'Unknown')}\n"
            f"   📈 Trend Value       : {stats.get('trend_value', 'N/A')} | {trend_display}\n"
            f"   💰 Avg Buy Now       : {stats.get('average_buy_now', 'N/A')}\n"
            f"   🥇 Highest Price     : {stats.get('highest', 'N/A')}\n"
            f"   🥉 Lowest Price      : {stats.get('lowest', 'N/A')}\n"
            f"   ⬇️ Avg Below Trend   : {stats.get('avg_below_trend', 'N/A')}\n"
            f"   ⬆️ Avg Above Trend   : {stats.get('avg_above_trend', 'N/A')}\n"
            f"   💸 Profit Margin     : {stats.get('profit_margin', 'N/A')}\n"
            f"   📊 Profit Margin %   : {profit_display}\n"
        )

    return text