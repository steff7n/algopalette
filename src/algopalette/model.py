"""Model danych AlgoPalette (v2): sesja, kolory i ich zasady.

Każdy kolor ma komplet własnych zasad (``Slot.rules``); pole ``None`` znaczy „tej zasady nie ma”.
Nie ma dziedziczenia ani wartości wspólnych dla roli — domyślne zasady ról nadaje preset.
"""

import uuid
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import Literal

Role = Literal["bg", "fg", "accent"]
ContrastMetric = Literal["wcag21", "apca"]
DeltaEMethod = Literal["ok", "2000", "hyab", "itp", "cam16"]
CvdType = Literal["protan", "deutan", "tritan"]
CvdMethod = Literal["brettel", "vienot", "machado"]
FitMethod = Literal["clip", "minde-chroma", "lch-chroma", "oklch-chroma", "raytrace", "scale"]
ViewModel = Literal["oklch", "hsl"]
ChromaMode = Literal["abs", "rel"]  # rel = część największego C w sRGB przy (L, H), 0–1
Polarity = Literal["dark", "light"]
# Kłódka zasad (chroni zasady koloru przed presetem): "off"; "rules" — zasady zostają, odcień
# dalej z układu odcieni palety; "hue" — jak "rules", a cel układu zamrożony w zasadzie odcienia.
RulesLock = Literal["off", "rules", "hue"]


@dataclass(frozen=True)
class OKLCH:
    """Kolor w OKLCH: l 0–1, c ≥ 0, h w stopniach [0, 360)."""

    l: float
    c: float
    h: float


MAX_ACCENTS = 14
MIN_ACCENTS = 1
HISTORY_LIMIT = 200

RULE_FIELDS: tuple[str, ...] = (
    "lightness",
    "chroma",
    "hue",
    "contrast_bg",
    "min_distance",
    "cvd_min_distance",
    "extreme",
)
ACCENT_ONLY_FIELDS = frozenset({"min_distance", "cvd_min_distance", "extreme"})


class FrozenMap[K, V](Mapping[K, V]):
    """Niezmienne, hashowalne odwzorowanie (równość i hash jak dla zbioru par).

    Równa się każdemu ``Mapping`` o tych samych parach, więc ``FrozenMap(d) == d``. Wartości muszą
    być hashowalne, jeśli ktoś woła ``hash``.
    """

    __slots__ = ("_d",)

    def __init__(self, data: Mapping[K, V] | Iterable[tuple[K, V]] = ()) -> None:
        self._d: dict[K, V] = dict(data)

    def __getitem__(self, key: K) -> V:
        return self._d[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    def __hash__(self) -> int:
        return hash(frozenset(self._d.items()))

    def __repr__(self) -> str:
        return f"FrozenMap({self._d!r})"


# Zakazane przedziały: pary (od, do). Dla odcienia para może zawijać się przez 0° (od > do).
Exclusions = tuple[tuple[float, float], ...]


def _exclusions(raw: Iterable[Iterable[float]]) -> Exclusions:
    out: list[tuple[float, float]] = []
    for pair in raw:
        lo, hi = pair
        out.append((float(lo), float(hi)))
    return tuple(out)


@dataclass(frozen=True)
class Interval:
    """Przedział bez zakazów (rozrzut jasności akcentów)."""

    lo: float | None = None
    hi: float | None = None


@dataclass(frozen=True)
class Rule[T]:
    """Jedna zasada: wartość + włączenie + twarda/miękka + waga (dla miękkich)."""

    value: T
    enabled: bool = True
    hard: bool = True
    weight: float = 1.0


@dataclass(frozen=True)
class Band:
    """Dozwolony zakres jasności z zakazanymi przedziałami."""

    lo: float | None = None
    hi: float | None = None
    exclude: Exclusions = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "exclude", _exclusions(self.exclude))


@dataclass(frozen=True)
class ChromaBand:
    """Dozwolony zakres nasycenia (bezwzględnego albo względnego); zakazy w jednostkach trybu."""

    mode: ChromaMode
    lo: float | None
    hi: float | None
    exclude: Exclusions = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "exclude", _exclusions(self.exclude))


@dataclass(frozen=True)
class HueArc:
    """Dozwolony łuk odcienia w stopniach; ``lo > hi`` = przez 0°, ``0, 360`` = pełne koło."""

    lo: float
    hi: float
    exclude: Exclusions = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "exclude", _exclusions(self.exclude))


@dataclass(frozen=True)
class ContrastBound:
    metric: ContrastMetric | None  # None = metryka z ustawień palety
    lo: float | None
    hi: float | None


