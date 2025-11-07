import json
import os
from datetime import datetime, timedelta
from .constants import SQUAD_EXPIRY_MINUTES

def load_cache(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_cache(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def is_fresh(item):
    last_checked = item.get("last_checked")
    if not last_checked:
        return False
    last_time = datetime.fromisoformat(last_checked)
    return (datetime.now() - last_time).total_seconds() < SQUAD_EXPIRY_MINUTES * 60

from datetime import datetime, timedelta

def is_recent(last_checked_str, max_age_minutes=30):
    """Return True if last_checked is within the last `max_age_minutes`."""
    if not last_checked_str:
        return False  # If it's None or missing, treat as stale
    
    try:
        last_checked = datetime.fromisoformat(last_checked_str)
    except ValueError:
        return False  # Handle malformed timestamps gracefully

    return datetime.now() - last_checked <= timedelta(minutes=max_age_minutes)