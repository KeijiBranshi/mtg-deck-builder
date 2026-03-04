---
name: mtg-deck-builder
description: "Build and manage Magic: The Gathering Commander/EDH deck lists in Moxfield-compatible text format. Use this skill when the user wants to create a new MTG deck, add or remove cards from a deck, tag cards, look up card info, analyze deck composition (mana curve, creature count, color breakdown, etc.), or verify a deck against Commander rules. Triggers on any mention of MTG, Magic the Gathering, Commander, EDH, deck building, or Moxfield deck lists."
---

# MTG Deck Builder

Build Commander/EDH deck lists as Moxfield-compatible text files. Decks are managed under `~/.mtg/decks/<uuid>/` as directory-based projects with YAML metadata.

## Deck Structure

Each deck is a directory containing:

```
~/.mtg/decks/<uuid>/
    meta.yml          Deck metadata (name, format)
    commanders.txt    Commander card(s), 1-2 lines
    main.txt          Main deck cards
    sideboard.txt     Sideboard cards
    considering.txt   Cards under consideration
    primer.md         Deck primer (strategy guide & card rationale)
    batches/          Workspace for batch lookup files
```

## Scripts

All scripts are in this skill's `scripts/` directory. Use full paths when invoking:

```bash
SKILL_DIR="<this skill's base directory>"

# Card lookup (functional data only)
python3 "$SKILL_DIR/scripts/scryfall.py" search "counter spell"   # fuzzy name search
python3 "$SKILL_DIR/scripts/scryfall.py" exact "Counterspell"     # exact name lookup
python3 "$SKILL_DIR/scripts/scryfall.py" batch cards.txt          # bulk lookup from file
python3 "$SKILL_DIR/scripts/scryfall.py" query "t:creature o:draw cmc<=3"  # advanced search

# Deck management
python3 "$SKILL_DIR/scripts/deck.py" create "Deck Name" "Commander Name"
python3 "$SKILL_DIR/scripts/deck.py" list
python3 "$SKILL_DIR/scripts/deck.py" show "<uuid>"
python3 "$SKILL_DIR/scripts/deck.py" path "<uuid>"              # deck directory
python3 "$SKILL_DIR/scripts/deck.py" path "<uuid>" main         # specific file
python3 "$SKILL_DIR/scripts/deck.py" path "<uuid>" commanders   # commanders file
python3 "$SKILL_DIR/scripts/deck.py" path "<uuid>" batches      # batches directory

# Templates
python3 "$SKILL_DIR/scripts/deck.py" template create "Balanced Commander"
python3 "$SKILL_DIR/scripts/deck.py" template list
python3 "$SKILL_DIR/scripts/deck.py" template show "balanced"
python3 "$SKILL_DIR/scripts/deck.py" template path "balanced"
python3 "$SKILL_DIR/scripts/deck.py" template delete "balanced"

# Deck verification
python3 "$SKILL_DIR/scripts/verify.py" check "<uuid>"
python3 "$SKILL_DIR/scripts/verify.py" check "<uuid>" --template "balanced"
```

## Scryfall Query Syntax

The `query` subcommand uses Scryfall's full search syntax:

```bash
python3 "$SKILL_DIR/scripts/scryfall.py" query "t:creature o:draw cmc<=3"
python3 "$SKILL_DIR/scripts/scryfall.py" query "t:instant id:dimir o:counter"
python3 "$SKILL_DIR/scripts/scryfall.py" query "t:land id:gruul"
python3 "$SKILL_DIR/scripts/scryfall.py" query "is:commander id:simic"
```

Common syntax:
- `o:text` — oracle text contains "text"
- `t:type` — type line contains "type"
- `c:color` / `id:color` — color / color identity (w/u/b/r/g)
- `cmc:N`, `cmc>=N`, `cmc<=N` — mana value comparisons
- `is:commander` — legal as commander

Results are returned as a compact table (up to 225 cards across 3 pages).

## Workflow

### Building a New Deck

