# MTG Deck Builder

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill for building and managing Magic: The Gathering Commander/EDH deck lists in Moxfield-compatible text format.

## Usage

```bash
cd mtg-deck-builder
claude
```

Then ask Claude to help you build a deck:

- "Build me a Commander deck around Atraxa, Praetors' Voice"
- "Add Sol Ring and Arcane Signet to my deck"
- "What does my mana curve look like?"
- "Check if my deck is legal"
- "Search for creatures with draw effects under 3 mana"

## What It Does

- Creates and manages deck lists stored under `~/.mtg/decks/`
- Looks up card data via the Scryfall API (names, types, mana costs, legality, color identity), with on-disk caching to avoid rate limits
- Resolves user-known aliases for reskinned cards (e.g., Universes Beyond printings that share oracle text with an existing card)
- Verifies decks against Commander rules (100-card singleton, color identity, ban list)
- Supports deck composition **templates** that define a tag vocabulary with optional count targets and descriptions
- Suggests tags for cards based on heuristic oracle-text matching (`--suggest-tags`)
- Generates a `primer.md` strategy guide once a deck is finalized
- Outputs Moxfield-compatible text files you can import directly

## Deck Structure

Each deck is a directory of plain text files:

```
~/.mtg/decks/<uuid>/
    meta.yml          Deck metadata (name, format)
    commanders.txt    Commander card(s)
    main.txt          Main deck cards
    sideboard.txt     Sideboard cards
    considering.txt   Cards under consideration
    primer.md         Strategy guide (written after the deck is finalized)
    tags.md           Optional: deck-specific tag definitions
    batches/          Workspace for bulk lookup files
```

Card lines follow the Moxfield format: `1 Card Name #Tag1 #Tag2`. Tags prefixed with `#` are local to the deck; `#!` tags are global across the user's Moxfield collection.