@dataclass(frozen=True)
class SlotRules:
    """Zasady jednego koloru. Pole ``None`` = tej zasady nie ma."""

    lightness: Rule[Band] | None = None
    chroma: Rule[ChromaBand] | None = None
    hue: Rule[HueArc] | None = None
    contrast_bg: Rule[ContrastBound] | None = None
    min_distance: Rule[float] | None = None  # ΔE do każdego innego akcentu
    cvd_min_distance: Rule[float] | None = None
    extreme: Rule[Literal["weakest", "strongest"]] | None = None


RelKind = Literal["hue", "lightness", "chroma", "contrast", "distance", "mix"]
RelOp = Literal["eq", "ge", "le"]


@dataclass(frozen=True)
class Relation:
    kind: RelKind
    target: str
    op: RelOp
    value: float
    tol: float = 0.0
    chroma_op: Literal["add", "mul"] = "add"
    chroma_mode: ChromaMode = "abs"
    metric: ContrastMetric | DeltaEMethod | None = None
    other: str | None = None  # tylko mix: self ≈ mix(target, other, t) w OKLab
    t: float = 0.5
    enabled: bool = True
    hard: bool = True
    weight: float = 1.0


@dataclass(frozen=True)
class Slot:
    id: str
    name: str = ""
    locked: bool = False
    value: OKLCH = OKLCH(0.5, 0.0, 0.0)
    rules: SlotRules = SlotRules()
    use_scheme: bool = True  # tylko akcenty: czy kolor dostaje cel z układu odcieni
    relations: tuple[Relation, ...] = ()
    rules_lock: RulesLock = "off"


@dataclass(frozen=True)
class HueScheme:
    kind: Literal[
        "equal", "analogous", "complementary", "split", "triad", "tetrad", "custom", "none"
    ]
    rotation: float = 0.0
    center: float = 0.0
    spread: float = 90.0
    custom: tuple[float, ...] = ()
    tol: float = 15.0
    jitter: float = 0.0
    hard: bool = False
    weight: float = 1.0


@dataclass(frozen=True)
class CvdSettings:
    types: frozenset[CvdType] = frozenset()
    method: CvdMethod = "machado"
    severity: float = 1.0


@dataclass(frozen=True)
class OptimizerSettings:
    n_proposals: int = 6
    seed: int = 0
    # Największa liczba ocen funkcji celu z gradientem na jeden przebieg (jednego kandydata).
    budget: int = 3_000
    time_cap_s: float = 30.0  # tylko bezpiecznik (timed_out); pracę ogranicza budżet
    min_diversity: float = 0.05
    hard_weight: float = 1000.0
    threads: int = 0  # 0 = wszystkie rdzenie


@dataclass(frozen=True)
class GlobalSettings:
    polarity: Polarity
    hue_scheme: HueScheme
    lightness_spread: Rule[Interval] | None  # max L − min L akcentów
    contrast_metric: ContrastMetric
    delta_e: DeltaEMethod
    cvd: CvdSettings
    fit_method: FitMethod
    avoid_colors: tuple[OKLCH, ...] = ()
    avoid_distance: float = 0.0
    optimizer: OptimizerSettings = OptimizerSettings()

    def __post_init__(self) -> None:
        if not isinstance(self.avoid_colors, tuple):
            object.__setattr__(self, "avoid_colors", tuple(self.avoid_colors))


@dataclass(frozen=True)
class Session:
    globals: GlobalSettings
    slots: tuple[Slot, ...]
    preset: str | None = None  # nazwa ostatnio nałożonego presetu (zasady mogły się potem zmienić)
    view_model: ViewModel = "oklch"  # tylko pokazywanie/edycja wartości koloru

    def __post_init__(self) -> None:
        if not isinstance(self.slots, tuple):
            object.__setattr__(self, "slots", tuple(self.slots))


def role_of(index: int) -> Role:
    """Rola strukturalna slotu o danym indeksie: 0 = tło, 1 = tekst, ≥ 2 = akcent."""
    if index < 0:
        raise ValueError("Indeks slotu nie może być ujemny")
    return ("bg", "fg")[index] if index < 2 else "accent"  # type: ignore[return-value]


def new_slot_id() -> str:
    return uuid.uuid4().hex[:8]


def rule_fields_for(role: Role) -> tuple[str, ...]:
    """Zasady dotyczące roli: tło nie ma kontrastu z tłem; trzy ostatnie tylko dla akcentów."""
    if role == "accent":
        return RULE_FIELDS
    out = tuple(f for f in RULE_FIELDS if f not in ACCENT_ONLY_FIELDS)
    return tuple(f for f in out if f != "contrast_bg") if role == "bg" else out


