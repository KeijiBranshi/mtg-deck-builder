# Moxfield Decklist Format

## Line Format

```
AMOUNT CARDNAME (SETCODE) NUMBER *F* TAGLIST
```

| Field | Required | Description |
|-------|----------|-------------|
| `AMOUNT` | Yes | Integer quantity (usually `1` for Commander singleton) |
| `CARDNAME` | Yes | Exact card name as printed. Use the name returned by Scryfall. |
| `(SETCODE)` | No | 3-4 letter set code in parentheses, e.g. `(CMR)` |
| `NUMBER` | No | Collector number. Only valid when set code is present. |
| `*F*` | No | Foil indicator |
| Tags | No | Space-separated tags at end of line |

### Tags

- **Local tags**: `#TagName` — apply only to this specific deck
- **Global tags**: `#!TagName` — apply across the user's entire Moxfield collection

Tag names may contain letters, numbers, and spaces (though spaces within a single tag are uncommon). Each tag is prefixed with `#` or `#!`.

## Deck Directory Structure

Each deck is stored as a directory under `~/.mtg/decks/<uuid>/`:

```
~/.mtg/decks/<uuid>/
    meta.yml          Deck metadata (YAML)
    commanders.txt    Commander card(s)
    main.txt          Main deck cards
    sideboard.txt     Sideboard cards
    considering.txt   Cards under consideration
    primer.md         Strategy guide (created in Phase 6)
    tags.md           Optional: deck-specific tag definitions (see below)
    batches/          Workspace for batch lookup files
```

### meta.yml

YAML file containing deck metadata:

```yaml
name: Atraxa Superfriends
format: commander
```

### commanders.txt

Commander cards in Moxfield line format (1-2 lines for partner commanders):

```
1 Atraxa, Praetors' Voice
```

Partner example:

```
1 Thrasios, Triton Hero
1 Tymna the Weaver
```

### main.txt

Main deck cards, one per line in Moxfield line format:

```
1 Sol Ring #!Ramp #ArtifactSynergy
1 Arcane Signet *F* #!Ramp #ArtifactSynergy
1 Counterspell #TargetedDisruption #Protection
1 Swords to Plowshares #!Removal #TargetedDisruption
1 Command Tower #!Land #Fixing
```

### sideboard.txt / considering.txt

Same line format as main.txt. Used for sideboard cards and cards under consideration.

### tags.md

Optional markdown file holding deck-specific tag definitions. Format is one `## TagName` heading per tag, followed by a freeform description:

```markdown
## WinCon
Cards that close the game in this deck: Aetherflux Reservoir, Exsanguinate, Gray Merchant.

## Drain
Effects where an opponent loses life and you gain it.
```

Picked up by `scryfall.py batch --suggest-tags --deck <uuid>` to expand the suggestion vocabulary beyond what the active template defines.

### batches/

Workspace directory for temporary batch lookup files. Write card names (one per line) to files here, then use `scryfall.py batch <path>` for bulk lookups.

## Examples

Minimal entry:
```
1 Sol Ring
```

With tags:
```
1 Sol Ring #!Ramp #ArtifactSynergy
```

With set code and collector number:
```
1 Counterspell (CMR) 632
```

With everything:
```
4 Counterspell (CMR) 632 *F* #TargetedDisruption #Protection
```

## Templates

Templates define a deck's tag vocabulary, with optional count targets and descriptions per tag. They are resolved from two locations (user-space first):

1. **User-space**: `~/.mtg/templates/<name>.txt` — personal templates
2. **Bundled**: `assets/<name>.txt` in the skill directory — pre-packaged templates

Example template:

```
// Template: Balanced Commander
// Description: Standard balanced 100-card Commander deck composition

Lands: 38
  Mana-producing lands.

Ramp: 10-15
  Cards that accelerate mana production: rocks, dorks, rituals, cost reducers.

CardAdvantage: 10
  Net-positive card draw or selection.

Plan:
  Strategy cards specific to the deck's win condition. No fixed count.
```

Each entry is `TagName: count`, `TagName: low-high`, or `TagName:` (no count). Tags without counts are part of the vocabulary but skipped by `verify.py`'s count comparison. Indented continuation lines (2+ spaces) following a tag header are the tag's description. Blank lines end the description. Lines starting with `//` are comments. Categories correspond to tag names used in deck files (e.g., `Ramp` matches `#Ramp` or `#!Ramp`).
