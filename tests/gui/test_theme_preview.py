import pytest
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QListView, QStyleOptionViewItem

from algopalette import color
from algopalette.gui import theme
from algopalette.gui.theme_preview import (
    PALETTE_ROLE,
    THEME_ROLE,
    SwatchDelegate,
    ThemePreview,
    comment_color,
)
from algopalette.themes.model import Theme, resolve

BASE16 = [
    "#2e3440",
    "#d8dee9",
    "#bf616a",
    "#d08770",
    "#ebcb8b",
    "#a3be8c",
    "#88c0d0",
    "#81a1c1",
    "#b48ead",
    "#5e81ac",
]
NAMES = tuple(f"base0{c}" for c in "89ABCDEF")[: len(BASE16) - 2]


def _theme(colors, names=(), roles=True, source="base16", name="Nord"):
    return Theme(source, name.lower(), name, "", None, tuple(colors), tuple(names), roles)


def _hex(c):
    return color.to_hex(c, "oklch-chroma")


def _b16():
    # base00=tło, base05=tekst, base08..0F = 8 akcentów
    return resolve(_theme(BASE16, NAMES))


def test_base16_roles_follow_canonical_names(qtbot):
    pal = _b16()
    w = ThemePreview()
    qtbot.addWidget(w)
    w.set_palette(pal)
    by_name = dict(zip(pal.accent_names, pal.accents, strict=True))
    roles = w.snippet_colors()
    assert roles["keyword"].name() == _hex(by_name["base0E"])
    assert roles["string"].name() == _hex(by_name["base0B"])
    assert roles["added"].name() == _hex(by_name["base0B"])
    assert roles["removed"].name() == _hex(by_name["base08"])
    assert roles["number"].name() == _hex(by_name["base09"])
    assert roles["type"].name() == _hex(by_name["base0A"])
    assert roles["function"].name() == _hex(by_name["base0D"])


def test_comment_is_fg_bg_oklab_mix(qtbot):
    pal = _b16()
    w = ThemePreview()
    qtbot.addWidget(w)
    w.set_palette(pal)
    mixed = comment_color(pal)
    assert mixed.l == pytest.approx((pal.fg.l + pal.bg.l) / 2, abs=0.02)
    assert w.snippet_colors()["comment"].name() == _hex(mixed)


def test_sequential_accents_without_base16_names(qtbot):
    pal = resolve(_theme(["#101010", "#f0f0f0", "#ff0000", "#00ff00", "#0000ff"], ("", "", "")))
    w = ThemePreview()
    qtbot.addWidget(w)
    w.set_palette(pal)
    roles = w.snippet_colors()
    order = ("keyword", "string", "number", "function", "type", "added", "removed")
    for i, role in enumerate(order):
        assert roles[role].name() == _hex(pal.accents[i % 3])


def test_single_accent_all_code_roles(qtbot):
    pal = resolve(_theme(["#101010", "#f0f0f0", "#ff8800"], ("",)))
    w = ThemePreview()
    qtbot.addWidget(w)
    w.set_palette(pal)
    roles = w.snippet_colors()
    acc = _hex(pal.accents[0])
    assert {r: c.name() for r, c in roles.items() if r != "comment"} == dict.fromkeys(
        ("keyword", "string", "number", "function", "type", "added", "removed"), acc
    )


def test_message_when_none(qtbot):
    w = ThemePreview()
    qtbot.addWidget(w)
    w.resize(400, 300)
    w.set_palette(None, message="Za mało różnych kolorów")
    assert w.message == "Za mało różnych kolorów"
    assert w.accessibleDescription() == "Za mało różnych kolorów"
    assert not w.grab().isNull()
    assert w.snippet_colors() == {}
    w.set_palette(_b16())
    assert w.message == ""


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_background_pixel_independent_of_window_theme(qtbot, qapp, mode):
    pal = _b16()
    w = ThemePreview()
    qtbot.addWidget(w)
    w.resize(460, 320)
    w.set_palette(pal)
    theme.apply(qapp, mode)
    try:
        img = w.grab().toImage()
    finally:
        theme.apply(qapp, "light")
    expected = QColor(_hex(pal.bg))
    for x, y in ((2, 2), (img.width() - 3, 2), (img.width() - 3, img.height() - 3)):
        assert QColor(img.pixel(x, y)) == expected


def test_grab_identical_in_light_and_dark(qtbot, qapp):
    w = ThemePreview()
    qtbot.addWidget(w)
    w.resize(460, 320)
    w.set_palette(_b16())
    theme.apply(qapp, "light")
    a = w.grab().toImage()
    theme.apply(qapp, "dark")
    try:
        b = w.grab().toImage()
    finally:
        theme.apply(qapp, "light")
    assert a == b


def test_size_hint_fits_layout(qtbot):
    w = ThemePreview()
    qtbot.addWidget(w)
    assert w.sizeHint().height() >= w.minimumSizeHint().height() > 100


# --- delegat -------------------------------------------------------------------------------
def _model(*rows):
    m = QStandardItemModel()
    for t, p in rows:
        it = QStandardItem(t.name)
        it.setData(t, THEME_ROLE)
        it.setData(p, PALETTE_ROLE)
        m.appendRow(it)
    return m


def _render(qtbot, model, width=320):
    v = QListView()
    qtbot.addWidget(v)
    d = SwatchDelegate(v)
    v.setItemDelegate(d)
    v.setModel(model)
    v.resize(width, 260)
    v.show()
    return v, d


def test_delegate_size_hint_two_lines(qtbot):
    t = _theme(BASE16, NAMES)
    v, d = _render(qtbot, _model((t, resolve(t))))
    opt = QStyleOptionViewItem()
    opt.initFrom(v)
    sh = d.sizeHint(opt, v.model().index(0, 0))
    assert sh.height() >= 2 * opt.fontMetrics.height() - 4
    assert sh.height() <= 4 * opt.fontMetrics.height()


def test_delegate_paints_swatches_with_and_without_palette(qtbot):
    t = _theme(BASE16, NAMES)
    lospec = _theme(["#111111", "#eeeeee", "#ff0000", "#00ff00"], roles=False, source="lospec")
    v, _ = _render(qtbot, _model((t, resolve(t)), (lospec, None), (t, None)))
    img = v.viewport().grab().toImage()
    assert not img.isNull()
    # pierwszy wiersz: lewy skraj paska próbek = tło motywu (poniżej linii nazwy)
    rect = v.visualRect(v.model().index(0, 0))
    y = rect.bottom() - 8
    assert QColor(img.pixel(rect.left() + 12, y)) == QColor(BASE16[0])
    rect2 = v.visualRect(v.model().index(1, 0))
    assert QColor(img.pixel(rect2.left() + 12, rect2.bottom() - 8)) == QColor("#111111")


def test_delegate_without_theme_falls_back(qtbot):
    m = QStandardItemModel()
    m.appendRow(QStandardItem("zwykły"))
    v, _ = _render(qtbot, m)
    assert not v.viewport().grab().isNull()


def test_delegate_long_name_and_selection(qtbot):
    t = _theme(BASE16, NAMES, name="Bardzo długa nazwa motywu " * 6)
    v, _ = _render(qtbot, _model((t, resolve(t))), width=200)
    v.setCurrentIndex(v.model().index(0, 0))
    assert not v.viewport().grab().isNull()
