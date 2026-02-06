#!/usr/bin/env python3
"""Scryfall API wrapper for MTG card data lookup.

Usage:
    scryfall.py search "<name>"     Fuzzy name search
    scryfall.py exact "<name>"      Exact name lookup
    scryfall.py batch "<file>"      Bulk lookup from file (one card name per line)
    scryfall.py query "<query>"     Advanced search using Scryfall syntax

Query examples:
    scryfall.py query "t:creature o:draw cmc<=3"
    scryfall.py query "t:instant id:dimir o:counter"
    scryfall.py query "t:land id:gruul"

Common Scryfall search syntax:
    o:text       oracle text contains "text"
    t:type       type line contains "type"
    c:color      card color (w/u/b/r/g)
    id:color     color identity
    cmc:N        mana value equals N (also cmc>=N, cmc<=N)
    is:commander legal as commander
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.scryfall.com"
DELAY_SEC = 0.1  # 100ms between requests per Scryfall policy
HEADERS = {
    "User-Agent": "MTGDeckBuilder/1.0",
    "Accept": "application/json",
}


def _request(path, params=None):
    """Make a GET request to the Scryfall API."""
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        detail = body.get("details", e.reason)
        print(f"Error: {detail}", file=sys.stderr)
        sys.exit(1)


def _format_card(card):
    """Format a card's functional data as readable text."""
    # Handle double-faced / modal cards
    faces = card.get("card_faces")
    if faces and "oracle_text" not in card:
        # Multi-face card: print each face
        lines = [f"Name: {card['name']}"]
        lines.append(f"Type: {card.get('type_line', 'N/A')}")
        lines.append(f"Mana Cost: {card.get('mana_cost') or faces[0].get('mana_cost', 'N/A')}")
        lines.append(f"Mana Value: {card.get('cmc', 'N/A')}")
        lines.append(f"Colors: {', '.join(card.get('colors', [])) or 'Colorless'}")
        lines.append(f"Color Identity: {', '.join(card.get('color_identity', [])) or 'Colorless'}")
        for i, face in enumerate(faces):
            label = "Front" if i == 0 else "Back"
            lines.append(f"--- {label} Face ---")
            lines.append(f"  Name: {face.get('name', 'N/A')}")
            lines.append(f"  Mana Cost: {face.get('mana_cost', 'N/A')}")
            lines.append(f"  Type: {face.get('type_line', 'N/A')}")
            lines.append(f"  Oracle Text: {face.get('oracle_text', 'N/A')}")
            if "power" in face:
                lines.append(f"  P/T: {face['power']}/{face['toughness']}")
            if "loyalty" in face:
                lines.append(f"  Loyalty: {face['loyalty']}")
        keywords = card.get("keywords", [])
        if keywords:
            lines.append(f"Keywords: {', '.join(keywords)}")
        legality = card.get("legalities", {}).get("commander", "N/A")
        lines.append(f"Commander Legal: {legality}")
        return "\n".join(lines)

    # Single-face card
    lines = [f"Name: {card['name']}"]
    lines.append(f"Mana Cost: {card.get('mana_cost', 'N/A')}")
    lines.append(f"Mana Value: {card.get('cmc', 'N/A')}")
    lines.append(f"Type: {card.get('type_line', 'N/A')}")
    lines.append(f"Oracle Text: {card.get('oracle_text', 'N/A')}")
    lines.append(f"Colors: {', '.join(card.get('colors', [])) or 'Colorless'}")
    lines.append(f"Color Identity: {', '.join(card.get('color_identity', [])) or 'Colorless'}")
    if "power" in card:
        lines.append(f"P/T: {card['power']}/{card['toughness']}")
    if "loyalty" in card:
        lines.append(f"Loyalty: {card['loyalty']}")
    keywords = card.get("keywords", [])
    if keywords:
        lines.append(f"Keywords: {', '.join(keywords)}")
    legality = card.get("legalities", {}).get("commander", "N/A")
    lines.append(f"Commander Legal: {legality}")
    return "\n".join(lines)


def cmd_search(name):
    """Fuzzy name search."""
    card = _request("/cards/named", {"fuzzy": name})
    print(_format_card(card))


def cmd_exact(name):
    """Exact name lookup."""
    card = _request("/cards/named", {"exact": name})
    print(_format_card(card))


def cmd_query(query):
    """Advanced search using Scryfall's full search syntax.

    Uses the /cards/search endpoint. Fetches up to 3 pages (225 cards max).
    Outputs a compact summary table.
    """
    MAX_PAGES = 3
    all_cards = []
    total_cards = 0

    data = _request("/cards/search", {"q": query, "order": "name"})
    total_cards = data.get("total_cards", 0)
    all_cards.extend(data.get("data", []))

    pages_fetched = 1
    while data.get("has_more") and pages_fetched < MAX_PAGES:
        time.sleep(DELAY_SEC)
        next_url = data["next_page"]
        req = urllib.request.Request(next_url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            break
        all_cards.extend(data.get("data", []))
        pages_fetched += 1

    print(f"Found {total_cards} cards (showing {len(all_cards)}):\n")
    print(f"{'Name':<35} {'Type':<30} {'CMC':>4} {'Colors':<12}")
    print("-" * 85)

    for card in all_cards:
        colors = ", ".join(card.get("colors", [])) or "C"
        type_line = card.get("type_line", "N/A")
        if len(type_line) > 28:
            type_line = type_line[:27] + "…"
        card_name = card["name"]
        if len(card_name) > 33:
            card_name = card_name[:32] + "…"
        print(f"{card_name:<35} {type_line:<30} {card.get('cmc', 0):>4.0f} {colors:<12}")


def cmd_batch(filepath):
    """Bulk lookup from a file of card names (one per line).

    Outputs a compact summary table for deck analysis.
    """
    try:
        with open(filepath) as f:
            names = [line.strip() for line in f if line.strip() and not line.startswith("//")]
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    # Print header
    print(f"{'Name':<35} {'Type':<30} {'CMC':>4} {'Colors':<12}")
    print("-" * 85)

    errors = []
    for i, name in enumerate(names):
        if i > 0:
            time.sleep(DELAY_SEC)
        try:
            card = _request("/cards/named", {"exact": name})
            colors = ", ".join(card.get("colors", [])) or "C"
            type_line = card.get("type_line", "N/A")
            # Truncate long type lines
            if len(type_line) > 28:
                type_line = type_line[:27] + "…"
            card_name = card["name"]
            if len(card_name) > 33:
                card_name = card_name[:32] + "…"
            print(f"{card_name:<35} {type_line:<30} {card.get('cmc', 0):>4.0f} {colors:<12}")
        except SystemExit:
            errors.append(name)
            # Reset so we don't actually exit
            continue

    if errors:
        print(f"\nFailed to look up {len(errors)} card(s):")
        for name in errors:
            print(f"  - {name}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "search" and len(sys.argv) == 3:
        cmd_search(sys.argv[2])
    elif cmd == "exact" and len(sys.argv) == 3:
        cmd_exact(sys.argv[2])
    elif cmd == "batch" and len(sys.argv) == 3:
        cmd_batch(sys.argv[2])
    elif cmd == "query" and len(sys.argv) == 3:
        cmd_query(sys.argv[2])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
