//! Porządek wyniku i zachłanny wybór różnorodnych kandydatów.

use std::cmp::Ordering;

use crate::objective::Objective;

use super::Candidate;

/// Porządek wyniku: bez twardych naruszeń najpierw, potem rosnąco wg `total`, remisy wg numeru
/// przebiegu. `NaN` w `total` (dowolnego znaku) trafia na koniec swojej grupy — samo
/// `total_cmp` stawia −NaN (typowe 0/0 na x86) NA POCZĄTKU (przegląd 2026-11-18 M3).
pub fn rank(a: &Candidate, b: &Candidate) -> Ordering {
    let key = |t: f64| if t.is_nan() { f64::INFINITY } else { t };
    b.score
        .feasible
        .cmp(&a.score.feasible)
        .then_with(|| key(a.score.total).total_cmp(&key(b.score.total)))
        .then_with(|| a.score.total.is_nan().cmp(&b.score.total.is_nan()))
        .then_with(|| a.run.cmp(&b.run))
}

/// Zachłanny wybór z listy posortowanej wg [`rank`]: bierze kandydata, którego odległość do
/// każdego już wybranego wynosi co najmniej `min_diversity`. `prepared[i]` to kandydat `i` w
/// postaci z [`Objective::prepare`]. Zwraca indeksy (rosnąco), najwyżej `n`.
pub fn pick_diverse<O: Objective + ?Sized>(
    obj: &O,
    prepared: &[Vec<f64>],
    n: usize,
    min_diversity: f64,
) -> Vec<usize> {
    let mut picked: Vec<usize> = Vec::with_capacity(n.min(prepared.len()));
    for (i, cand) in prepared.iter().enumerate() {
        if picked.len() >= n {
            break;
        }
        // „za blisko” to `<`: odległość NaN nie dyskwalifikuje kandydata
        let too_close = |&j: &usize| obj.distance_prepared(cand, &prepared[j]) < min_diversity;
        if !picked.iter().any(too_close) {
            picked.push(i);
        }
    }
    picked
}

/// Lista końcowa: wybrani różnorodni (`picked`, indeksy w `sorted`) dopełnieni do `n`
/// najlepszymi pozostałymi z `diverse = false`; całość w porządku [`rank`].
pub fn assemble(sorted: &[Candidate], picked: &[usize], n: usize) -> Vec<Candidate> {
    let mut diverse = vec![false; sorted.len()];
    for &i in picked.iter().take(n) {
        diverse[i] = true;
    }
    let mut fill = n.saturating_sub(picked.len().min(n));
    let mut out = Vec::with_capacity(n.min(sorted.len()));
    for (cand, &is_diverse) in sorted.iter().zip(&diverse) {
        if is_diverse {
            out.push(Candidate { diverse: true, ..cand.clone() });
        } else if fill > 0 {
            fill -= 1;
            out.push(Candidate { diverse: false, ..cand.clone() });
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::objective::Score;
    use crate::optim::testutil::Wells;

    fn cand(x: f64, feasible: bool, total: f64, run: u32) -> Candidate {
        Candidate { x: vec![x, 0.0], score: Score { feasible, total }, run, wave: 1, diverse: true }
    }

    fn points(list: &[Candidate]) -> Vec<Vec<f64>> {
        list.iter().map(|c| c.x.clone()).collect()
    }

    fn runs(list: &[Candidate]) -> Vec<u32> {
        list.iter().map(|c| c.run).collect()
    }

    #[test]
    fn rank_puts_feasible_first_then_total_then_run() {
        let mut list = vec![
            cand(0.0, false, 0.1, 0),
            cand(0.0, true, 5.0, 1),
            cand(0.0, true, 2.0, 2),
            cand(0.0, true, 2.0, 3),
            cand(0.0, false, 0.05, 4),
            cand(0.0, true, f64::NAN, 5),
            cand(0.0, true, -f64::NAN, 7), // −NaN (0/0 na x86) też na koniec grupy
            cand(0.0, true, 0.0, 6),
        ];
        list.reverse();
        list.sort_by(rank);
        assert_eq!(runs(&list), [6, 2, 3, 1, 5, 7, 4, 0]);
    }

    #[test]
    fn pick_skips_candidates_too_close_to_a_chosen_one() {
        let obj = Wells::grid(1);
        // posortowane wg total; odległości liczone po pierwszej współrzędnej
        let sorted = vec![
            cand(0.0, true, 1.0, 0),
            cand(0.04, true, 2.0, 1), // za blisko 0
            cand(0.10, true, 3.0, 2),
            cand(0.12, true, 4.0, 3), // za blisko 2
            cand(0.20, true, 5.0, 4),
            cand(0.30, true, 6.0, 5),
        ];
        assert_eq!(pick_diverse(&obj, &points(&sorted), 6, 0.05), [0, 2, 4, 5]);
        assert_eq!(pick_diverse(&obj, &points(&sorted), 2, 0.05), [0, 2]);
        // próg 0: każdy kandydat jest różny, także duplikaty
        assert_eq!(pick_diverse(&obj, &points(&sorted), 3, 0.0), [0, 1, 2]);
        assert_eq!(pick_diverse(&obj, &points(&sorted), 0, 0.05), Vec::<usize>::new());
        assert_eq!(pick_diverse(&obj, &[], 3, 0.05), Vec::<usize>::new());
    }

    #[test]
    fn distance_exactly_at_threshold_counts_as_diverse() {
        let obj = Wells::grid(1);
        let sorted = vec![cand(0.0, true, 1.0, 0), cand(0.25, true, 2.0, 1)];
        assert_eq!(pick_diverse(&obj, &points(&sorted), 2, 0.25), [0, 1]);
        assert_eq!(pick_diverse(&obj, &points(&sorted), 2, 0.2500001), [0]);
    }

    #[test]
    fn assemble_fills_with_best_remaining_marked_not_diverse() {
        let sorted = vec![
            cand(0.0, true, 1.0, 0),
            cand(0.04, true, 2.0, 1),
            cand(0.10, true, 3.0, 2),
            cand(0.12, true, 4.0, 3),
            cand(0.20, false, 0.5, 4),
        ];
        let out = assemble(&sorted, &[0, 2], 4);
        assert_eq!(runs(&out), [0, 1, 2, 3]);
        assert_eq!(out.iter().map(|c| c.diverse).collect::<Vec<_>>(), [true, false, true, false]);
        // bez dopełniania, gdy wybranych jest dość
        let out = assemble(&sorted, &[0, 2], 2);
        assert_eq!(runs(&out), [0, 2]);
        assert!(out.iter().all(|c| c.diverse));
        // za mało kandydatów: zwraca wszystkich
        let out = assemble(&sorted, &[0], 9);
        assert_eq!(runs(&out), [0, 1, 2, 3, 4]);
        assert_eq!(out.iter().filter(|c| c.diverse).count(), 1);
    }
}
