#!/usr/bin/env python3
"""Deck file manager for MTG deck lists.

Manages deck directories under ~/.mtg/decks/<uuid>/ with Moxfield-compatible
card list files and YAML metadata.

Deck structure:
    ~/.mtg/decks/<uuid>/
        meta.yml          Deck metadata (name, format, etc.)
        commanders.txt    Commander card(s), 1-2 lines
        main.txt          Main deck cards
        sideboard.txt     Sideboard cards
        considering.txt   Cards under consideration
        batches/          Workspace for batch lookup files

Templates are resolved from two locations (user-space takes priority):
    1. ~/.mtg/templates/         User-space templates
    2. <skill>/assets/           Bundled templates shipped with the skill

Usage:
    deck.py create "<deck-name>" "<commander-name>"
    deck.py list
    deck.py show "<uuid>"
    deck.py path "<uuid>" [file]
    deck.py template create "<name>"
    deck.py template list
    deck.py template show "<name>"
    deck.py template path "<name>"
    deck.py template delete "<name>"
"""

import re
import sys
import uuid
from pathlib import Path

DECKS_DIR = Path.home() / ".mtg" / "decks"
TEMPLATES_DIR = Path.home() / ".mtg" / "templates"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

DECK_FILES = ["commanders.txt", "main.txt", "sideboard.txt", "considering.txt"]
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def _ensure_dir(path):
    """Create a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def _deck_dir(deck_id):
    """Return the directory path for a deck, validating the UUID."""
    try:
        uuid.UUID(deck_id)
    except ValueError:
        print(f"Error: Invalid UUID: {deck_id}", file=sys.stderr)
        sys.exit(1)
    return DECKS_DIR / deck_id


def _deck_file(deck_id, filename):
    """Return the path to a specific file within a deck directory."""
    return _deck_dir(deck_id) / filename


def _require_deck(deck_id):
    """Validate UUID and check that the deck directory exists."""
    deck_path = _deck_dir(deck_id)
    if not deck_path.is_dir():
        print(f"Error: Deck not found: {deck_id}", file=sys.stderr)
        sys.exit(1)
    return deck_path


def _write_meta(deck_path, name):
    """Write YAML metadata file for a deck."""
    meta_path = deck_path / "meta.yml"
    meta_path.write_text(f"name: {name}\nformat: commander\n")


def _parse_meta(deck_path):
    """Read deck metadata from meta.yml and card files.

    Returns (deck_name, commander_name, card_count).
    """
    deck_name = "Unknown"
    commander = "Unknown"
    card_count = 0

    meta_path = deck_path / "meta.yml"
    if meta_path.exists():
        for line in meta_path.read_text().splitlines():
            if line.startswith("name:"):
                deck_name = line[len("name:"):].strip()

    commanders_path = deck_path / "commanders.txt"
    if commanders_path.exists():
        lines = [l.strip() for l in commanders_path.read_text().splitlines()
                 if l.strip() and not l.strip().startswith("//")]
        if lines:
            # Strip quantity prefix (e.g., "1 Atraxa..." -> "Atraxa...")
            first = lines[0]
            parts = first.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                commander = parts[1]
            else:
                commander = first
            card_count += len(lines)

    main_path = deck_path / "main.txt"
    if main_path.exists():
        main_lines = [l.strip() for l in main_path.read_text().splitlines()
                      if l.strip() and not l.strip().startswith("//")]
        card_count += len(main_lines)

    return deck_name, commander, card_count


# ---------------------------------------------------------------------------
# Deck commands
# ---------------------------------------------------------------------------

def cmd_create(deck_name, commander_name):
    """Create a new deck directory with initial files."""
    _ensure_dir(DECKS_DIR)
    deck_id = str(uuid.uuid4())
    deck_path = DECKS_DIR / deck_id

    deck_path.mkdir()
    (deck_path / "batches").mkdir()

    _write_meta(deck_path, deck_name)
    (deck_path / "commanders.txt").write_text(f"1 {commander_name}\n")
    (deck_path / "main.txt").write_text("")
    (deck_path / "sideboard.txt").write_text("")
    (deck_path / "considering.txt").write_text("")

    print(f"Created: {deck_id}")
    print(f"Path: {deck_path}")


def cmd_list():
    """List all decks."""
    _ensure_dir(DECKS_DIR)
    dirs = sorted(d for d in DECKS_DIR.iterdir()
                  if d.is_dir() and UUID_RE.match(d.name))
    if not dirs:
        print("No decks found.")
        return

    print(f"{'UUID':<38} {'Deck Name':<30} {'Commander':<30} {'Cards':>5}")
    print("-" * 107)
    for d in dirs:
        name, commander, count = _parse_meta(d)
        if len(name) > 28:
            name = name[:27] + "\u2026"
        if len(commander) > 28:
            commander = commander[:27] + "\u2026"
        print(f"{d.name:<38} {name:<30} {commander:<30} {count:>5}")


def cmd_show(deck_id):
    """Print the full contents of a deck."""
    deck_path = _require_deck(deck_id)
    name, _, _ = _parse_meta(deck_path)

    print(f"// Deck: {name}")

    sections = [
        ("Commanders", "commanders.txt"),
        ("Main", "main.txt"),
        ("Sideboard", "sideboard.txt"),
        ("Considering", "considering.txt"),
    ]
    for label, filename in sections:
        filepath = deck_path / filename
        if filepath.exists():
            content = filepath.read_text().rstrip("\n")
            if content:
                print(f"// {label}")
                print(content)


def cmd_path(deck_id, subfile=None):
    """Print the path for a deck directory or a specific file within it."""
    deck_path = _require_deck(deck_id)
    if subfile:
        # Map short names to filenames
        name_map = {
            "meta": "meta.yml",
            "commanders": "commanders.txt",
            "main": "main.txt",
            "sideboard": "sideboard.txt",
            "considering": "considering.txt",
            "batches": "batches",
        }
        filename = name_map.get(subfile, subfile)
        target = deck_path / filename
        if not target.exists():
            print(f"Error: File not found: {filename}", file=sys.stderr)
            sys.exit(1)
        print(target)
    else:
        print(deck_path)


# ---------------------------------------------------------------------------
# Template commands
# ---------------------------------------------------------------------------

def _sanitize_template_name(name):
    """Convert a template name to a filesystem-safe string."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _template_filename(name):
    """Return the sanitized filename for a template."""
    safe = _sanitize_template_name(name)
    if not safe:
        print(f"Error: Invalid template name: {name}", file=sys.stderr)
        sys.exit(1)
    return f"{safe}.txt"


