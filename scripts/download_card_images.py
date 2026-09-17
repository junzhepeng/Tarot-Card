"""Download public-domain RWS tarot card images.

Source: metabismuth/tarot-json (MIT, RWS scans ~350x600)
https://github.com/metabismuth/tarot-json
"""
import json
import time
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/metabismuth/tarot-json/master/cards"
OUT_DIR = Path(__file__).parent.parent / "app" / "static" / "cards"
CARDS_JSON = Path(__file__).parent.parent / "app" / "data" / "cards.json"

SUIT_PREFIX = {"wands": "w", "cups": "c", "swords": "s", "pentacles": "p"}
COURT_NUM = {"page": 11, "knight": 12, "queen": 13, "king": 14}


def source_filename(card: dict) -> str:
    if card["arcana"] == "major":
        return f"m{card['number']:02d}.jpg"
    prefix = SUIT_PREFIX[card["suit"]]
    num = COURT_NUM.get(card["rank"], card["number"])
    return f"{prefix}{num:02d}.jpg"


def download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Tarot-Card-App/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return dest.stat().st_size > 1000
    except Exception as exc:
        print(f"  FAIL {dest.name}: {exc}")
        if dest.exists():
            dest.unlink()
        return False


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CARDS_JSON, encoding="utf-8") as f:
        cards = json.load(f)

    ok, fail = 0, 0
    for card in cards:
        dest = OUT_DIR / f"{card['id']}.jpg"
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"  skip {dest.name}")
            ok += 1
            continue
        src = source_filename(card)
        url = f"{BASE_URL}/{src}"
        print(f"  get  {card['id']} <- {src}")
        if download(url, dest):
            ok += 1
        else:
            fail += 1
        time.sleep(0.1)

    print(f"\nDone: {ok} ok, {fail} failed -> {OUT_DIR}")


if __name__ == "__main__":
    main()