def default_rules(
    role: Role, polarity: Polarity = "dark", contrast_metric: ContrastMetric = "wcag21"
) -> SlotRules:
    """Zasady presetu „neutralny” dla roli, polaryzacji i metryki kontrastu.

    Progi kontrastu zależą od metryki (stosunek WCAG albo |Lc| APCA), dlatego ``metric`` w
    ``ContrastBound`` zostaje ``None`` (metryka palety), a liczba jest dobierana tutaj.
    """
    wcag = contrast_metric == "wcag21"
    dark = polarity == "dark"
    tint = Rule(ChromaBand("abs", 0.0, 0.04))
    if role == "bg":
        return SlotRules(
            lightness=Rule(Band(0.10, 0.25) if dark else Band(0.93, 0.99)), chroma=tint
        )
    if role == "fg":
        return SlotRules(
            lightness=Rule(Band(0.85, 0.98) if dark else Band(0.15, 0.30)),
            chroma=tint,
            contrast_bg=Rule(ContrastBound(None, 7.0 if wcag else 75.0, None)),
        )
    return SlotRules(
        lightness=Rule(Band(0.60, 0.85) if dark else Band(0.35, 0.60)),
        chroma=Rule(ChromaBand("abs", 0.06, 0.20)),
        contrast_bg=Rule(ContrastBound(None, 4.5 if wcag else 60.0, None)),
        min_distance=Rule(0.08, hard=False),  # ΔE „ok” (skala 0–1)
        cvd_min_distance=Rule(0.04, hard=False),
    )


def _starting_accent(index: int) -> OKLCH:
    """Kolor startowy n-tego akcentu (0-based): odcienie co 45°, L na przemian."""
    return OKLCH(0.78 if index % 2 == 0 else 0.72, 0.12, (25.0 + 45.0 * index) % 360.0)


def default_session() -> Session:
    """Sesja startowa: ciemna, tło + tekst + 8 akcentów, preset „neutralny”."""
    g = GlobalSettings(
        polarity="dark",
        hue_scheme=HueScheme(kind="equal"),
        lightness_spread=None,
        contrast_metric="wcag21",
        delta_e="ok",
        cvd=CvdSettings(),
        fit_method="oklch-chroma",
    )
    accent = default_rules("accent", "dark", "wcag21")
    slots = [
        Slot(
            id=new_slot_id(),
            name="tło",
            value=OKLCH(0.18, 0.02, 260.0),
            rules=default_rules("bg", "dark", "wcag21"),
        ),
        Slot(
            id=new_slot_id(),
            name="tekst",
            value=OKLCH(0.92, 0.01, 260.0),
            rules=default_rules("fg", "dark", "wcag21"),
        ),
        *(Slot(id=new_slot_id(), value=_starting_accent(i), rules=accent) for i in range(8)),
    ]
    return Session(globals=g, slots=tuple(slots), preset="neutralny")


def slot_index(session: Session, slot_id: str) -> int:
    for i, s in enumerate(session.slots):
        if s.id == slot_id:
            return i
    raise ValueError(f"Nieznany slot: {slot_id}")


# ---------------------------------------------------------------------------
# Łuki odcienia (stopnie; łuk biegnie od ``lo`` do ``hi`` w stronę rosnących kątów)
# ---------------------------------------------------------------------------


def arc_width(lo: float, hi: float) -> float:
    """Szerokość łuku ``lo → hi`` w stopniach; ``lo ≠ hi`` o tej samej pozycji to pełne koło."""
    width = (hi - lo) % 360.0
    if width == 0.0 and lo != hi:
        return 360.0
    return width


def arc_from_center(center: float, half: float) -> tuple[float, float]:
    """Łuk ``środek ± połowa szerokości``; połowa ≥ 180° to pełne koło ``(0, 360)``."""
    if half >= 180.0:
        return 0.0, 360.0
    return (center - half) % 360.0, (center + half) % 360.0


def arc_center_half(lo: float, hi: float) -> tuple[float, float]:
    """Środek i połowa szerokości łuku (odwrotność ``arc_from_center``)."""
    half = arc_width(lo, hi) / 2.0
    return (lo + half) % 360.0, half


