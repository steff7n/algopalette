"""Pomoc zakładki „Zasady”: pełna treść, terminy wg wzorca, brak tematów starego modelu."""

import math
import re
from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from algopalette.forms import DELTA_E, DISPLAY_ORDER, FITS, SCHEMES, default_for
from algopalette.gui import help as gh
from algopalette.gui.help_content import GROUPS, TOPICS
from algopalette.gui.relations import RelationRow
from algopalette.model import (
    ContrastBound,
    HueArc,
    Interval,
    OptimizerSettings,
    Relation,
    Rule,
    SlotRules,
    with_slot,
)
from algopalette.presets_builtin import BUILTIN

TERMS_REQUIRED = {
    "rules.hues.kind",
    "rules.hues.tol",
    "rules.hues.jitter",
    "rules.spread",
    "rules.gen.budget",
    "rules.gen.seed",
    "rules.gen.min_diversity",
    "rules.gen.hard_weight",
    "rules.extreme",
    "rel.hue",
    "rel.lightness",
    "rel.chroma",
    "rel.contrast",
    "rel.distance",
    "rel.mix",
}


def settle(win) -> None:
    win.rules_tab.flush()
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def check(win) -> None:
    settle(win)
    rep = gh.uncovered(win.rules_tab)
    assert rep == [], "\n".join(rep)


def rich_session(win):
    """Akcent 1: wszystkie siedem zasad (kontrast z własną metryką, odcień z zakazem)
    i zależności każdego typu + jedna zerwana."""
    s = win.session
    slot = s.slots[2]
    rules = {f: Rule(default_for(f, s)) for f in DISPLAY_ORDER}
    rules["contrast_bg"] = Rule(ContrastBound("apca", 60.0, None))
    rules["hue"] = Rule(HueArc(0.0, 270.0, exclude=((60.0, 85.0),)))
    a, b = s.slots[3].id, s.slots[4].id
    rels = (
        Relation("hue", a, "eq", 180.0, tol=15.0),
        Relation("lightness", a, "le", -0.1),
        Relation("chroma", a, "ge", 1.0, chroma_op="mul", chroma_mode="rel"),
        Relation("contrast", s.slots[0].id, "ge", 4.5, metric="wcag21"),
        Relation("distance", b, "ge", 0.03, metric="ok"),
        Relation("mix", a, "eq", 0.0, tol=0.02, other=b, t=0.5),
        Relation("hue", "nie-ma-takiego", "eq", 30.0, tol=10.0),  # zerwana
    )
    return with_slot(s, replace(slot, rules=SlotRules(**rules), relations=rels))


# --- pokrycie elementów ----------------------------------------------------------------------


def test_rule_rows_and_relations_of_every_kind_are_covered(win):
    win.set_session(rich_session(win), structural=True)
    win.show_rules([win.session.slots[2].id])
    settle(win)
    tab = win.rules_tab
    assert set(tab.rows) == set(DISPLAY_ORDER)
    for field, row in tab.rows.items():
        assert row.state == "same" and gh.key_of(row) == f"rules.{field}"
    rows = tab.relations.findChildren(RelationRow)
    assert {r.rel.kind for r in rows} == {
        "hue",
        "lightness",
        "chroma",
        "contrast",
        "distance",
        "mix",
    }
    assert any(r.broken for r in rows)
    for r in rows:
        assert gh.key_of(r) == f"rel.{r.rel.kind}"
    check(win)


def test_whole_palette_page_covered_with_and_without_spread(win):
    s = win.session
    for spread in (None, Rule(Interval(0.15, None), hard=False)):
        win.set_session(
            replace(s, globals=replace(s.globals, lightness_spread=spread)), structural=True
        )
        win.show_rules([])
        check(win)


# --- treść -----------------------------------------------------------------------------------