Building a deck is a collaborative, conversational process. NEVER auto-fill an entire deck list in one shot. The user's preferences, playstyle, and vision drive every card choice. Work through these phases in order:

#### Phase 1: Commander Discovery

1. If the user hasn't specified a commander, help them find one
2. Verify the commander via `scryfall.py exact` — confirm it's a legendary creature legal in Commander
3. Look up the commander's abilities and present them to the user, highlighting the key mechanical themes (e.g. "Smeagol cares about creatures dying and landfall")

#### Phase 2: Deck Vision Interview

Before looking up any cards, understand the user's goals. Ask about these areas across 1-3 rounds of questions (do not dump all questions at once — prioritize and follow up naturally):

- **Win condition / strategy**: "How do you want to win? Combo, combat damage, drain, mill, commander damage?" Probe for specifics beyond the obvious commander synergy.
- **Playstyle**: Aggressive, controlling, midrange, combo, political? How interactive do they want to be?
- **Power level**: Casual, focused, optimized, or competitive (cEDH)? What does their playgroup look like?
- **Budget**: Any budget constraints? Proxy-friendly group?
- **Must-includes / pet cards**: Cards they already own or love that they want in the deck.
- **Cards or strategies to avoid**: Things they find unfun or don't want to play against (e.g., stax, infinite combos, mass land destruction).
- **Themes / flavor**: Any subthemes they care about (tribal, flavor wins, specific set, etc.)?

Adapt questions to context — if the user already expressed strong opinions (e.g., "I want a landfall sacrifice deck"), skip questions they've already answered. If they mention a template, use it as a structural guide but still ask about the Plan category.

#### Phase 3: Plan Category Discussion

The "Plan" slots (strategy cards) are the heart of the deck and the most personal part. Before filling them:

1. Based on the commander's abilities and the user's stated goals, identify 2-3 strategic axes the deck could lean into. Present these to the user with brief explanations and example cards (looked up via Scryfall).
2. Let the user pick which axes to emphasize and in what proportion.
3. Suggest cards for each axis in small batches (5-10 at a time), presenting name, mana cost, and a brief note on why it fits. Let the user approve, reject, or ask for alternatives before continuing.

#### Phase 4: Supporting Categories

After the Plan cards are settled, fill in the supporting categories (Ramp, Card Advantage, Targeted Disruption, Mass Disruption, Lands). For each category:

1. Suggest cards that synergize with the deck's plan where possible (e.g., Sakura-Tribe Elder as ramp that also triggers death-matters).
2. Present suggestions in batches for user approval rather than adding them silently.
3. When a template is in use, mention the target count so the user can gauge completeness.

#### Phase 5: Finalize

1. Run `verify.py check` to confirm legality (100 cards, singleton, color identity, Commander-legal)
2. If a template is in use, run `verify.py check --template` and share the results
3. Present a summary of the final deck composition and ask if the user wants any swaps

#### Phase 6: Primer

After the deck is finalized and verified, write a `primer.md` file in the deck directory. This is a comprehensive strategy guide that documents the deck's design rationale, how it plays, and why each card was included. See [Primer Format](#primer-format) below for the full structure.

The primer should be written **after** Phase 5 completes, using information gathered throughout the entire build process (the interview answers from Phase 2, strategic axes from Phase 3, card choices from Phase 4, and verification results from Phase 5).

#### Creating the Deck Files

Once the user has confirmed a commander and a deck name (can be decided at any point during the interview):

1. Run `deck.py create "<name>" "<commander>"`
2. Get file paths via `deck.py path "<uuid>" main` for adding cards
3. Add cards as they are approved — do not wait until the end to write them all

### Adding Cards

1. Look up the card via `scryfall.py exact "<name>"` (or `search` for fuzzy match, `query` for advanced search)
2. Confirm the card is commander-legal and within the deck's color identity
3. Append a line to the appropriate deck file (usually `main.txt`): `1 <Exact Card Name>` with any tags
4. See `references/moxfield-format.md` for the full line format
5. Update `primer.md` — add the card to the appropriate role table and note its role. If the card changes strategic interactions or win conditions, update those sections too.

