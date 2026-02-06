#!/usr/bin/env python3
"""Deck verification for MTG Commander decks.

Validates deck composition against Commander rules and optional templates.

Usage:
    verify.py check "<uuid>"                        Run all checks
    verify.py check "<uuid>" --template "<name>"    Also compare against template
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DECKS_DIR = Path.home() / ".mtg" / "decks"
TEMPLATES_DIR = Path.home() / ".mtg" / "templates"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

BASE_URL = "https://api.scryfall.com"
DELAY_SEC = 0.1
HEADERS = {
    "User-Agent": "MTGDeckBuilder/1.0",
    "Accept": "application/json",
}

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _request(url):
    """Make a GET request, returning parsed JSON."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        return {"error": body.get("details", e.reason)}


def _scryfall_search(query):
    """Search Scryfall, returning a list of card objects."""
    url = BASE_URL + "/cards/search?" + urllib.parse.urlencode({"q": query})
    data = _request(url)
    if "error" in data:
        return []
    return data.get("data", [])


def _scryfall_exact(name):
    """Look up a single card by exact name."""
    url = BASE_URL + "/cards/named?" + urllib.parse.urlencode({"exact": name})
    return _request(url)


def _require_deck(deck_id):
    """Validate UUID and return deck directory path."""
    if not UUID_RE.match(deck_id):
        print(f"Error: Invalid UUID: {deck_id}", file=sys.stderr)
        sys.exit(1)
    deck_path = DECKS_DIR / deck_id
    if not deck_path.is_dir():
        print(f"Error: Deck not found: {deck_id}", file=sys.stderr)
        sys.exit(1)
    return deck_path


def _parse_card_line(line):
    """Parse a card line into (quantity, name, tags).

    Handles formats like:
        1 Sol Ring
        1 Sol Ring #Ramp #!ArtifactSynergy
        1 Sol Ring (CMR) 632 *F* #Ramp
    """
    line = line.strip()
    if not line or line.startswith("//"):
        return None

    # Extract tags from end
    tags = []
    parts = line.split()
    while parts and parts[-1].startswith("#"):
        tags.insert(0, parts.pop())

    # Remove foil indicator
    if parts and parts[-1] == "*F*":
        parts.pop()

    # Remove collector number (digits after set code)
    if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].startswith("("):
        parts.pop()  # collector number
        parts.pop()  # set code

    # First token is quantity
    if not parts or not parts[0].isdigit():
        return None

    qty = int(parts[0])
    name = " ".join(parts[1:])
    return qty, name, tags


def _read_card_lines(filepath):
    """Read and parse all card lines from a file."""
    cards = []
    if not filepath.exists():
        return cards
    for line in filepath.read_text().splitlines():
        parsed = _parse_card_line(line)
        if parsed:
            cards.append(parsed)
    return cards


def _check_card_count(commanders, main):
    """Check that total card count is 100."""
    total = sum(q for q, _, _ in commanders) + sum(q for q, _, _ in main)
    if total == 100:
        return "PASS", f"Card count: {total}/100"
    elif total < 100:
        return "FAIL", f"Card count: {total}/100 (need {100 - total} more)"
    else:
        return "FAIL", f"Card count: {total}/100 ({total - 100} over)"


def _check_singleton(commanders, main):
    """Check singleton rule (no duplicates except basic lands)."""
    seen = {}
    all_cards = commanders + main
    duplicates = []
    for qty, name, _ in all_cards:
        if name in BASIC_LANDS:
            continue
        if qty > 1:
            duplicates.append(f"{name} (x{qty})")
        if name in seen:
            duplicates.append(f"{name} (in multiple sections)")
        seen[name] = True

    if not duplicates:
        return "PASS", "Singleton rule: OK"
    return "FAIL", "Singleton violations:\n" + "\n".join(f"  - {d}" for d in duplicates)


def _check_legality(commanders, main):
    """Check Commander legality via Scryfall."""
    all_cards = commanders + main
    unique_names = list(dict.fromkeys(name for _, name, _ in all_cards))

    banned = []
    not_legal = []
    errors = []

    for i, name in enumerate(unique_names):
        if i > 0:
            time.sleep(DELAY_SEC)
        card = _scryfall_exact(name)
        if "error" in card:
            errors.append(name)
            continue
        legality = card.get("legalities", {}).get("commander", "unknown")
        if legality == "banned":
            banned.append(name)
        elif legality == "not_legal":
            not_legal.append(name)

    lines = []
    if banned:
        lines.append("Banned in Commander:")
        lines.extend(f"  - {n}" for n in banned)
    if not_legal:
        lines.append("Not legal in Commander:")
        lines.extend(f"  - {n}" for n in not_legal)
    if errors:
        lines.append("Could not look up:")
        lines.extend(f"  - {n}" for n in errors)

    if not lines:
        return "PASS", f"Commander legality: all {len(unique_names)} cards legal"
    return "FAIL", "\n".join(lines)


