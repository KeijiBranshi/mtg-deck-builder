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
- Looks up card data via the Scryfall API (names, types, mana costs, legality, color identity)
- Verifies decks against Commander rules (100-card singleton, color identity, ban list)
- Supports deck composition templates (e.g., the Command Zone methodology)
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
```

Card lines follow the Moxfield format: `1 Card Name #Tag1 #Tag2`
