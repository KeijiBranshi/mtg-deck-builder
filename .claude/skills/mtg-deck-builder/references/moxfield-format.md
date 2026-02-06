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

- **Global tags**: `#TagName` — apply across the user's entire Moxfield collection
- **Local tags**: `#!TagName` — apply only to this specific deck

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
1 Sol Ring #Ramp #!ArtifactSynergy
1 Arcane Signet *F* #Ramp #!ArtifactSynergy
1 Counterspell #!TargetedDisruption #!Protection
1 Swords to Plowshares #Removal #!TargetedDisruption
1 Command Tower #Land #!Fixing
```

### sideboard.txt / considering.txt

Same line format as main.txt. Used for sideboard cards and cards under consideration.

### batches/

Workspace directory for temporary batch lookup files. Write card names (one per line) to files here, then use `scryfall.py batch <path>` for bulk lookups.

## Examples

Minimal entry:
```
1 Sol Ring
```

With tags:
```
1 Sol Ring #Ramp #!ArtifactSynergy
```

With set code and collector number:
```
1 Counterspell (CMR) 632
```

With everything:
```
4 Counterspell (CMR) 632 *F* #!TargetedDisruption #!Protection
```

## Templates

Templates define target card counts per tag category. They are resolved from two locations (user-space first):

1. **User-space**: `~/.mtg/templates/<name>.txt` — personal templates
2. **Bundled**: `assets/<name>.txt` in the skill directory — pre-packaged templates

Example template:

```
// Template: Balanced Commander
// Description: Standard balanced 100-card Commander deck composition
Lands: 38
Ramp: 10-15
Card Draw: 10
Board Wipes: 3-5
Targeted Removal: 8-10
Counterspells: 3-5
Creatures: 25-30
```

Lines are `Category: count` or `Category: min-max`. Categories correspond to tag names used in deck files (e.g., `Ramp` matches `#Ramp` or `#!Ramp`). Lines starting with `//` are comments.
