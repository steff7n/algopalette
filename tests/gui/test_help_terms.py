"""Pomoc: wzorzec terminu („co to jest / przykład z liczbami / kiedy użyć”), pojęcia, rysunek."""

import re

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import QApplication

from algopalette import color
from algopalette.gui import help as gh
from algopalette.gui import help_figures, theme
from algopalette.gui.help_content import GROUPS, TOPICS
from algopalette.model import OKLCH

REQUIRED = {
    "concept.chroma_modes",
    "concept.hard_soft",
    "concept.delta_e",
    "concept.contrast",
    "concept.gamut",
    "concept.exclusion",
    "concept.hue_arc",
}
TERMS = sorted(k for k, t in TOPICS.items() if t.term)
PART = re.compile(r"\*\*(Co to jest|Przykład|Kiedy użyć)[.:]?\*\*")


def parts(body: str) -> dict[str, str]:
    """Części tematu według pogrubionych nagłówków, w kolejności wystąpienia."""
    found = list(PART.finditer(body))
    out: dict[str, str] = {}
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(body)
        out[m.group(1)] = body[m.end() : end].strip()
    return out


def test_required_concepts_follow_the_pattern():
    assert set(TERMS) >= REQUIRED
    assert TOPICS["concept.oklch"].term is False
    assert "concept.sources" not in TOPICS  # dziedziczenia już nie ma
    assert {"Zasady", "Zasady koloru"} <= set(GROUPS)


@pytest.mark.parametrize("key", TERMS)
def test_term_topic_has_three_parts_with_a_number_in_example(key):
    got = parts(TOPICS[key].body)
    assert list(got) == ["Co to jest", "Przykład", "Kiedy użyć"], key
    assert all(len(text.split()) >= 8 for text in got.values()), key
    assert re.search(r"\d", got["Przykład"]), key


def test_chroma_modes_numbers_come_from_the_program():
    body = TOPICS["concept.chroma_modes"].body
    example = parts(body)["Przykład"]
    for hue in (30, 110, 150, 260, 330):
        m = color.max_chroma(0.75, float(hue))
        assert f"{hue}°" in example
        assert f"{m:.3f}" in example  # największe C tego odcienia
        assert f"{round(100 * 0.10 / m)}–{round(100 * 0.15 / m)}%" in example  # 0.10–0.15 bezwzgl.
        assert f"{0.5 * m:.3f}–{0.7 * m:.3f}" in example  # 50–70% względnie


def test_chroma_modes_short_is_two_plain_sentences():
    short = TOPICS["concept.chroma_modes"].short
    assert len(re.findall(r"[.!?](?:\s|$)", short)) == 2
    low = short.casefold()
    assert "ułam" not in low and "osiągaln" not in low
    assert "bezwzględne" in low and "względne" in low
    assert "%" in short or "procent" in low


def test_example_numbers_of_other_concepts_match_the_program():
    a, b = OKLCH(0.70, 0.12, 30.0), OKLCH(0.70, 0.12, 60.0)
    delta = parts(TOPICS["concept.delta_e"].body)["Przykład"]
    for method, fmt in (
        ("ok", ".3f"),
        ("hyab", ".3f"),
        ("2000", ".1f"),
        ("itp", ".1f"),
        ("cam16", ".1f"),
    ):
        assert f"`{method}`" in delta
        assert format(color.delta_e(a, b, method), fmt) in delta
    bg, fg = OKLCH(0.18, 0.02, 260.0), OKLCH(0.92, 0.01, 260.0)
    contrast = parts(TOPICS["concept.contrast"].body)["Przykład"]
    assert f"{color.contrast(fg, bg, 'wcag21'):.2f}" in contrast
    assert f"{color.contrast(fg, bg, 'apca'):.1f}" in contrast
    gamut = parts(TOPICS["concept.gamut"].body)["Przykład"]
    assert f"{color.max_chroma(0.75, 150.0):.3f}" in gamut
    for method in ("oklch-chroma", "lch-chroma", "minde-chroma", "raytrace", "scale", "clip"):
        assert f"`{method}`" in gamut


def _figure(panel: gh.HelpPanel) -> QImage:
    doc = panel.text.document()
    return doc.resource(QTextDocument.ResourceType.ImageResource, QUrl("figure:chroma_modes"))


def test_chroma_figure_renders_in_help_panel_in_both_themes(qtbot):
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    assert "(figure:chroma_modes)" in TOPICS["concept.chroma_modes"].body
    images = {}
    try:
        for mode in ("light", "dark"):
            theme.apply(app, mode)
            panel = gh.HelpPanel()
            qtbot.addWidget(panel)
            panel.show_topic("concept.chroma_modes")
            img = _figure(panel)
            assert isinstance(img, QImage) and not img.isNull()
            assert img.width() >= 300 and img.height() >= 80
            y_abs, y_rel = help_figures.chroma_modes_rows()
            row_abs = [img.pixel(x, y_abs) for x in range(img.width())]
            row_rel = [img.pixel(x, y_rel) for x in range(img.width())]
            assert len(set(row_abs)) >= 12  # dwanaście próbek, nie pusty obraz
            assert row_abs != row_rel  # rzędy różnią się nasyceniem
            images[mode] = img
        assert images["light"] != images["dark"]  # podpisy w kolorze tekstu motywu
    finally:
        theme.apply(app, "light")


def test_figure_follows_theme_change_in_open_panel(qtbot):
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    try:
        theme.apply(app, "light")
        panel = gh.HelpPanel()
        qtbot.addWidget(panel)
        panel.show_topic("concept.chroma_modes")
        light = _figure(panel)
        theme.apply(app, "dark")
        assert _figure(panel) != light
    finally:
        theme.apply(app, "light")


def test_unknown_figure_is_an_error():
    with pytest.raises(KeyError):
        help_figures.render("nie_ma")