### Removing Cards

1. Get the file path via `deck.py path "<uuid>" main`
2. Read the file, find the line containing the card name
3. Remove that line using the Edit tool
4. Update `primer.md` — remove the card from its role table. If it was mentioned in synergies, win conditions, or gameplay sections, update or remove those references. If the card is being cut in favor of another, add it to the "Alternatives Considered" section with the reason it was cut.

### Tagging Cards

- **Global tags** (collection-wide): `#TagName`
- **Local tags** (deck-specific): `#!TagName`
- To add/remove tags, find the card's line in the deck file and edit it
- Tags go at the end of the line, space-separated

Example: `1 Sol Ring #Ramp #!ArtifactSynergy`

### Batch Card Lookup

1. Get the batches directory: `deck.py path "<uuid>" batches`
2. Write card names to a file in that directory (one per line)
3. Run `scryfall.py batch <path-to-file>`
4. Use the output for analysis

### Analyzing the Deck

To answer questions about deck composition (mana curve, creature count, color distribution, etc.):

1. Extract card names from the deck files (strip quantity/tags)
2. Write the names to a temp file (one per line)
3. Run `scryfall.py batch <tempfile>`
4. Compute stats from the batch output

### Verifying a Deck

Run the verifier to check Commander rules compliance:

```bash
python3 "$SKILL_DIR/scripts/verify.py" check "<uuid>"
```

This checks:
- **Card count**: Must be exactly 100 (commanders + main)
- **Singleton rule**: No duplicates except basic lands
- **Commander legality**: All cards legal in Commander format (via Scryfall)
- **Color identity**: All cards within commander's color identity (via Scryfall)

To also compare against a template:

```bash
python3 "$SKILL_DIR/scripts/verify.py" check "<uuid>" --template "balanced"
```

### Using Templates

Templates define target card counts per category for deck composition. Templates are resolved from two locations (user-space takes priority):

1. **User-space** (`~/.mtg/templates/`) — personal templates created via `deck.py template create`
2. **Bundled** (`assets/` in this skill's directory) — pre-packaged templates shipped with the skill

#### Bundled Templates

- **command-zone-template** — Based on the Command Zone's deck building methodology (10 Ramp, 12 CardAdvantage, 12 TargetedDisruption, 6 MassDisruption, 38 Lands, 30 Plan)

#### Creating Custom Templates

1. Create a template: `deck.py template create "Balanced Commander"`
2. Get its path: `deck.py template path "balanced"`
3. Edit the template file to add category targets:
   ```
   // Template: Balanced Commander
   // Description: Standard balanced 100-card Commander deck
   Lands: 38
   Ramp: 10-15
   Card Draw: 10
   Board Wipes: 3-5
   Targeted Removal: 8-10
   Creatures: 25-30
   ```
4. Tag categories correspond to tags in deck files (e.g., `Ramp` matches `#Ramp` or `#!Ramp`)
5. Use `verify.py check "<uuid>" --template "balanced"` to compare

A user-space template with the same name as a bundled template will take priority. Bundled templates cannot be deleted via `deck.py template delete`.

## Primer Format

The `primer.md` file is a strategy guide written for someone picking up the deck for the first time. It should be detailed, opinionated, and explain *why* cards are in the deck — not just list them. Write it in a confident, analytical tone.

### Required Sections

#### 1. Deck Identity
A header block with:
- **Commander:** Full name and stats (cost, power/toughness)
- **Color Identity:** e.g., Mono-White, Dimir, Temur
- **Strategy:** One-line deck archetype (e.g., "Group Hug/Slug hybrid with Pillow Fort and ETB value")
- **Power Level:** Casual / Focused / Optimized / Competitive (with numeric 1-10 if discussed)

Then a paragraph explaining the commander's key ability and how the deck exploits it. Highlight any non-obvious mechanical interactions (e.g., "each turn" meaning each player's turn in multiplayer).

