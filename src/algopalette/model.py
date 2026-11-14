"""Model danych AlgoPalette (kontrakt z Shared Interfaces; rozszerzany w Task 2)."""

import uuid
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal

Role = Literal["bg", "fg", "accent"]
ContrastMetric = Literal["wcag21", "apca"]
DeltaEMethod = Literal["ok", "2000", "hyab", "itp", "cam16"]
CvdType = Literal["protan", "deutan", "tritan"]
CvdMethod = Literal["brettel", "vienot", "machado"]
FitMethod = Literal["clip", "minde-chroma", "lch-chroma", "oklch-chroma", "raytrace", "scale"]
ChromaMode = Literal["abs", "rel"]  # rel = ułamek max C w sRGB przy (L, H), 0–1


@dataclass(frozen=True)
class OKLCH:
    """Kolor w OKLCH: l 0–1, c ≥ 0, h w stopniach [0, 360)."""

    l: float
    c: float
    h: float


# ---------------------------------------------------------------------------
# Rozszerzenie z Task 2: modele sesji, dziedziczenie warunków, historia.
# ---------------------------------------------------------------------------

MAX_ACCENTS = 14
MIN_ACCENTS = 1
HISTORY_LIMIT = 200

CONDITION_FIELDS: tuple[str, ...] = (
    "hue_range",
    "hue_target",
    "chroma",
    "lightness",
    "contrast_bg",
    "min_distance",
    "cvd_min_distance",
    "extreme",
)


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


@dataclass(frozen=True)
class Interval:
    lo: float | None = None
    hi: float | None = None


@dataclass(frozen=True)
class Cond[T]:
    """Pojedynczy warunek: wartość + włączenie + twardy/miękki + waga (dla miękkich)."""

    value: T
    enabled: bool = True
    hard: bool = True
    weight: float = 1.0


@dataclass(frozen=True)
class HueRange:
    lo: float
    hi: float  # lo > hi = zakres przez 0°


@dataclass(frozen=True)
class HueTarget:
    target: float
    tol: float


@dataclass(frozen=True)
class ChromaRange:
    mode: ChromaMode
    lo: float | None
    hi: float | None


@dataclass(frozen=True)
class ContrastBound:
    metric: ContrastMetric | None  # None = metryka globalna
    lo: float | None
    hi: float | None


@dataclass(frozen=True)
class SlotConditions:
    """Warunki slotu. Pole ``None`` = dziedzicz z ustawień globalnych."""

    hue_range: Cond[HueRange] | None = None
    hue_target: Cond[HueTarget] | None = None
    chroma: Cond[ChromaRange] | None = None
    lightness: Cond[Interval] | None = None
    contrast_bg: Cond[ContrastBound] | None = None
    min_distance: Cond[float] | None = None  # ΔE do każdego innego akcentu
    cvd_min_distance: Cond[float] | None = None
    extreme: Cond[Literal["weakest", "strongest"]] | None = None


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
    conditions: SlotConditions = SlotConditions()
    relations: tuple[Relation, ...] = ()


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
    # Budżet w ewaluacjach funkcji celu na jedną propozycję (nie czas). Wartość startowa; Task 4
    # (engine) dostroi ją po pomiarach jakości/czasu.
    max_evals: int = 8_000  # pomiar 2026-11-14: ~3.8 s / 6 propozycji dla najwolniejszych nastrojów
    time_cap_s: float = 30.0  # tylko bezpiecznik (timed_out); budżet to max_evals
    min_diversity: float = 0.05
    hard_weight: float = 1000.0


@dataclass(frozen=True)
class GlobalSettings:
    polarity: Literal["dark", "light"]
    role_defaults: Mapping[Role, SlotConditions]  # pełne dla bg/fg/accent
    hue_scheme: HueScheme
    lightness_spread: Cond[Interval] | None  # max L − min L akcentów
    contrast_metric: ContrastMetric
    delta_e: DeltaEMethod
    cvd: CvdSettings
    fit_method: FitMethod
    avoid_colors: tuple[OKLCH, ...] = ()
    avoid_distance: float = 0.0
    optimizer: OptimizerSettings = OptimizerSettings()

    def __post_init__(self) -> None:
        if not isinstance(self.role_defaults, FrozenMap):
            object.__setattr__(self, "role_defaults", FrozenMap(self.role_defaults))


@dataclass(frozen=True)
class Session:
    globals: GlobalSettings
    slots: tuple[Slot, ...]
    mood: str | None = None
    mood_snapshot: Mapping[str, Any] | None = None  # wartości ustawione przez nastrój

    def __post_init__(self) -> None:
        if self.mood_snapshot is not None and not isinstance(self.mood_snapshot, FrozenMap):
            object.__setattr__(self, "mood_snapshot", FrozenMap(self.mood_snapshot))
        if not isinstance(self.slots, tuple):
            object.__setattr__(self, "slots", tuple(self.slots))


def role_of(index: int) -> Role:
    """Rola strukturalna slotu o danym indeksie: 0 = tło, 1 = tekst, ≥ 2 = akcent."""
    if index < 0:
        raise ValueError("Indeks slotu nie może być ujemny")
    return ("bg", "fg")[index] if index < 2 else "accent"  # type: ignore[return-value]


def new_slot_id() -> str:
    return uuid.uuid4().hex[:8]