def _resolve_template(name):
    """Resolve a template name to a path, checking user dir then assets.

    Returns (path, is_bundled) or exits with an error if not found.
    """
    filename = _template_filename(name)
    user_path = TEMPLATES_DIR / filename
    if user_path.exists():
        return user_path, False
    bundled_path = ASSETS_DIR / filename
    if bundled_path.exists():
        return bundled_path, True
    return None, False


def _template_path(name):
    """Return the path for a user-space template file."""
    safe = _sanitize_template_name(name)
    if not safe:
        print(f"Error: Invalid template name: {name}", file=sys.stderr)
        sys.exit(1)
    return TEMPLATES_DIR / f"{safe}.txt"


def cmd_template_create(name):
    """Create a new template file."""
    _ensure_dir(TEMPLATES_DIR)
    path = _template_path(name)
    if path.exists():
        print(f"Error: Template already exists: {path.stem}", file=sys.stderr)
        sys.exit(1)
    path.write_text(f"// Template: {name}\n// Description:\n")
    print(f"Created template: {path.stem}")
    print(f"Path: {path}")


def cmd_template_list():
    """List available templates from both user and bundled directories."""
    _ensure_dir(TEMPLATES_DIR)

    # Collect templates: user-space first, then bundled (skip duplicates)
    seen = set()
    entries = []  # (stem, display_name, source_label)

    for f in sorted(TEMPLATES_DIR.glob("*.txt")):
        display_name = f.stem
        for line in f.read_text().splitlines():
            if line.startswith("// Template:"):
                display_name = line[len("// Template:"):].strip()
                break
        seen.add(f.stem)
        entries.append((f.stem, display_name, "user"))

    if ASSETS_DIR.is_dir():
        for f in sorted(ASSETS_DIR.glob("*.txt")):
            if f.stem not in seen:
                display_name = f.stem
                for line in f.read_text().splitlines():
                    if line.startswith("// Template:"):
                        display_name = line[len("// Template:"):].strip()
                        break
                entries.append((f.stem, display_name, "bundled"))

    if not entries:
        print("No templates found.")
        return

    for stem, display_name, source in entries:
        tag = " [bundled]" if source == "bundled" else ""
        print(f"  {stem:<30} {display_name}{tag}")


def cmd_template_show(name):
    """Print the contents of a template (user or bundled)."""
    path, _ = _resolve_template(name)
    if path is None:
        print(f"Error: Template not found: {name}", file=sys.stderr)
        sys.exit(1)
    print(path.read_text(), end="")


def cmd_template_path(name):
    """Print the path for a template file (user or bundled)."""
    path, _ = _resolve_template(name)
    if path is None:
        print(f"Error: Template not found: {name}", file=sys.stderr)
        sys.exit(1)
    print(path)


def cmd_template_delete(name):
    """Delete a user-space template file. Bundled templates cannot be deleted."""
    path, is_bundled = _resolve_template(name)
    if path is None:
        print(f"Error: Template not found: {name}", file=sys.stderr)
        sys.exit(1)
    if is_bundled:
        print(f"Error: Cannot delete bundled template: {name}", file=sys.stderr)
        sys.exit(1)
    path.unlink()
    print(f"Deleted template: {path.stem}")


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    cmd = sys.argv[1]

    # Template subcommand group
    if cmd == "template":
        if len(sys.argv) < 3:
            print("Usage: deck.py template <create|list|show|path|delete> [args]")
            sys.exit(1)
        subcmd = sys.argv[2]
        if subcmd == "create" and len(sys.argv) == 4:
            cmd_template_create(sys.argv[3])
        elif subcmd == "list" and len(sys.argv) == 3:
            cmd_template_list()
        elif subcmd == "show" and len(sys.argv) == 4:
            cmd_template_show(sys.argv[3])
        elif subcmd == "path" and len(sys.argv) == 4:
            cmd_template_path(sys.argv[3])
        elif subcmd == "delete" and len(sys.argv) == 4:
            cmd_template_delete(sys.argv[3])
        else:
            print("Usage: deck.py template <create|list|show|path|delete> [args]")
            sys.exit(1)
        return

    # Deck commands
    if cmd == "create" and len(sys.argv) == 4:
        cmd_create(sys.argv[2], sys.argv[3])
    elif cmd == "list" and len(sys.argv) == 2:
        cmd_list()
    elif cmd == "show" and len(sys.argv) == 3:
        cmd_show(sys.argv[2])
    elif cmd == "path" and len(sys.argv) in (3, 4):
        subfile = sys.argv[3] if len(sys.argv) == 4 else None
        cmd_path(sys.argv[2], subfile)
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
