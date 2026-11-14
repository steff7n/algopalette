"""Zakładka „Globalne”: nastroje, polaryzacja, metryki, układ odcieni, daltonizm, gamut,
optymalizator,
domyślne warunki ról (spec §5.4, §5.5)."""

from __future__ import annotations

import secrets
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Collapsible, Input, Select, Static

from algopalette.globals_logic import change_delta_e, change_polarity_or_metric
from algopalette.model import (
    Cond,
    CvdSettings,
    CvdType,
    DeltaEMethod,
    GlobalSettings,
    Interval,
)
from algopalette.moods import apply_mood, delete_user_mood, list_moods, save_user_mood
from algopalette.tui.conditions import ConditionsEditor
from algopalette.tui.widgets import Field, RangeSlider, ValueSlider, parse_finite, source_badge

if TYPE_CHECKING:
    from algopalette.tui.app import AlgoPaletteApp

SCHEMES = [
    ("równo po kole", "equal"),
    ("analogiczny", "analogous"),
    ("dopełniający", "complementary"),
    ("rozszczepiony dopełniający", "split"),
    ("triada", "triad"),
    ("tetrada", "tetrad"),
    ("własna lista", "custom"),
    ("brak (bez celów)", "none"),
]
DELTA_E = [
    ("ok (OKLab, 0–1)", "ok"),
    ("hyab (OKLab)", "hyab"),
    ("2000 (CIE, ~0–100)", "2000"),
    ("itp (ICtCp)", "itp"),
    ("cam16 (CAM16-UCS)", "cam16"),
]
FITS = [(m, m) for m in ("oklch-chroma", "raytrace", "minde-chroma", "lch-chroma", "scale", "clip")]
CVD = [("protanopia", "protan"), ("deuteranopia", "deutan"), ("tritanopia", "tritan")]


def _num(text: str) -> float | None:
    try:
        return parse_finite(text)
    except ValueError:
        return None


