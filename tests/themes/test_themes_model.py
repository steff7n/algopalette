import httpx
import pytest

from algopalette.themes import (
    Theme,
    ThemeError,
    filter_themes,
    fold,
    is_dark,
    resolve,
    theme_from_dict,
    theme_to_dict,
)


def roles(name: str, colors: tuple[str, ...], source="gogh", author="") -> Theme:
    names = tuple(f"a{i}" for i in range(len(colors) - 2))
    return Theme(source, name, name, author, None, colors, names, True)


def lospec(name: str, colors: tuple[str, ...]) -> Theme:
    return Theme("lospec", name, name, "", None, colors, (), False)


def test_resolve_with_roles():
    t = roles("Nord", ("#2e3440", "#e5e9f0", "#bf616a", "#a3be8c", "#ebcb8b"))
    p = resolve(t)
    assert len(p.accents) == 3
    assert p.accent_names == ("a0", "a1", "a2")
    assert p.bg.l < 0.5 < p.fg.l


def test_resolve_lospec_dark_and_light_bg():
    t = lospec("bw", ("#000000", "#ffffff", "#ff0000", "#00ff00"))
    p = resolve(t)
    assert p.bg.l < 0.01 and p.fg.l > 0.99 and len(p.accents) == 2
    q = resolve(t, light_bg=True)
    assert q.bg.l > 0.99 and q.fg.l < 0.01 and len(q.accents) == 2
    assert p.accent_names == ("", "")


def test_resolve_lospec_too_few_after_dedupe():
    with pytest.raises(ThemeError, match="Za mało"):
        resolve(lospec("x", ("#112233", "#112233", "#ffffff")))


def test_resolve_roles_without_accents():
    with pytest.raises(ThemeError):
        resolve(roles("x", ("#000000", "#ffffff")))


def test_is_dark():
    assert is_dark(roles("d", ("#101010", "#eeeeee", "#ff0000"))) is True
    assert is_dark(roles("l", ("#fafafa", "#111111", "#ff0000"))) is False
    assert is_dark(lospec("p", ("#000000", "#ffffff", "#ff0000"))) is None


def test_fold_and_filter():
    assert fold("Żółty ŁOŚ") == "zolty los"
    themes = [
        roles("Żółty", ("#101010", "#eeeeee", "#ff0000")),
        roles("Nord", ("#2e3440", "#e5e9f0", "#bf616a"), source="base16"),
        roles("Day", ("#fafafa", "#111111", "#ff0000"), author="Ąna"),
        lospec("Pal", ("#000000", "#ffffff", "#ff0000")),
    ]
    assert [t.name for t in filter_themes(themes, "zolty", "any")] == ["Żółty"]
    assert [t.name for t in filter_themes(themes, "NORD", "any")] == ["Nord"]
    assert [t.name for t in filter_themes(themes, "ana", "any")] == ["Day"]
    light = [t.name for t in filter_themes(themes, "", "light")]
    assert light == ["Day", "Pal"]
    dark = [t.name for t in filter_themes(themes, "", "dark")]
    assert dark == ["Nord", "Żółty", "Pal"]  # kolejność: źródło, potem nazwa


def test_dict_round_trip():
    t = Theme(
        "base16",
        "base16/nord",
        "Nord",
        "a",
        "https://x",
        ("#000000", "#ffffff", "#ff0000"),
        ("base08",),
        True,
        "MIT",
    )
    assert theme_from_dict(theme_to_dict(t)) == t
    with pytest.raises(ValueError):
        theme_from_dict({"source": "nope"})


def test_network_is_blocked():
    with pytest.raises(RuntimeError, match="zablokowana"):
        httpx.get("https://example.com")