def test_every_rules_topic_has_real_content():
    keys = [k for k in TOPICS if k.startswith(("rules.", "rel."))]
    assert len(keys) >= 60
    for k in keys:
        t = TOPICS[k]
        assert t.group in ("Zasady", "Zasady koloru"), k
        assert len(t.short) >= 30, k
    full = [k for k in keys if k.startswith("rules.") and k != "rules.palette_link"]
    for k in full:
        assert len(TOPICS[k].body) >= 150, k


def test_terms_of_the_panel_follow_the_pattern():
    terms = {k for k, t in TOPICS.items() if t.term}
    assert terms >= TERMS_REQUIRED, sorted(TERMS_REQUIRED - terms)


@pytest.mark.parametrize(
    ("key", "words"),
    [
        ("rules.tab", ["✕ usuń", "komplet własnych zasad"]),
        ("rules.editing", ["różne", "brak zasady", "każdego"]),
        ("rules.rule.mixed", ["ustaw dla zaznaczonych", "usuń u wszystkich", "brak"]),
        ("rules.strip", ["Ctrl+klik", "Shift+klik", "wszystkie akcenty", "Ctrl+A", "spacja"]),
        ("rules.lightness", ["+ zakaz", "zakreskowany"]),
        ("rules.hue", ["od", "środek", "±", "pełne koło", "+ zakaz"]),
        ("rules.scheme_use", ["cel", "własną", "Odznaczony"]),
        ("rules.hues.custom", ["klik w koło", "Alt+↑", "Delete", "przeciąganie"]),
        ("rules.avoid", ["hex", "oklch(", "klik w koło"]),
        ("rules.preset.current", ["(zmieniony)"]),
        ("rules.polarity", ["pyta", "zastąp", "tylko oznaczenie", "anuluj"]),
        ("rules.count", ["kopię zasad", "ostatni akcent", "10 kolorów"]),
        ("rules.gen.threads", ["0", "identyczne"]),
        ("rules.gen.budget", ["na jednego kandydata", "starszych wersjach"]),
        ("rules.gen.time_cap", ["wszystkie", "⏱"]),
        ("rules.generation", ["niezależnie od liczby wątków"]),
    ],
)
def test_topic_explains_what_the_program_does(key, words):
    body = TOPICS[key].body.replace("**", "")
    missing = [w for w in words if w not in body]
    assert missing == [], (key, missing)


def test_option_lists_and_presets_described_in_body():
    def has(key, words):
        body = TOPICS[key].body
        missing = [w for w in words if w not in body]
        assert missing == [], (key, missing)

    has("rules.preset", [p.name for p in BUILTIN] + [p.description for p in BUILTIN])
    has("rules.hues.kind", [label.split(" (")[0] for label, _ in SCHEMES])
    has("rules.delta_e", [f"`{v}`" for _, v in DELTA_E])
    has("rules.fit", [f"`{v}`" for _, v in FITS])


def test_defaults_quoted_in_help_come_from_the_program():
    o = OptimizerSettings()
    assert f"Domyślny budżet to {o.budget}" in TOPICS["rules.gen.budget"].body
    assert f"Domyślnie {o.n_proposals}" in TOPICS["rules.gen.n_proposals"].body
    runs = max(o.n_proposals + 4, math.ceil(1.5 * o.n_proposals))
    assert f"— {runs})" in TOPICS["rules.gen.n_proposals"].body
    assert f"wadze {o.hard_weight:g}" in TOPICS["rules.gen.hard_weight"].body
    assert f"różnorodności {o.min_diversity:g}" in TOPICS["rules.gen.min_diversity"].body


def test_old_model_topics_and_links_are_gone():
    gone = [k for k in TOPICS if k.startswith(("globals.", "cond.")) or k == "concept.sources"]
    assert gone == []
    assert "Globalne" not in GROUPS and "Warunki i zależności" not in GROUPS
    assert "window.tab.globals" not in TOPICS
    for key, topic in TOPICS.items():
        for target in re.findall(r"\(help:([^)\s]+)\)", topic.body):
            assert target in TOPICS, (key, target)
        text = f"{topic.title} {topic.short} {topic.body}".casefold()
        for word in ("globaln", "dziedzic", "nastr"):
            assert word not in text, (key, word)
