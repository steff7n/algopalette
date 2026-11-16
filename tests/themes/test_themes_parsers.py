"""Parsery źródeł motywów: fixture z wycinków prawdziwych odpowiedzi + przypadki brzegowe."""

import gzip
import io
import json
import tarfile
from pathlib import Path

import pytest

from algopalette.themes import ThemeError
from algopalette.themes.parsers import (
    ANSI_ACCENT_NAMES,
    normalize_hex,
    parse_gogh,
    parse_lospec,
    parse_tinted,
    parse_wt,
)

FIX = Path(__file__).parent.parent / "fixtures" / "themes"


def _tinted_archive(root: str = "schemes-HEAD", extra=()) -> bytes:
    """``.tar.gz`` w pamięci z ``fixtures/themes/tinted/`` pod prefiksem ``<root>/``."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted((FIX / "tinted").rglob("*")):
            if p.is_file():
                tar.add(p, arcname=f"{root}/{p.relative_to(FIX / 'tinted').as_posix()}")
        for member, payload in extra:
            tar.addfile(member, io.BytesIO(payload) if payload is not None else None)
    return buf.getvalue()


def _by_id(parsed):
    return {t.id: t for t in parsed.themes}


# --- normalize_hex -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("#2E3440", "#2e3440"),
        ("2E3440", "#2e3440"),
        ("#FfF", "#ffffff"),
        ("abc", "#aabbcc"),
        (" #000 ", "#000000"),
        ("#12345", None),
        ("#1234567", None),
        ("#ggg", None),
        ("rgb(1,2,3)", None),
        ("", None),
        (None, None),
        (123456, None),
    ],
)
def test_normalize_hex(raw, want):
    assert normalize_hex(raw) == want


# --- base16 / base24 -----------------------------------------------------------------------------


def test_tinted_counts_and_skips():
    r = parse_tinted(_tinted_archive())
    # poprawne: base16 nord, linux-vt, github + base24 0x96f, abyssal; złe: zepsuty, bez-palety,
    # zly-hex, bez-akcentow; README.md i tinted8/ ignorowane bez liczenia
    assert len(r.themes) == 5
    assert r.skipped == 4
    assert sorted(_by_id(r)) == [
        "base16/github",
        "base16/linux-vt",
        "base16/nord",
        "base24/0x96f",
        "base24/abyssal",
    ]


def test_tinted_nord_roles_and_metadata():
    t = _by_id(parse_tinted(_tinted_archive()))["base16/nord"]
    assert t.source == "base16" and t.has_roles
    assert t.name == "Nord" and t.author == "arcticicestudio"
    assert t.url == "https://github.com/tinted-theming/schemes/blob/HEAD/base16/nord.yaml"
    assert t.colors[:3] == ("#2e3440", "#e5e9f0", "#bf616a")  # base00, base05, base08
    assert len(t.colors) == 2 + 8 and len(t.accent_names) == 8
    assert t.accent_names == tuple(f"base0{c}" for c in "89ABCDEF")
    assert all(c == c.lower() and c.startswith("#") and len(c) == 7 for c in t.colors)


def test_tinted_base24_has_14_accents():
    t = _by_id(parse_tinted(_tinted_archive()))["base24/abyssal"]
    assert len(t.colors) == 2 + 14 and len(t.accent_names) == 14
    assert t.accent_names[-6:] == tuple(f"base{n}" for n in range(12, 18))
    assert t.url.endswith("/base24/abyssal.yaml")


def test_tinted_duplicate_accent_removed_with_its_name():
    # 0x96f: base12 == base0F (#ff8787) → 13 akcentów, nazwa „base12” znika razem z kolorem
    t = _by_id(parse_tinted(_tinted_archive()))["base24/0x96f"]
    assert len(t.colors) == 2 + 13 and len(t.accent_names) == 13
    assert "base12" not in t.accent_names and "base0F" in t.accent_names


def test_tinted_unquoted_yaml_and_comments_ok():
    # linux-vt: wartości w cudzysłowie z komentarzem, ``system:`` bez cudzysłowu
    t = _by_id(parse_tinted(_tinted_archive()))["base16/linux-vt"]
    assert t.colors[0] == "#000000" and t.colors[1] == "#aaaaaa"


def test_tinted8_ignored_without_counting():
    only_tinted8 = io.BytesIO()
    with tarfile.open(fileobj=only_tinted8, mode="w:gz") as tar:
        tar.add(
            FIX / "tinted/tinted8/catppuccin-latte.yaml",
            arcname="schemes-HEAD/tinted8/catppuccin-latte.yaml",
        )
    r = parse_tinted(only_tinted8.getvalue())
    assert r.themes == () and r.skipped == 0


def test_tinted_arbitrary_root_name():
    a = parse_tinted(_tinted_archive("schemes-spec-0.11"))
    assert len(a.themes) == 5 and a.skipped == 4


def test_tinted_ignores_non_regular_and_misplaced_members():
    link = tarfile.TarInfo("schemes-HEAD/base16/link.yaml")
    link.type = tarfile.SYMTYPE
    link.linkname = "nord.yaml"
    dirm = tarfile.TarInfo("schemes-HEAD/base16/dir.yaml")
    dirm.type = tarfile.DIRTYPE
    payload = (FIX / "tinted/base16/nord.yaml").read_bytes()
    deep = tarfile.TarInfo("schemes-HEAD/base16/sub/nord.yaml")  # za głęboko
    deep.size = len(payload)
    shallow = tarfile.TarInfo("base16/nord.yaml")  # bez katalogu głównego
    shallow.size = len(payload)
    wrong_ext = tarfile.TarInfo("schemes-HEAD/base16/nord.yml")
    wrong_ext.size = len(payload)
    extra = [(link, None), (dirm, None), (deep, payload), (shallow, payload), (wrong_ext, payload)]
    r = parse_tinted(_tinted_archive(extra=extra))
    assert len(r.themes) == 5 and r.skipped == 4


def test_tinted_oversized_member_skipped():
    big = b"system: base16\nname: x\npalette: {}\n" + b"# " + b"a" * (300 * 1024) + b"\n"
    info = tarfile.TarInfo("schemes-HEAD/base16/olbrzym.yaml")
    info.size = len(big)
    r = parse_tinted(_tinted_archive(extra=[(info, big)]))
    assert len(r.themes) == 5 and r.skipped == 5


def test_tinted_yaml_is_safe_loaded():
    evil = b'palette: !!python/object/apply:os.getcwd []\nname: "x"\n'
    info = tarfile.TarInfo("schemes-HEAD/base16/zlosliwy.yaml")
    info.size = len(evil)
    r = parse_tinted(_tinted_archive(extra=[(info, evil)]))
    assert len(r.themes) == 5 and r.skipped == 5


@pytest.mark.parametrize(
    "data",
    [b"\x00", b"", b"not a tar", gzip.compress(b"to nie jest tar"), _tinted_archive()[:200]],
)
def test_tinted_garbage_raises(data):
    with pytest.raises(ThemeError, match="base16"):
        parse_tinted(data)


# --- Gogh ----------------------------------------------------------------------------------------


def test_gogh_counts_and_skips():
    r = parse_gogh((FIX / "gogh.json").read_bytes())
    # złe: nieczytelny hex, 0 akcentów po deduplikacji, wpis nie-obiekt
    assert [t.id for t in r.themes] == ["0x96f", "1984 Light", "3024", "Krótkie hexy"]
    assert r.skipped == 3


def test_gogh_full_entry_has_12_accents_and_polish_names():
    t = _by_id(parse_gogh((FIX / "gogh.json").read_bytes()))["0x96f"]
    assert t.source == "gogh" and t.has_roles and t.license is None
    assert t.author == "Filip"  # author_name, nie „Filip (https://…)”
    assert t.url == "https://gogh-co.github.io/Gogh/"
    assert t.colors[:3] == ("#262427", "#fcfcfa", "#ff7272")  # background, foreground, color_02
    assert len(t.colors) == 14 and t.accent_names == ANSI_ACCENT_NAMES
    assert t.accent_names[:6] == ("czerwony", "zielony", "żółty", "niebieski", "magenta", "cyjan")
    assert t.accent_names[6] == "jasny czerwony" and t.accent_names[10] == "jasna magenta"


def test_gogh_bright_equal_to_normal_deduped():
    t = _by_id(parse_gogh((FIX / "gogh.json").read_bytes()))["1984 Light"]
    assert len(t.colors) - 2 == 6 and len(t.accent_names) == 6
    assert t.accent_names == ANSI_ACCENT_NAMES[:6]
    assert len(set(t.colors)) == len(t.colors)


def test_gogh_accent_equal_to_bg_or_fg_dropped_with_name():
    t = _by_id(parse_gogh((FIX / "gogh.json").read_bytes()))["3024"]
    assert len(t.colors) == len(set(t.colors)) and len(t.accent_names) == len(t.colors) - 2
    assert t.colors[0] not in t.colors[2:] and t.colors[1] not in t.colors[2:]


def test_gogh_short_hex_normalized():
    t = _by_id(parse_gogh((FIX / "gogh.json").read_bytes()))["Krótkie hexy"]
    assert t.colors[:3] == ("#112233", "#ffffff", "#ff0000")


# --- Windows Terminal ----------------------------------------------------------------------------


def test_wt_bad_hex_skipped_rest_ok():
    r = parse_wt((FIX / "wt.json").read_bytes())
    assert r.skipped == 1
    assert [t.id for t in r.themes] == ["3024 Day", "Blazer", "Adventure", "Bez meta"]


def test_wt_author_from_credits_and_url():
    by = _by_id(parse_wt((FIX / "wt.json").read_bytes()))
    t = by["3024 Day"]
    assert (
        t.source == "wt" and t.author == "0x3024" and t.url == "https://windowsterminalthemes.dev/"
    )
    assert t.colors[:3] == ("#f7f7f7", "#4a4543", "#db2d20")  # background, foreground, red
    assert by["Blazer"].author == ""  # brak credits
    assert by["Bez meta"].author == ""  # brak meta


def test_wt_dedup_names_follow_colors():
    t = _by_id(parse_wt((FIX / "wt.json").read_bytes()))["3024 Day"]
    # 12 ANSI minus duplikaty (brightGreen == foreground itd.): 11 akcentów
    assert len(t.colors) - 2 == 11 == len(t.accent_names)
    assert len(set(t.colors)) == len(t.colors)
    assert set(t.accent_names) <= set(ANSI_ACCENT_NAMES)


_WT_ACCENT_KEYS = ["red", "green", "yellow", "blue", "purple", "cyan"]
_WT_ACCENT_KEYS += ["bright" + k.capitalize() for k in _WT_ACCENT_KEYS]


def test_wt_black_and_white_not_used():
    entry = {
        "name": "Test",
        "background": "#000001",
        "foreground": "#fffffe",
        "black": "#111111",
        "white": "#eeeeee",
        "brightBlack": "#222222",
        "brightWhite": "#dddddd",
    }
    entry |= {k: f"#0000{i:02x}" for i, k in enumerate(_WT_ACCENT_KEYS, start=10)}
    t = parse_wt(json.dumps([entry]).encode()).themes[0]
    assert len(t.colors) == 14
    assert not {"#111111", "#eeeeee", "#222222", "#dddddd"} & set(t.colors)


# --- Lospec --------------------------------------------------------------------------------------


def test_lospec_total_count_and_roleless_palettes():
    r, total = parse_lospec((FIX / "lospec_page.json").read_bytes())
    assert total == 3171
    # pominięte: 17 kolorów, 2 kolory, nieczytelny kolor
    assert r.skipped == 3
    assert [t.id for t in r.themes] == [
        "pumpkin-parade-16",
        "fade-grub",
        "fall",
        "trees",
        "soft4",
        "krotki-hex",
    ]
    assert all(not t.has_roles and t.accent_names == () and t.source == "lospec" for t in r.themes)


def test_lospec_hex_normalized_and_metadata():
    r, _ = parse_lospec((FIX / "lospec_page.json").read_bytes())
    by = _by_id(r)
    p = by["pumpkin-parade-16"]
    assert p.name == "Pumpkin Parade 16" and p.author == "Hoang Lam"
    assert p.url == "https://lospec.com/palette-list/pumpkin-parade-16"
    assert p.colors[:4] == ("#000000", "#757575", "#9f9f9f", "#ffffff") and len(p.colors) == 16
    assert by["krotki-hex"].colors == ("#000000", "#ffffff", "#ab12cd")
    assert by["krotki-hex"].author == ""  # brak user


def test_lospec_no_dedup_of_colors():
    page = {
        "totalCount": 1,
        "palettes": [{"title": "Dup", "slug": "dup", "colors": ["000000", "000000", "ffffff"]}],
    }
    r, _ = parse_lospec(json.dumps(page).encode())
    assert r.themes[0].colors == ("#000000", "#000000", "#ffffff")


def test_lospec_user_null_ok():
    page = {
        "totalCount": 1,
        "palettes": [{"title": "T", "slug": "t", "colors": ["000", "fff", "f00"], "user": None}],
    }
    r, _ = parse_lospec(json.dumps(page).encode())
    assert r.themes[0].author == ""


# --- śmieci --------------------------------------------------------------------------------------


@pytest.mark.parametrize("parser", [parse_gogh, parse_wt])
@pytest.mark.parametrize(
    "data", [b"not json", b"\x00", b"", b"\xff\xfe", b'{"a": 1}', b'"tekst"', b"null"]
)
def test_json_list_garbage_raises(parser, data):
    with pytest.raises(ThemeError):
        parser(data)


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        b"\x00",
        b"[]",
        b'{"palettes": 1, "totalCount": 3}',
        b'{"palettes": []}',
        b'{"palettes": [], "totalCount": "3"}',
        b'{"palettes": [], "totalCount": true}',
    ],
)
def test_lospec_garbage_raises(data):
    with pytest.raises(ThemeError, match="Lospec"):
        parse_lospec(data)


def test_error_names_the_source():
    with pytest.raises(ThemeError, match="Gogh"):
        parse_gogh(b"not json")
    with pytest.raises(ThemeError, match="Windows Terminal"):
        parse_wt(b"not json")


def test_empty_list_is_valid_not_error():
    assert parse_gogh(b"[]").themes == () and parse_wt(b"[]").skipped == 0