def _check_color_identity(commanders, main):
    """Check all cards fit within commander's color identity."""
    if not commanders:
        return "WARN", "No commander found, skipping color identity check"

    # Look up commander color identity
    commander_name = commanders[0][1]
    cmd_card = _scryfall_exact(commander_name)
    if "error" in cmd_card:
        return "WARN", f"Could not look up commander: {commander_name}"

    cmd_identity = set(cmd_card.get("color_identity", []))
    identity_str = ", ".join(sorted(cmd_identity)) or "Colorless"

    # Check each card
    violations = []
    all_cards = commanders[1:] + main  # skip the commander itself
    unique_names = list(dict.fromkeys(name for _, name, _ in all_cards))

    for i, name in enumerate(unique_names):
        if i > 0:
            time.sleep(DELAY_SEC)
        card = _scryfall_exact(name)
        if "error" in card:
            continue
        card_identity = set(card.get("color_identity", []))
        if not card_identity.issubset(cmd_identity):
            extra = ", ".join(sorted(card_identity - cmd_identity))
            violations.append(f"{name} (adds {extra})")

    if not violations:
        return "PASS", f"Color identity ({identity_str}): all cards within identity"
    return "FAIL", (
        f"Cards outside commander's color identity ({identity_str}):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def _resolve_template(template_name):
    """Resolve a template name to a path, checking user dir then assets."""
    safe_name = re.sub(r"[^a-z0-9]+", "-", template_name.lower()).strip("-")
    filename = f"{safe_name}.txt"
    user_path = TEMPLATES_DIR / filename
    if user_path.exists():
        return user_path
    bundled_path = ASSETS_DIR / filename
    if bundled_path.exists():
        return bundled_path
    return None


def _check_template(commanders, main, template_name):
    """Compare deck composition against a template."""
    template_path = _resolve_template(template_name)
    if template_path is None:
        return "WARN", f"Template not found: {template_name}"

    # Parse template targets
    targets = {}
    for line in template_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        match = re.match(r"^(.+?):\s*(\d+)(?:\s*-\s*(\d+))?$", line)
        if match:
            category = match.group(1).strip()
            low = int(match.group(2))
            high = int(match.group(3)) if match.group(3) else low
            targets[category] = (low, high)

    if not targets:
        return "WARN", "Template has no category targets defined"

    # Count cards per tag category
    all_cards = commanders + main
    tag_counts = {}
    for _, _, tags in all_cards:
        for tag in tags:
            # Strip # or #! prefix
            if tag.startswith("#!"):
                cat = tag[2:]
            elif tag.startswith("#"):
                cat = tag[1:]
            else:
                continue
            tag_counts[cat] = tag_counts.get(cat, 0) + 1

    # Build comparison table
    lines = [f"{'Category':<20} {'Target':<12} {'Actual':>8}  Status"]
    lines.append("-" * 55)
    all_ok = True
    for category, (low, high) in targets.items():
        actual = tag_counts.get(category, 0)
        target_str = str(low) if low == high else f"{low}-{high}"
        if actual < low:
            status = f"Under by {low - actual}"
            all_ok = False
        elif actual > high:
            status = f"Over by {actual - high}"
            all_ok = False
        else:
            status = "OK"
        lines.append(f"{category:<20} {target_str:<12} {actual:>8}  {status}")

    result = "PASS" if all_ok else "WARN"
    return result, "\n".join(lines)


def cmd_check(deck_id, template_name=None):
    """Run all verification checks on a deck."""
    deck_path = _require_deck(deck_id)

    # Read deck metadata
    meta_path = deck_path / "meta.yml"
    deck_name = "Unknown"
    if meta_path.exists():
        for line in meta_path.read_text().splitlines():
            if line.startswith("name:"):
                deck_name = line[len("name:"):].strip()

    commanders = _read_card_lines(deck_path / "commanders.txt")
    main = _read_card_lines(deck_path / "main.txt")

    print(f"Verifying: {deck_name} ({deck_id})\n")

    checks = [
        ("Card Count", _check_card_count(commanders, main)),
        ("Singleton Rule", _check_singleton(commanders, main)),
    ]

    # Print quick checks first
    for label, (status, detail) in checks:
        print(f"[{status}] {label}")
        if status != "PASS":
            for line in detail.split("\n"):
                print(f"  {line}")
        else:
            print(f"  {detail}")
        print()

    # Scryfall-dependent checks (slower)
    total_cards = sum(q for q, _, _ in commanders) + sum(q for q, _, _ in main)
    if total_cards > 0:
        print("Checking legality via Scryfall (this may take a moment)...\n")

        status, detail = _check_legality(commanders, main)
        print(f"[{status}] Commander Legality")
        for line in detail.split("\n"):
            print(f"  {line}")
        print()

        status, detail = _check_color_identity(commanders, main)
        print(f"[{status}] Color Identity")
        for line in detail.split("\n"):
            print(f"  {line}")
        print()

    # Template check
    if template_name:
        status, detail = _check_template(commanders, main, template_name)
        print(f"[{status}] Template: {template_name}")
        for line in detail.split("\n"):
            print(f"  {line}")
        print()


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd != "check":
        print(__doc__.strip())
        sys.exit(1)

    deck_id = sys.argv[2]
    template_name = None

    # Parse --template flag
    if "--template" in sys.argv:
        idx = sys.argv.index("--template")
        if idx + 1 < len(sys.argv):
            template_name = sys.argv[idx + 1]
        else:
            print("Error: --template requires a name argument", file=sys.stderr)
            sys.exit(1)

    cmd_check(deck_id, template_name)


if __name__ == "__main__":
    main()
