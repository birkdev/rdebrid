import json
import sys
from pathlib import Path

import requests

CONFIG_DIR = Path.home() / ".config" / "rdebrid"
CONFIG_FILE = CONFIG_DIR / "config.json"
API_BASE = "https://api.real-debrid.com/rest/1.0"


def _load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_token():
    config = _load_config()
    return config.get("api_token", "")


def save_token(token):
    config = _load_config()
    config["api_token"] = token
    _save_config(config)


def validate_token(token):
    """Check if a token is valid by calling the /user endpoint."""
    try:
        resp = requests.get(
            f"{API_BASE}/user",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException:
        return None


def setup_interactive():
    """Prompt the user for their API token and save it."""
    print("Real-Debrid Setup")
    print("=" * 40)
    print()
    print("Get your API token from: https://real-debrid.com/apitoken")
    print()

    token = input("Enter your API token: ").strip()
    if not token:
        print("No token entered. Aborting.")
        sys.exit(1)

    print("Validating token...")
    user = validate_token(token)

    if user:
        save_token(token)
        username = user.get("username", "Unknown")
        premium = user.get("type", "free")
        print(f"  Logged in as: {username} ({premium})")
        print(f"  Token saved to: {CONFIG_FILE}")
        print()
        print("Setup complete!")
    else:
        print("  Invalid token. Please check and try again.")
        sys.exit(1)