def arc_intersection(a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
    """Część wspólna dwóch łuków: 0, 1 albo 2 łuki, w kolejności wzdłuż ``a``.

    Samo zetknięcie końcami nie jest częścią wspólną; łuk o zerowej szerokości (jeden odcień)
    leżący wewnątrz drugiego łuku — jest.
    """
    wa, wb = arc_width(*a), arc_width(*b)
    if wa == 360.0:
        return [(float(b[0]), float(b[1]))]
    if wb == 360.0:
        return [(float(a[0]), float(a[1]))]
    start = a[0] % 360.0
    offset = (b[0] - start) % 360.0  # początek b liczony od początku a
    parts: list[tuple[float, float]] = []
    for shift in (-360.0, 0.0):
        lo = max(0.0, offset + shift)
        hi = min(wa, offset + shift + wb)
        if lo < hi or (lo == hi and (wa == 0.0 or wb == 0.0)):
            parts.append((lo, hi))
    return [((start + lo) % 360.0, (start + hi) % 360.0) for lo, hi in sorted(parts)]


def broken_relations(session: Session) -> list[tuple[str, int]]:
    """Zależności (slot_id, indeks) z celem albo ``other`` spoza sesji (też mix bez ``other``)."""
    ids = {s.id for s in session.slots}
    broken: list[tuple[str, int]] = []
    for slot in session.slots:
        for i, rel in enumerate(slot.relations):
            bad = rel.target not in ids
            if rel.kind == "mix":
                bad = bad or rel.other is None or rel.other not in ids
            elif rel.other is not None and rel.other not in ids:
                bad = True
            if bad:
                broken.append((slot.id, i))
    return broken


def with_slot(session: Session, slot: Slot) -> Session:
    """Podmienia slot o tym samym ``id`` (``ValueError``, gdy go nie ma)."""
    i = slot_index(session, slot.id)
    return replace(session, slots=(*session.slots[:i], slot, *session.slots[i + 1 :]))


def _accent_count(session: Session) -> int:
    return max(len(session.slots) - 2, 0)


def add_accent(session: Session) -> Session:
    """Dodaje akcent z zasadami i ``use_scheme`` ostatniego akcentu (bez jego zależności)."""
    n = _accent_count(session)
    if n >= MAX_ACCENTS:
        raise ValueError(f"Najwyżej {MAX_ACCENTS} akcentów")
    used = {s.id for s in session.slots}
    sid = new_slot_id()
    while sid in used:
        sid = new_slot_id()
    last = session.slots[-1]
    slot = Slot(id=sid, value=_starting_accent(n), rules=last.rules, use_scheme=last.use_scheme)
    return replace(session, slots=(*session.slots, slot))


def remove_slot(session: Session, slot_id: str) -> Session:
    """Usuwa akcent. Zależności innych kolorów od niego zostają (``broken_relations`` je zgłosi)."""
    i = slot_index(session, slot_id)
    if i < 2:
        raise ValueError("Nie można usunąć tła ani tekstu")
    if _accent_count(session) <= MIN_ACCENTS:
        raise ValueError("Co najmniej 1 akcent")
    return replace(session, slots=(*session.slots[:i], *session.slots[i + 1 :]))


def move_slot(session: Session, slot_id: str, new_index: int) -> Session:
    """Przesuwa akcent na pozycję ``new_index`` ≥ 2 (tło i tekst mają stałe indeksy 0 i 1)."""
    i = slot_index(session, slot_id)
    if i < 2:
        raise ValueError("Nie można przesunąć tła ani tekstu")
    if not 2 <= new_index < len(session.slots):
        raise ValueError("Pozycja poza zakresem akcentów")
    items = list(session.slots)
    items.insert(new_index, items.pop(i))
    return replace(session, slots=tuple(items))


class History:
    """Undo/redo sesji. ``limit`` = maks. liczba stanów (łącznie z bieżącym); najstarszy znika.

    ``push`` po ``undo`` odcina ogon redo. Stany niezmienne (frozen), więc nie kopiujemy.
    """

    def __init__(self, initial: Session | None = None, limit: int = HISTORY_LIMIT) -> None:
        if limit < 1:
            raise ValueError("Limit historii musi wynosić co najmniej 1")
        self.limit = limit
        self._states: list[Session] = [] if initial is None else [initial]
        self._pos = len(self._states) - 1

    @property
    def current(self) -> Session | None:
        return self._states[self._pos] if self._pos >= 0 else None

    def __len__(self) -> int:
        return len(self._states)

    @property
    def can_undo(self) -> bool:
        return self._pos > 0

    @property
    def can_redo(self) -> bool:
        return self._pos < len(self._states) - 1

    def push(self, s: Session) -> None:
        del self._states[self._pos + 1 :]
        self._states.append(s)
        if len(self._states) > self.limit:
            del self._states[0 : len(self._states) - self.limit]
        self._pos = len(self._states) - 1

    def replace_current(self, s: Session) -> None:
        """Podmienia bieżący stan (scalanie serii drobnych zmian w jeden krok cofania)."""
        if self._pos < 0:
            self.push(s)
            return
        del self._states[self._pos + 1 :]
        self._states[self._pos] = s

    def undo(self) -> Session | None:
        if not self.can_undo:
            return None
        self._pos -= 1
        return self._states[self._pos]

    def redo(self) -> Session | None:
        if not self.can_redo:
            return None
        self._pos += 1
        return self._states[self._pos]
