"""Zmiany ustawień palety, które pociągają przeliczenie progów w zasadach kolorów."""

from dataclasses import replace

from algopalette.model import ContrastMetric, DeltaEMethod, Session
from algopalette.units import rescale_contrast_metric, rescale_delta_e


def change_metric(session: Session, metric: ContrastMetric) -> Session:
    """Nowa metryka kontrastu; progi kontrastu bez własnej metryki przeliczone na jej skalę."""
    old = session.globals.contrast_metric
    if old == metric:
        return session
    s = replace(session, globals=replace(session.globals, contrast_metric=metric))
    return rescale_contrast_metric(s, old, metric)


def change_delta_e(session: Session, method: DeltaEMethod) -> Session:
    """Nowa metoda ΔE z progami odległości przeliczonymi na jej skalę."""
    return rescale_delta_e(session, session.globals.delta_e, method)
