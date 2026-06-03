#!/usr/bin/env python3
"""Scryfall API wrapper for MTG card data lookup.

Usage:
    scryfall.py search "<name>"     Fuzzy name search
    scryfall.py exact "<name>"      Exact name lookup
    scryfall.py batch "<file>"      Bulk lookup from file (one card name per line)
    scryfall.py query "<query>"     Advanced search using Scryfall syntax
    scryfall.py cache <op> [...]    Manage the on-disk card cache

Cache subcommands:
    scryfall.py cache stats
    scryfall.py cache clear
    scryfall.py cache evict --name "<card>"
    scryfall.py cache evict --older-than <duration>   e.g. 30d, 12h, 300s

Global flags (apply to search/exact/batch/query):
    --no-cache             Bypass the on-disk cache for this invocation
    --max-age <duration>   Treat cache entries older than this as misses

Query-only flags:
    --max-pages N          Page cap (default 3, 0 = unlimited until has_more is false)

Batch/query flags:
    --verbose              Print full oracle text per card instead of the compact table

Tag-suggestion flags (apply to exact and batch):
    --suggest-tags         Emit a heuristic `Suggested tags:` line per card
    --template <name>      Restrict tag suggestions to this template's vocabulary
    --deck <uuid>          Augment vocabulary with the deck's tags.md (if present)

Query examples:
    scryfall.py query "t:creature o:draw cmc<=3"
    scryfall.py query "t:instant id:dimir o:counter"
    scryfall.py query "t:land id:gruul"
    scryfall.py query "id:b is:commander_legal o:'lose ~ life'" --max-pages 0 --verbose

Common Scryfall search syntax:
    o:text       oracle text contains "text"
    t:type       type line contains "type"
    c:color      card color (w/u/b/r/g)
    id:color     color identity
    cmc:N        mana value equals N (also cmc>=N, cmc<=N)
    is:commander legal as commander
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from card_cache import CardCache, parse_duration

BASE_URL = "https://api.scryfall.com"
DELAY_SEC = 0.2  # 200ms between requests (~5 req/s, under Scryfall's <10 req/s limit)
MAX_RETRIES = 3
DEFAULT_RETRY_WAIT = 60  # seconds; used when Retry-After header is missing
MAX_RETRY_WAIT = 90      # cap to keep runs bounded
HEADERS = {
    "User-Agent": "MTGDeckBuilder/1.0",
    "Accept": "application/json",
}

CACHE = CardCache(Path.home() / ".mtg" / "cache" / "scryfall" / "cards")

ALIASES_PATH = Path(__file__).resolve().parent.parent / "references" / "card-aliases.json"


def _load_aliases():
    """Load the card name alias map. Returns {} if the file is missing or malformed."""
    try:
        data = json.loads(ALIASES_PATH.read_text())
        return data.get("aliases", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


ALIASES = _load_aliases()


def _resolve_alias(name):
    """Map a user-supplied name to its canonical Scryfall name if aliased.

    Prints a notice to stderr when an alias is applied so the user sees the
    substitution rather than wondering why the wrong card came back.
    """
    canonical = ALIASES.get(name)
    if canonical and canonical != name:
        print(f"[alias] {name!r} → {canonical!r}", file=sys.stderr)
        return canonical
    return name


def _request(path, params=None):
    """Make a GET request to the Scryfall API, retrying on 429."""
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)

    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                try:
                    wait = int(e.headers.get("Retry-After", DEFAULT_RETRY_WAIT))
                except (TypeError, ValueError):
                    wait = DEFAULT_RETRY_WAIT
                wait = min(max(wait, 1), MAX_RETRY_WAIT)
                print(f"Rate limited; waiting {wait}s before retry ({attempt + 1}/{MAX_RETRIES})...", file=sys.stderr)
                time.sleep(wait)
                continue
            try:
                body = json.loads(e.read().decode())
                detail = body.get("details", e.reason)
            except (json.JSONDecodeError, ValueError):
                detail = e.reason
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


def _lookup_exact(name, use_cache=True, max_age_sec=None):
    """Look up a card by exact name, consulting the cache when allowed."""
    name = _resolve_alias(name)
    if use_cache:
        cached = CACHE.get(name, max_age_sec)
        if cached is not None:
            return cached, True
    card = _request("/cards/named", {"exact": name})
    CACHE.put(name, card)
    return card, False


def cmd_search(name, use_cache=True, max_age_sec=None):
    """Fuzzy name search. Caches the resolved card under its canonical name."""
    name = _resolve_alias(name)
    # Fuzzy input rarely matches the cache key; check anyway in case the user
    # passed the canonical name.
    if use_cache:
        cached = CACHE.get(name, max_age_sec)
        if cached is not None:
            print(_format_card(cached))
            return
    card = _request("/cards/named", {"fuzzy": name})
    CACHE.put(name, card)
    print(_format_card(card))


def cmd_exact(name, use_cache=True, max_age_sec=None,
              suggest_tags=False, template_name=None, deck_id=None):
    """Exact name lookup. Optionally appends a `Suggested tags:` line."""
    card, _ = _lookup_exact(name, use_cache=use_cache, max_age_sec=max_age_sec)
    print(_format_card(card))
    if suggest_tags:
        from tag_suggest import suggest_tags as _suggest

        template_vocab, _parsed = _load_template_vocabulary(template_name)
        deck_vocab = _load_deck_tags(deck_id)
        vocabulary = None
        if template_vocab is not None or deck_vocab:
            vocabulary = (template_vocab or set()) | deck_vocab
        tags = _suggest(card, vocabulary=vocabulary)
        tag_str = " ".join(f"#{t}" for t in tags) if tags else "(none)"
        print(f"Suggested tags: {tag_str}")


def cmd_query(query, max_pages=3, verbose=False):
    """Advanced search using Scryfall's full search syntax.

    Uses the /cards/search endpoint. By default fetches up to 3 pages (~525 cards).
    Pass max_pages=0 for unlimited paging. Pass verbose=True to print full oracle
    text per card instead of the compact summary table.
    """
    all_cards = []
    total_cards = 0

    data = _request("/cards/search", {"q": query, "order": "name"})
    total_cards = data.get("total_cards", 0)
    all_cards.extend(data.get("data", []))

    pages_fetched = 1
    while data.get("has_more") and (max_pages == 0 or pages_fetched < max_pages):
        time.sleep(DELAY_SEC)
        next_url = data["next_page"]
        req = urllib.request.Request(next_url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError:
            break
        all_cards.extend(data.get("data", []))
        pages_fetched += 1

    print(f"Found {total_cards} cards (showing {len(all_cards)} across {pages_fetched} page(s)):\n")

    if verbose:
        for card in all_cards:
            # Reuse the single-card formatter; cache so later exact lookups are free.
            CACHE.put(card["name"], card)
            print(_format_card(card))
            print()
        return

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


def _load_template_vocabulary(template_name):
    """Resolve a template by name and return (vocabulary_set, parsed) or (None, None)."""
    if not template_name:
        return None, None
    # Import locally to avoid pulling deck.py if --template isn't used.
    from template import get_tags, parse_template

    user_dir = Path.home() / ".mtg" / "templates"
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in template_name.lower()).strip("-")
    for d in (user_dir, assets_dir):
        candidate = d / f"{safe}.txt"
        if candidate.exists():
            parsed = parse_template(candidate)
            return set(get_tags(parsed).keys()), parsed
    print(f"[warn] Template not found: {template_name}", file=sys.stderr)
    return None, None


def _load_deck_tags(deck_id):
    """Read tag names from a deck-local tags.md if present. Returns set of names."""
    if not deck_id:
        return set()
    path = Path.home() / ".mtg" / "decks" / deck_id / "tags.md"
    if not path.exists():
        return set()
    names = set()
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*##\s+([A-Za-z][A-Za-z0-9_]*)\s*$", line)
        if m:
            names.add(m.group(1))
    return names


def cmd_batch(filepath, use_cache=True, max_age_sec=None, verbose=False,
              suggest_tags=False, template_name=None, deck_id=None):
    """Bulk lookup from a file of card names (one per line).

    Outputs a compact summary table for deck analysis, or full oracle text per
    card when verbose=True (useful for bulk tagging or category analysis).

    When suggest_tags=True, emits a `Suggested tags:` line after each card based
    on heuristic oracle-text matching. Pass `template_name` to restrict
    suggestions to that template's vocabulary; `deck_id` augments the vocabulary
    with tags defined in the deck's local tags.md.
    """
    try:
        with open(filepath) as f:
            names = [line.strip() for line in f if line.strip() and not line.startswith("//")]
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    vocabulary = None
    if suggest_tags:
        # Import locally so the script's import cost stays minimal when unused.
        from tag_suggest import suggest_tags as _suggest

        template_vocab, _ = _load_template_vocabulary(template_name)
        deck_vocab = _load_deck_tags(deck_id)
        if template_vocab is not None or deck_vocab:
            vocabulary = (template_vocab or set()) | deck_vocab

    if not verbose:
        print(f"{'Name':<35} {'Type':<30} {'CMC':>4} {'Colors':<12}")
        print("-" * 85)

    errors = []
    hit_api = False
    for name in names:
        try:
            card, was_cached = _lookup_exact(name, use_cache=use_cache, max_age_sec=max_age_sec)
        except SystemExit:
            errors.append(name)
            continue
        if not was_cached:
            # Throttle only between actual API calls; cache hits are free.
            if hit_api:
                time.sleep(DELAY_SEC)
            hit_api = True
        if verbose:
            print(_format_card(card))
            if suggest_tags:
                tags = _suggest(card, vocabulary=vocabulary)
                tag_str = " ".join(f"#{t}" for t in tags) if tags else "(none)"
                print(f"Suggested tags: {tag_str}")
            print()
            continue
        colors = ", ".join(card.get("colors", [])) or "C"
        type_line = card.get("type_line", "N/A")
        if len(type_line) > 28:
            type_line = type_line[:27] + "…"
        card_name = card["name"]
        if len(card_name) > 33:
            card_name = card_name[:32] + "…"
        print(f"{card_name:<35} {type_line:<30} {card.get('cmc', 0):>4.0f} {colors:<12}")
        if suggest_tags:
            tags = _suggest(card, vocabulary=vocabulary)
            tag_str = " ".join(f"#{t}" for t in tags) if tags else "(none)"
            print(f"    suggested: {tag_str}")

    if errors:
        print(f"\nFailed to look up {len(errors)} card(s):")
        for name in errors:
            print(f"  - {name}")


def _format_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _format_ts(ts):
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def cmd_cache(args):
    """Cache management."""
    if not args:
        print("Usage: scryfall.py cache <stats|clear|evict ...>", file=sys.stderr)
        sys.exit(1)

    sub = args[0]
    rest = args[1:]

    if sub == "stats":
        s = CACHE.stats()
        print(f"Location:     {CACHE.cache_dir}")
        print(f"Entries:      {s['count']}")
        print(f"Total size:   {_format_size(s['bytes'])}")
        print(f"Oldest entry: {_format_ts(s['oldest'])}")
        print(f"Newest entry: {_format_ts(s['newest'])}")
        return

    if sub == "clear":
        n = CACHE.clear()
        print(f"Cleared {n} cached card(s) from {CACHE.cache_dir}")
        return

    if sub == "evict":
        if rest and rest[0] == "--name" and len(rest) >= 2:
            if CACHE.evict_name(rest[1]):
                print(f"Evicted: {rest[1]}")
            else:
                print(f"Not in cache: {rest[1]}")
            return
        if rest and rest[0] == "--older-than" and len(rest) >= 2:
            try:
                age = parse_duration(rest[1])
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            n = CACHE.evict_older_than(age)
            print(f"Evicted {n} entries older than {rest[1]}")
            return
        print("Usage: scryfall.py cache evict (--name <card> | --older-than <duration>)", file=sys.stderr)
        sys.exit(1)

    print(f"Unknown cache subcommand: {sub}", file=sys.stderr)
    sys.exit(1)


def _extract_flag(name):
    if name in sys.argv:
        sys.argv.remove(name)
        return True
    return False


def _extract_value(name):
    if name in sys.argv:
        idx = sys.argv.index(name)
        if idx + 1 < len(sys.argv):
            val = sys.argv[idx + 1]
            del sys.argv[idx:idx + 2]
            return val
        print(f"Error: {name} requires a value", file=sys.stderr)
        sys.exit(1)
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    no_cache = _extract_flag("--no-cache")
    max_age_raw = _extract_value("--max-age")
    max_age_sec = None
    if max_age_raw is not None:
        try:
            max_age_sec = parse_duration(max_age_raw)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    use_cache = not no_cache

    verbose = _extract_flag("--verbose")
    suggest_tags_flag = _extract_flag("--suggest-tags")
    template_name = _extract_value("--template")
    deck_id = _extract_value("--deck")
    max_pages_raw = _extract_value("--max-pages")
    max_pages = 3
    if max_pages_raw is not None:
        try:
            max_pages = int(max_pages_raw)
            if max_pages < 0:
                raise ValueError
        except ValueError:
            print("Error: --max-pages must be a non-negative integer (0 = unlimited)", file=sys.stderr)
            sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "search" and len(sys.argv) == 3:
        cmd_search(sys.argv[2], use_cache=use_cache, max_age_sec=max_age_sec)
    elif cmd == "exact" and len(sys.argv) == 3:
        cmd_exact(sys.argv[2], use_cache=use_cache, max_age_sec=max_age_sec,
                  suggest_tags=suggest_tags_flag,
                  template_name=template_name, deck_id=deck_id)
    elif cmd == "batch" and len(sys.argv) == 3:
        cmd_batch(sys.argv[2], use_cache=use_cache, max_age_sec=max_age_sec,
                  verbose=verbose, suggest_tags=suggest_tags_flag,
                  template_name=template_name, deck_id=deck_id)
    elif cmd == "query" and len(sys.argv) == 3:
        cmd_query(sys.argv[2], max_pages=max_pages, verbose=verbose)
    elif cmd == "cache":
        cmd_cache(sys.argv[2:])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