#### 2. Design Constraints
Summarize the user's requirements from the Phase 2 interview:
- Required/excluded cards
- Strategy and playstyle preferences
- Power level and budget constraints
- Any restrictions (no stax, no infinites, etc.)

#### 3. Strategic Axes
The 2-3 strategic axes identified in Phase 3. For each axis:
- A heading and one-sentence description of the axis
- **Key cards:** List each card with a bold name and 1-2 sentence explanation of its role and how it connects to the axis. Focus on interactions, not just restating oracle text.

#### 4. Win Conditions
Numbered list of how the deck actually closes games. Each entry should name specific cards and describe the board state needed to win through that line.

#### 5. Key Synergies & Interactions
Named combo/synergy packages with explanations. For each:
- Bold the card names involved
- Explain what happens when they're combined
- Note any rules interactions that aren't obvious (e.g., ETB doubler stacking, replacement effects)

#### 6. Card-by-Card Roles
Group cards by functional role (matching the deck's tag categories where applicable). Use tables with columns: Card | Role. Write the Role column as a concise explanation of what the card does *in this deck*, not generic card evaluation. Include a count in each category heading.

Categories typically include: Token Doublers, Card Advantage, Ramp, Targeted Removal, Protection, Board Wipes, Lands — but adapt to the deck's actual structure and tags.

For lands, explain the mana base philosophy (e.g., Plains-heavy for specific synergies) and call out notable utility lands.

#### 7. How the Game Plays
Describe the typical game arc in 3 phases:
- **Early Game (Turns 1-3):** What to deploy first, ideal openers, setup priorities
- **Mid Game (Turns 4-6):** When the engine comes online, key sequencing
- **Late Game (Turns 7+):** How you close, what board states you're building toward

Include **Priority plays** for each phase as ordered lists.

#### 8. Alternatives Considered
Three subsections:
- **Cards Cut During Construction:** Table of cards that were evaluated and removed, with the reason and what replaced them
- **Considering Cards Worth Watching:** Table of cards in `considering.txt` with why they're interesting and what they might replace
- **Cards Deliberately Excluded:** Table of cards that were explicitly rejected with the reason (e.g., against deck constraints, off-theme, owner preference)

#### 9. Deck Statistics
Summary counts: nonland cards, land sources (broken down), creatures, enchantments, artifacts, instants/sorceries, planeswalkers. Note any cards that serve dual roles (e.g., MDFCs counted as both land and spell).

### Maintaining the Primer

The primer must stay in sync with the actual deck list. When cards are added, removed, or swapped:
- Update the relevant role table in section 6
- If the card appears in synergy descriptions (section 5), win conditions (section 4), or gameplay (section 7), update those references
- When cutting a card, move it to "Cards Cut" in section 8 with the reason
- When adding a card from the considering list, remove it from "Considering Cards" in section 8
- Update deck statistics in section 9

Do NOT regenerate the entire primer for small changes — edit the affected sections in place.

## Critical Rules

1. **ALWAYS use Scryfall for card data.** NEVER rely on model knowledge for card names, oracle text, mana costs, types, or any card attributes. Run `scryfall.py` before making any claims about a card.
2. **Use exact card names.** Always use the name as returned by Scryfall (correct capitalization, punctuation, split card formatting with `//`).
3. **Commander singleton rule.** Maximum 1 copy of each card except basic lands. 100 cards total including the commander.
4. **Color identity.** All cards must fit within the commander's color identity. Check `Color Identity` from Scryfall output against the commander's.
5. **Deck directory is source of truth.** The deck directory and its files are the canonical deck list. Always read them before making edits.
6. **Commanders in their own file.** Commander cards go in `commanders.txt`, not `main.txt`. Supports partner commanders (up to 2 lines).

## Format Reference

See `references/moxfield-format.md` for the complete Moxfield decklist format specification, including line syntax, tag format, and examples.
