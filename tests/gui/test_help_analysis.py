"""Pomoc na zakładce Analiza — każdy przełącznik i wykres, w każdym trybie."""

import itertools

from algopalette.gui import help as gh


def test_analysis_covered_each_mode(win, qtbot):
    tab = win.analysis_tab
    assert gh.uncovered(tab) == []  # przed pierwszym rysowaniem też
    win.tabs.setCurrentWidget(tab)
    for m, a in itertools.product(range(tab.matrix_kind.count()), range(tab.axis.count())):
        tab.matrix_kind.setCurrentIndex(m)
        tab.axis.setCurrentIndex(a)
        tab.refresh_from_session()
        rep = gh.uncovered(tab)
        assert rep == [], "\n".join(rep)
        kind = tab.matrix_kind.currentData()
        expected = "analysis.matrix.contrast" if kind == "contrast" else "analysis.matrix.de"
        assert gh.key_of(tab.matrix) == expected
        assert tab.matrix.property(gh.COLUMNS_PROP) == expected
        assert tab.matrix.property(gh.ROWS_PROP) == expected


def test_plots_have_keys(win):
    tab = win.analysis_tab
    assert gh.key_of(tab.wheel) == "analysis.wheel"
    assert gh.key_of(tab.lc) == "analysis.lc"
    assert gh.key_of(tab.samples) == "analysis.samples"
