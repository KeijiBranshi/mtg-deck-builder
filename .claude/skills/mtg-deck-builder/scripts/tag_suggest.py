"""Heuristic tag suggestions for MTG cards.

Given a card (parsed Scryfall JSON), suggest_tags() returns a list of tag names
that likely apply, based on type-line and oracle-text pattern matching.

Heuristics are tied to canonical tag names (Ramp, CardAdvantage, etc.). When the
active template uses those names, the suggester applies. Tags the template
defines but the suggester doesn't know about (e.g., deck-specific Plan, WinCon,
or custom tags) are skipped -- those require human judgment.

These are SUGGESTIONS, not authority. The agent reviewing them should always
read the oracle text and confirm.
"""

import re


def _oracle(card):
    """Return concatenated oracle text across faces, lowercased."""
    parts = []
    if "oracle_text" in card:
        parts.append(card["oracle_text"])
    for face in card.get("card_faces", []):
        if "oracle_text" in face:
            parts.append(face["oracle_text"])
    return "\n".join(parts).lower()


def _type_line(card):
    return card.get("type_line", "").lower()


def _matches_any(text, patterns):
    return any(re.search(p, text) for p in patterns)


# Each rule: (tag_name, predicate(card) -> bool)
# Predicates use lowercased oracle text and type line.
def _is_land(card):
    return "land" in _type_line(card)


def _is_mana_source(card):
    # Lands that tap for mana, OR non-land cards that have "{T}: Add" abilities.
    ot = _oracle(card)
    return bool(re.search(r"\{t\}.*: add \{", ot)) or (
        _is_land(card) and "add" in ot
    )


def _is_ramp(card):
    ot = _oracle(card)
    tl = _type_line(card)
    if _is_land(card):
        # Lands that add more than one mana (Cabal Coffers, Nykthos)
        if re.search(r"add \{[a-z]\} for each", ot) or "devotion" in ot:
            return True
        return False
    # Mana rocks/dorks/rituals
    if re.search(r"\{t\}.*: add \{", ot):
        return True
    if re.search(r"^add \{", ot, re.MULTILINE):  # ritual-style
        return True
    if re.search(r"costs \{\d+\} less", ot):
        return True
    if re.search(r"search your library for .* land", ot):
        return True
    return False


def _is_card_advantage(card):
    ot = _oracle(card)
    return _matches_any(ot, [
        r"\bdraw [a-z]+ cards?\b",
        r"draws? .* cards?",
        r"\bscry \d",
        r"\bsurveil \d",
        r"return target .* card from .* graveyard to your hand",
        r"return up to .* card .* from your graveyard to (the battlefield|your hand)",
    ])


def _is_tutor(card):
    ot = _oracle(card)
    return "search your library for a card" in ot or bool(
        re.search(r"search your library for .* card", ot)
    )


def _is_tokens(card):
    ot = _oracle(card)
    return "create" in ot and "token" in ot


def _is_targeted_disruption(card):
    ot = _oracle(card)
    return _matches_any(ot, [
        r"destroy target",
        r"exile target",
        r"return target .* to .* owner'?s? hand",
        r"counter target",
        r"target creature gets -\d",
        r"target opponent discards",
        r"target player discards",
        r"each opponent sacrifices",  # mass edict but still disruption
        r"target opponent .* sacrifices",
    ])


def _is_mass_disruption(card):
    ot = _oracle(card)
    return _matches_any(ot, [
        r"destroy all",
        r"exile all",
        r"all creatures get -\d",
        r"each creature .* -\d",
        r"each player .* discards",
        r"each player loses",
        r"each opponent .* discards",
        r"each opponent .* sacrifices",
    ])


def _is_life_gain(card):
    ot = _oracle(card)
    return "you gain" in ot and "life" in ot


def _is_drain(card):
    ot = _oracle(card)
    has_loss = "loses" in ot and "life" in ot
    has_gain = "you gain" in ot and "life" in ot
    return has_loss and has_gain


def _is_sac_outlet(card):
    ot = _oracle(card)
    # Either a repeatable activated ability that sacrifices, or an additional cost.
    return _matches_any(ot, [
        r"sacrifice (a|an|another) (creature|artifact|permanent|enchantment)",
    ])


def _is_death_trigger(card):
    ot = _oracle(card)
    return re.search(r"whenever .* dies", ot) is not None or re.search(
        r"when .* dies", ot
    ) is not None


def _is_protection(card):
    ot = _oracle(card)
    return _matches_any(ot, [
        r"\bhexproof\b",
        r"\bshroud\b",
        r"\bindestructible\b",
        r"\bward\b",
        r"prevent .* damage",
        r"protection from",
    ])


def _is_punish(card):
    ot = _oracle(card)
    # Cards that trigger off opponent actions and impose costs/damage
    return _matches_any(ot, [
        r"whenever an opponent (casts|draws|discards|plays|sacrifices)",
        r"whenever a player (casts|draws|discards)",
    ]) and _matches_any(ot, [r"loses?", r"discards?", r"sacrifices?", r"damage"])


RULES = [
    ("Land", _is_land),
    ("ManaSource", _is_mana_source),
    ("Ramp", _is_ramp),
    ("CardAdvantage", _is_card_advantage),
    ("Tutor", _is_tutor),
    ("Tokens", _is_tokens),
    ("TargetedDisruption", _is_targeted_disruption),
    ("MassDisruption", _is_mass_disruption),
    ("LifeGain", _is_life_gain),
    ("Drain", _is_drain),
    ("SacOutlet", _is_sac_outlet),
    ("DeathTrigger", _is_death_trigger),
    ("Protection", _is_protection),
    ("Punish", _is_punish),
]


def suggest_tags(card, vocabulary=None):
    """Return a sorted list of suggested tag names for a card.

    If `vocabulary` is provided (an iterable of allowed tag names from a
    template), only tags in that set are returned. Otherwise all heuristic
    matches are returned.
    """
    suggestions = []
    for tag, predicate in RULES:
        if vocabulary is not None and tag not in vocabulary:
            continue
        try:
            if predicate(card):
                suggestions.append(tag)
        except Exception:
            continue
    return sorted(suggestions)