def default_role_defaults(
    polarity: Literal["dark", "light"] = "dark",
    contrast_metric: ContrastMetric = "wcag21",
) -> Mapping[Role, SlotConditions]:
    """Domyślne warunki wg roli strukturalnej dla polaryzacji i metryki kontrastu.

    Liczby kontrastu zależą od metryki (WCAG ratio vs |Lc|), dlatego ``metric`` w ``ContrastBound``
    zostaje ``None`` (globalna), a wartość dobieramy tu. Zmiana metryki globalnej w TUI powinna
    wołać tę funkcję ponownie.
    """
    wcag = contrast_metric == "wcag21"
    fg_contrast = 7.0 if wcag else 75.0
    accent_contrast = 4.5 if wcag else 60.0
    dark = polarity == "dark"
    bg_l = Interval(0.10, 0.25) if dark else Interval(0.93, 0.99)
    fg_l = Interval(0.85, 0.98) if dark else Interval(0.15, 0.30)
    accent_l = Interval(0.60, 0.85) if dark else Interval(0.35, 0.60)
    tint = Cond(ChromaRange("abs", 0.0, 0.04))
    return FrozenMap(
        {
            "bg": SlotConditions(lightness=Cond(bg_l), chroma=tint),
            "fg": SlotConditions(
                lightness=Cond(fg_l),
                chroma=tint,
                contrast_bg=Cond(ContrastBound(None, fg_contrast, None)),
            ),
            "accent": SlotConditions(
                lightness=Cond(accent_l),
                chroma=Cond(ChromaRange("abs", 0.06, 0.20)),
                contrast_bg=Cond(ContrastBound(None, accent_contrast, None)),
                min_distance=Cond(0.08, hard=False),  # ΔE „ok” (skala 0–1)
                cvd_min_distance=Cond(0.04, hard=False),
            ),
        }
    )


def _starting_accent(index: int) -> OKLCH:
    """Plausibilny kolor startowy n-tego akcentu (0-based): odcienie co 45°, L na przemian."""
    return OKLCH(0.78 if index % 2 == 0 else 0.72, 0.12, (25.0 + 45.0 * index) % 360.0)


def default_session() -> Session:
    """Sesja startowa: ciemna, tło + tekst + 8 akcentów, układ odcieni „equal”, bez nastroju."""
    g = GlobalSettings(
        polarity="dark",
        role_defaults=default_role_defaults("dark", "wcag21"),
        hue_scheme=HueScheme(kind="equal"),
        lightness_spread=None,
        contrast_metric="wcag21",
        delta_e="ok",
        cvd=CvdSettings(),
        fit_method="oklch-chroma",
    )
    slots = [
        Slot(id=new_slot_id(), name="tło", value=OKLCH(0.18, 0.02, 260.0)),
        Slot(id=new_slot_id(), name="tekst", value=OKLCH(0.92, 0.01, 260.0)),
        *(Slot(id=new_slot_id(), value=_starting_accent(i)) for i in range(8)),
    ]
    return Session(globals=g, slots=tuple(slots), mood=None, mood_snapshot=None)


def snapshot_key(role: Role, field: str) -> str:
    """Klucz w ``mood_snapshot`` dla pola warunków roli: ``role_defaults.<rola>.<pole>``."""
    return f"role_defaults.{role}.{field}"


def slot_index(session: Session, slot_id: str) -> int:
    for i, s in enumerate(session.slots):
        if s.id == slot_id:
            return i
    raise ValueError(f"Nieznany slot: {slot_id}")


def effective_conditions(
    session: Session, slot_id: str
) -> tuple[SlotConditions, Mapping[str, Literal["mood", "global", "slot"]]]:
    """Warunki obowiązujące slot (pole po polu: slot > domyślne roli z ustawień globalnych).

    Zwraca ``(warunki, źródła)``; źródła są kluczowane nazwą pola ``SlotConditions``:

    * ``"slot"``   — slot definiuje pole (nie ``None``);
    * ``"mood"``   — pole dziedziczone, a ``session.mood_snapshot`` zawiera pod kluczem
      ``role_defaults.<rola>.<pole>`` (``snapshot_key``; rola ∈ bg/fg/accent) wartość równą
      wartości globalnej (nastrój ustawił ją i użytkownik jej nie zmienił);
    * ``"global"`` — pozostałe przypadki.
    """
    slot = session.slots[slot_index(session, slot_id)]
    role = role_of(slot_index(session, slot_id))
    base = session.globals.role_defaults[role]
    snapshot = session.mood_snapshot
    merged: dict[str, Any] = {}
    sources: dict[str, Literal["mood", "global", "slot"]] = {}
    for name in CONDITION_FIELDS:
        own = getattr(slot.conditions, name)
        if own is not None:
            merged[name] = own
            sources[name] = "slot"
            continue
        inherited = getattr(base, name)
        merged[name] = inherited
        key = snapshot_key(role, name)
        if snapshot is not None and key in snapshot and snapshot[key] == inherited:
            sources[name] = "mood"
        else:
            sources[name] = "global"
    return SlotConditions(**merged), sources


def broken_relations(session: Session) -> list[tuple[str, int]]:
    """Relacje (slot_id, indeks) z ``target`` albo ``other`` spoza sesji (też mix bez ``other``)."""
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
    """Dodaje akcent na końcu (kolejny odcień startowy). Najwyżej 14 akcentów."""
    n = _accent_count(session)
    if n >= MAX_ACCENTS:
        raise ValueError(f"Najwyżej {MAX_ACCENTS} akcentów")
    used = {s.id for s in session.slots}
    sid = new_slot_id()
    while sid in used:
        sid = new_slot_id()
    slot = Slot(id=sid, value=_starting_accent(n))
    return replace(session, slots=(*session.slots, slot))


def remove_slot(session: Session, slot_id: str) -> Session:
    """Usuwa akcent. Relacje innych slotów do niego zostają (``broken_relations`` je zgłosi)."""
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