class GlobalsTab(VerticalScroll):
    DEFAULT_CSS = """
    GlobalsTab { padding: 0 1; }
    GlobalsTab .section { text-style: bold; color: $accent; margin-top: 1; }
    GlobalsTab Input { width: 14; height: 1; border: none; padding: 0; }
    GlobalsTab Input#custom, GlobalsTab Input#mood-name { width: 40; }
    GlobalsTab Select { width: 40; }
    GlobalsTab Checkbox { height: 1; border: none; padding: 0; width: auto; margin-right: 2; }
    GlobalsTab Horizontal { height: auto; }
    GlobalsTab Horizontal > Static { width: auto; }
    GlobalsTab Horizontal > .field-label { width: 16; color: $text-muted; }
    GlobalsTab Collapsible { margin-top: 1; }
    """

    @property
    def pal_app(self) -> AlgoPaletteApp:
        return cast("AlgoPaletteApp", self.app)

    @property
    def g(self) -> GlobalSettings:
        return self.pal_app.session.globals

    def refresh_from_session(self) -> None:
        """Przebudowa tylko, gdy sesja zmieniła się od ostatniego rysowania (zachowuje fokus)."""
        if self.pal_app.session is not getattr(self, "_shown", None):
            self.refresh(recompose=True)

    def compose(self) -> ComposeResult:
        s = self.pal_app.session
        self._shown = s
        g = s.globals
        moods = list_moods_safe(self)
        yield Static("Nastrój", classes="section")
        yield Static(f"bieżący: {s.mood or '— (własne ustawienia)'}", id="mood-current")
        with Horizontal():
            yield Select(
                [(("★ " if m.builtin else "") + m.name, m.name) for m in moods],
                value=s.mood if s.mood in {m.name for m in moods} else Select.NULL,
                id="mood",
                compact=True,
            )
            yield Button("Zastosuj", id="mood-apply", compact=True)
            yield Button("Usuń własny", id="mood-delete", compact=True)
        with Horizontal():
            yield Input(placeholder="nazwa nowego nastroju", id="mood-name", compact=True)
            yield Button("Zapisz bieżące ustawienia jako nastrój", id="mood-save", compact=True)
        yield Static("Polaryzacja i metryki", classes="section")
        yield Field(
            "polaryzacja",
            Select(
                [("ciemne tło", "dark"), ("jasne tło", "light")],
                value=g.polarity,
                allow_blank=False,
                id="polarity",
                compact=True,
            ),
        )
        yield Field(
            "kontrast",
            Select(
                [("WCAG 2.1 (1–21)", "wcag21"), ("APCA |Lc| (0–108)", "apca")],
                value=g.contrast_metric,
                allow_blank=False,
                id="contrast_metric",
                compact=True,
            ),
        )
        yield Field(
            "ΔE", Select(DELTA_E, value=g.delta_e, allow_blank=False, id="delta_e", compact=True)
        )
        yield Field(
            "gamut (fit)",
            Select(FITS, value=g.fit_method, allow_blank=False, id="fit_method", compact=True),
        )

        h = g.hue_scheme
        yield Static(
            "Układ odcieni (cele dla akcentów bez własnego warunku odcienia)", classes="section"
        )
        yield Field(
            "rodzaj", Select(SCHEMES, value=h.kind, allow_blank=False, id="hs-kind", compact=True)
        )
        yield Field(
            "obrót",
            ValueSlider(
                h.rotation, minimum=0, maximum=360, step=1, fmt=".0f", wrap=True, id="hs-rotation"
            ),
        )
        yield Field(
            "środek",
            ValueSlider(
                h.center, minimum=0, maximum=360, step=1, fmt=".0f", wrap=True, id="hs-center"
            ),
        )
        yield Field(
            "rozpiętość",
            ValueSlider(h.spread, minimum=0, maximum=360, step=1, fmt=".0f", id="hs-spread"),
        )
        yield Field(
            "własne (°)",
            Input(
                ", ".join(f"{x:g}" for x in h.custom),
                id="custom",
                placeholder="np. 30, 200, 120",
                compact=True,
            ),
        )
        yield Field(
            "tolerancja ±°",
            ValueSlider(h.tol, minimum=0, maximum=90, step=1, fmt=".0f", id="hs-tol"),
        )
        yield Field(
            "jitter ±°",
            ValueSlider(h.jitter, minimum=0, maximum=45, step=1, fmt=".0f", id="hs-jitter"),
        )
        with Horizontal():
            yield Static("twardy ", classes="field-label")
            yield Checkbox("", h.hard, id="hs-hard", compact=True)
            yield Static("  waga ")
            yield Input(f"{h.weight:g}", id="hs-weight", compact=True)

        sp = g.lightness_spread
        yield Static("Rozrzut jasności akcentów (max L − min L)", classes="section")
        if sp is None:
            yield Button("+ dodaj warunek rozrzutu", id="spread-add", compact=True)
        else:
            with Horizontal():
                yield Static("wł. ")
                yield Checkbox("", sp.enabled, id="spread-enabled", compact=True)
                yield Static("  twardy ")
                yield Checkbox("", sp.hard, id="spread-hard", compact=True)
                yield Button("✕ usuń", id="spread-del", compact=True)
            yield RangeSlider(
                sp.value.lo,
                sp.value.hi,
                minimum=0,
                maximum=1,
                step=0.01,
                fmt=".2f",
                allow_none=True,
                id="spread",
            )

        c = g.cvd
        yield Static("Daltonizm (symulacja dla warunku odróżnialności)", classes="section")
        with Horizontal():
            for label, kind in CVD:
                yield Checkbox(label, kind in c.types, id=f"cvd-{kind}", compact=True)
        yield Field(
            "metoda",
            Select(
                [("Machado", "machado"), ("Viénot", "vienot"), ("Brettel", "brettel")],
                value=c.method,
                allow_blank=False,
                id="cvd-method",
                compact=True,
            ),
        )
        yield Field(
            "nasilenie",
            ValueSlider(c.severity, minimum=0, maximum=1, step=0.05, fmt=".2f", id="cvd-severity"),
        )

        o = g.optimizer
        yield Static("Optymalizator", classes="section")
        yield Field("propozycje", Input(str(o.n_proposals), id="opt-n_proposals", compact=True))
        with Horizontal():
            yield Static("ziarno", classes="field-label")
            yield Input(str(o.seed), id="opt-seed", compact=True)
            yield Button("🎲 losuj", id="seed-random", compact=True)
        yield Field("budżet (ewaluacje)", Input(str(o.max_evals), id="opt-max_evals", compact=True))
        yield Field("limit czasu s", Input(f"{o.time_cap_s:g}", id="opt-time_cap_s", compact=True))
        yield Field(
            "różnorodność ΔE", Input(f"{o.min_diversity:g}", id="opt-min_diversity", compact=True)
        )
        yield Field(
            "waga twardych", Input(f"{o.hard_weight:g}", id="opt-hard_weight", compact=True)
        )

        yield Static("Unikanie kolorów źródła (tryb „charakter”)", classes="section")
        with Horizontal():
            yield Static(f"{len(g.avoid_colors)} kolorów, min ΔE ok ", classes="field-label")
            yield Input(f"{g.avoid_distance:g}", id="avoid-distance", compact=True)
            yield Button("wyczyść", id="avoid-clear", compact=True)

        yield Static("Domyślne warunki ról (dziedziczone przez sloty)", classes="section")
        for role, title in (("bg", "tło"), ("fg", "tekst"), ("accent", "akcenty")):
            with Collapsible(title=f"{title}  ", collapsed=role != "accent", id=f"role-{role}"):
                yield ConditionsEditor("role", role, id=f"role-editor-{role}")
        yield Static(
            source_badge("mood")
            .append(" = wartość z nastroju; ")
            .append(source_badge("global"))
            .append(" = zmieniona ręcznie")
        )

    # --- zapis ---
    def _set(
        self, *, structural: bool = False, coalesce: str | None = None, **changes: Any
    ) -> None:
        s = self.pal_app.session
        self.pal_app.set_session(
            replace(s, globals=replace(s.globals, **changes)),
            coalesce=coalesce,
            structural=structural,
        )
        self._shown = self.pal_app.session  # własna edycja — widok już ją pokazuje
        if structural:
            self.refresh(recompose=True)

    @on(Select.Changed)
    def _select(self, event: Select.Changed) -> None:
        sid, val = event.select.id, event.value
        if val is Select.NULL or sid in (None, "mood"):
            return
        event.stop()
        g = self.g
        if sid in ("polarity", "contrast_metric"):
            if getattr(g, sid) != val:
                self.pal_app.set_session(
                    change_polarity_or_metric(self.pal_app.session, **{sid: val}), structural=True
                )
                note = (
                    "nastrój nałożony ponownie"
                    if self.pal_app.session.mood
                    else "domyślne zakresy ról (nastrój użytkownika zdjęty)"
                )
                self.notify(f"Przeliczono: {note}; własne progi kontrastu przeliczone.")
                self.refresh(recompose=True)
        elif sid == "delta_e":
            if g.delta_e != val:
                self.pal_app.set_session(
                    change_delta_e(self.pal_app.session, cast(DeltaEMethod, val)), structural=True
                )
                self.notify("Progi odległości przeliczone na skalę nowej metody ΔE.")
                self.refresh(recompose=True)
        elif sid == "fit_method":
            if g.fit_method != val:
                changes: dict[str, Any] = {sid: val}
                self._set(**changes)
        elif sid == "hs-kind":
            if g.hue_scheme.kind != val:
                self._set(hue_scheme=replace(g.hue_scheme, kind=val))
        elif sid == "cvd-method":
            self._set(cvd=replace(g.cvd, method=val))

    @on(ValueSlider.Changed)
    def _slider(self, event: ValueSlider.Changed) -> None:
        sid = event.slider.id or ""
        if event.value is None:
            return
        event.stop()
        g = self.g
        if sid.startswith("hs-"):
            self._set(
                hue_scheme=replace(g.hue_scheme, **{sid[3:]: float(event.value)}),
                coalesce=f"g:{sid}",
            )
        elif sid == "cvd-severity":
            self._set(cvd=replace(g.cvd, severity=float(event.value)), coalesce="g:cvd-severity")

    @on(RangeSlider.Changed, "#spread")
    def _spread(self, event: RangeSlider.Changed) -> None:
        event.stop()
        sp = self.g.lightness_spread
        if sp is not None:
            self._set(
                lightness_spread=replace(sp, value=Interval(event.lo, event.hi)),
                coalesce="g:spread",
            )

    @on(Checkbox.Changed)
    def _switch(self, event: Checkbox.Changed) -> None:
        event.stop()
        g = self.g
        sid = event.checkbox.id
        if sid == "hs-hard" and g.hue_scheme.hard != event.value:
            self._set(hue_scheme=replace(g.hue_scheme, hard=event.value))
        elif sid in ("spread-enabled", "spread-hard") and g.lightness_spread is not None:
            field = "enabled" if sid == "spread-enabled" else "hard"
            if getattr(g.lightness_spread, field) != event.value:
                self._set(lightness_spread=replace(g.lightness_spread, **{field: event.value}))

    @on(Checkbox.Changed)
    def _checkbox(self, event: Checkbox.Changed) -> None:
        event.stop()
        sid = event.checkbox.id or ""
        if not sid.startswith("cvd-"):
            return
        kind = cast(CvdType, sid[4:])
        types = set(self.g.cvd.types)
        (types.add if event.value else types.discard)(kind)
        if frozenset(types) != self.g.cvd.types:
            self._set(cvd=CvdSettings(frozenset(types), self.g.cvd.method, self.g.cvd.severity))

    @on(Input.Submitted)
    @on(Input.Blurred)
    def _input(self, event: Input.Submitted | Input.Blurred) -> None:
        sid = event.input.id or ""
        raw = event.input.value
        g = self.g
        if sid == "custom":
            event.stop()
            vals = [_num(x) for x in raw.replace(";", ",").split(",") if x.strip()]
            if any(v is None for v in vals):
                event.input.add_class("-bad")
                return
            event.input.remove_class("-bad")
            custom = tuple(float(v) % 360 for v in vals if v is not None)
            if custom != g.hue_scheme.custom:
                self._set(hue_scheme=replace(g.hue_scheme, custom=custom))
            return
        if sid == "hs-weight":
            event.stop()
            v = _num(raw)
            if v is not None and v >= 0 and v != g.hue_scheme.weight:
                self._set(hue_scheme=replace(g.hue_scheme, weight=v))
            return
        if sid == "avoid-distance":
            event.stop()
            v = _num(raw)
            if v is not None and v >= 0 and v != g.avoid_distance:
                self._set(avoid_distance=v)
            return
        if sid.startswith("opt-"):
            event.stop()
            field = sid[4:]
            v = _num(raw)
            o = g.optimizer
            ints = {"n_proposals": 1, "seed": 0, "max_evals": 100}  # ziarno ≥ 0 (C3)
            if v is None or (field in ints and v != int(v)):
                event.input.add_class("-bad")
                return
            minimum = ints.get(field, 0.0)
            if minimum is not None and v < minimum:
                event.input.add_class("-bad")
                return
            event.input.remove_class("-bad")
            value: float | int = int(v) if field in ints else v
            if getattr(o, field) != value:
                self._set(optimizer=replace(o, **{field: value}))

    @on(Button.Pressed)
    def _button(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid is None:
            return
        event.stop()
        app = self.pal_app
        g = self.g
        if bid == "mood-apply":
            name = self.query_one("#mood", Select).value
            if name is Select.NULL:
                self.notify("Wybierz nastrój z listy.", severity="warning")
                return
            try:
                app.set_session(apply_mood(app.session, str(name)), structural=True)
            except ValueError as e:
                self.notify(str(e), severity="error")
                return
            self.notify(f"Nastrój „{name}” nałożony na ustawienia globalne.")
            self.refresh(recompose=True)
        elif bid == "mood-save":
            name = self.query_one("#mood-name", Input).value.strip()
            try:
                save_user_mood(name, app.session)
            except (ValueError, OSError) as e:
                self.notify(str(e), severity="error")
                return
            self.notify(f"Zapisano nastrój „{name}”.")
            self.refresh(recompose=True)
        elif bid == "mood-delete":
            name = self.query_one("#mood", Select).value
            try:
                delete_user_mood(str(name))
            except (ValueError, OSError) as e:
                self.notify(str(e), severity="error")
                return
            self.notify(f"Usunięto nastrój „{name}”.")
            self.refresh(recompose=True)
        elif bid == "seed-random":
            self._set(
                optimizer=replace(g.optimizer, seed=secrets.randbelow(2**31)), structural=True
            )
        elif bid == "spread-add":
            self._set(lightness_spread=Cond(Interval(0.15, None), hard=False), structural=True)
        elif bid == "spread-del":
            self._set(lightness_spread=None, structural=True)
        elif bid == "avoid-clear":
            self._set(avoid_colors=(), avoid_distance=0.0, structural=True)


def list_moods_safe(widget: GlobalsTab):
    try:
        return list_moods()
    except ValueError as e:
        widget.notify(str(e), severity="error")
        from algopalette.moods import BUILTIN, Mood

        return [Mood(n, d, True) for n, (d, _) in BUILTIN.items()]
