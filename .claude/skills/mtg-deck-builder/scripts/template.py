"""Template file parser for the mtg-deck-builder skill.

Templates define a deck's tag vocabulary, with optional count targets per tag.
A template file looks like:

    // Template: Command Zone
    // Description: Based on the Command Zone methodology.

    Ramp: 10
      Cards that accelerate mana production: rocks, dorks, ritual spells,
      cost reducers.

    CardAdvantage: 12
      Net-positive card draw or selection.

    Plan:
      Strategy cards specific to the deck's win condition. No target count.

Rules:
- `// ...` lines are comments.
- A tag header is `TagName: count` or `TagName: low-high` or `TagName:` (count optional).
- Lines indented by 2+ spaces (or a tab) following a tag header are part of that
  tag's description; they're joined with single spaces.
- A blank line ends the current tag block.
"""

import re
from pathlib import Path


_HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(?:(\d+)(?:\s*-\s*(\d+))?)?\s*$")


def parse_template(path):
    """Parse a template file. Returns a dict of {tag: {count, description, meta}}.

    Each value is a dict with:
      - count: (low, high) tuple, or None if no count specified
      - description: string (may be empty)

    Also returns the template's display name and description under the keys
    `_name` and `_description` in the top-level dict.
    """
    path = Path(path)
    tags = {}
    meta = {"_name": path.stem, "_description": ""}

    current_tag = None
    desc_lines = []

    def flush():
        nonlocal desc_lines
        if current_tag is not None:
            tags[current_tag]["description"] = " ".join(desc_lines).strip()
        desc_lines = []

    for raw in path.read_text().splitlines():
        # Strip trailing whitespace but keep leading for indent detection
        line = raw.rstrip()
        stripped = line.strip()

        # Comments
        if stripped.startswith("//"):
            # Pick up template-level metadata
            if stripped.startswith("// Template:"):
                meta["_name"] = stripped[len("// Template:"):].strip()
            elif stripped.startswith("// Description:"):
                meta["_description"] = stripped[len("// Description:"):].strip()
            continue

        # Blank line ends current tag block
        if not stripped:
            flush()
            current_tag = None
            continue

        # Indented continuation = description for current tag
        if current_tag and (raw.startswith("  ") or raw.startswith("\t")):
            desc_lines.append(stripped)
            continue

        # Tag header
        header = _HEADER_RE.match(stripped)
        if header:
            flush()
            name = header.group(1)
            low = header.group(2)
            high = header.group(3)
            if low is None:
                count = None
            else:
                low = int(low)
                high = int(high) if high else low
                count = (low, high)
            tags[name] = {"count": count, "description": ""}
            current_tag = name
            continue

        # Unparseable line: end current block to avoid swallowing into description
        flush()
        current_tag = None

    flush()
    return {**meta, **tags}


def get_tags(parsed):
    """Return only the tag entries from a parsed template (no metadata keys)."""
    return {k: v for k, v in parsed.items() if not k.startswith("_")}
