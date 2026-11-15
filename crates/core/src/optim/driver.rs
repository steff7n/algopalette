//! Sterownik równoległy: fale niezależnych przebiegów → wybór różnorodnych rozwiązań.
//!
//! Fala 1 to `R = max(N + 4, ceil(1.5·N))` przebiegów. Przebieg `r` ma własny strumień losowy
//! `Rng::new(seed, r)`: ocenia pulę `clamp(budget / 8, 8, 128)` losowych startów (przebieg 0
//! dokłada bieżącą paletę), a najlepszy punkt puli minimalizuje lokalnie resztą budżetu. Po fali
//! kandydaci są sortowani i zachłannie wybierani z warunkiem minimalnej różnorodności. Gdy
//! wybranych jest mniej niż N, fale 2 i 3 puszczają `ceil(1.5·brakujących)` przebiegów z karą
//! odpychającą od wybranych; potem lista jest dopełniana najlepszymi pozostałymi z
//! `diverse = false`. Liczba fal jest stała i mała — sterownik nie szuka różnorodności do skutku.
//!
//! **Determinizm.** Przebiegi fali nie dzielą żadnego stanu (poza licznikami postępu) i są
//! zbierane wg numeru, nie wg kolejności zakończenia, więc wynik jest bitowo ten sam dla każdej
//! liczby wątków. Wyjątkiem jest przerwanie (anulowanie, limit czasu): wtedy wynik zależy od
//! tego, które przebiegi zdążyły się skończyć, i jest oznaczony `cancelled` / `timed_out`.

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

use rayon::prelude::*;

use crate::objective::Objective;
use crate::rng::Rng;

use super::lbfgsb::{self, Settings, Stop};
use super::select::{assemble, pick_diverse, rank};
use super::{Candidate, Control, DriverOpts, Outcome};

/// Największa liczba fal.
pub const MAX_WAVES: u32 = 3;

/// Liczba przebiegów pierwszej fali dla `n` rozwiązań: `max(n + 4, ceil(1.5·n))`.
pub fn first_wave_runs(n: usize) -> usize {
    (n + 4).max((3 * n).div_ceil(2))
}

/// Liczba przebiegów fali uzupełniającej: `ceil(1.5·brakujących)`.
pub fn refill_runs(missing: usize) -> usize {
    (3 * missing).div_ceil(2)
}

/// Wielkość puli startów przebiegu: `clamp(budget / 8, 8, 128)`.
pub fn pool_size(budget: usize) -> usize {
    (budget / 8).clamp(8, 128)
}

/// Generuje do `opts.n` różnorodnych rozwiązań funkcji celu `obj`. Blokuje do końca; postęp
/// i przerwanie przez `ctl`.
pub fn generate<O: Objective>(obj: &O, opts: &DriverOpts, ctl: &Control) -> Outcome {
    let deadline = Instant::now().checked_add(opts.time_cap);
    let timed_out = AtomicBool::new(false);
    let stop = || {
        if ctl.is_cancelled() || timed_out.load(Ordering::Relaxed) {
            return true;
        }
        if deadline.is_some_and(|d| Instant::now() >= d) {
            timed_out.store(true, Ordering::Relaxed);
            return true;
        }
        false
    };

    let mut all: Vec<Candidate> = Vec::new();
    let mut picked: Vec<usize> = Vec::new();
    if opts.n > 0 {
        let pool = thread_pool(opts.threads);
        let mut next_run: u32 = 0;
        for wave in 1..=MAX_WAVES {
            let (count, others): (usize, Vec<Vec<f64>>) = if wave == 1 {
                (first_wave_runs(opts.n), Vec::new())
            } else {
                let chosen = picked.iter().map(|&i| all[i].x.clone()).collect();
                (refill_runs(opts.n - picked.len()), chosen)
            };
            if stop() {
                break;
            }
            ctl.plan((count as u64).saturating_mul(opts.budget as u64));
            let first = next_run;
            let one = |k: usize| run_one(obj, opts, ctl, &stop, first + k as u32, wave, &others);
            // `collect` zachowuje kolejność indeksów, niezależnie od kolejności zakończenia
            let finished: Vec<Option<Candidate>> = match &pool {
                Some(pool) => pool.install(|| (0..count).into_par_iter().map(one).collect()),
                None => (0..count).map(one).collect(),
            };
            next_run += count as u32;
            all.extend(finished.into_iter().flatten());
            all.sort_by(rank);
            picked = pick_diverse(obj, &all, opts.n, opts.min_diversity);
            if picked.len() >= opts.n || stop() {
                break;
            }
        }
    }

    let cancelled = ctl.is_cancelled();
    let timed_out = timed_out.load(Ordering::Relaxed);
    if !cancelled && !timed_out {
        ctl.finish();
    }
    Outcome {
        chosen: assemble(&all, &picked, opts.n),
        timed_out,
        cancelled,
        runs: all.len() as u32,
    }
}

/// Pula wątków na jedno generowanie; `None` = wykonanie w wątku wywołującym (jeden wątek albo
/// nie udało się utworzyć puli).
fn thread_pool(threads: usize) -> Option<rayon::ThreadPool> {
    let threads = match threads {
        0 => std::thread::available_parallelism().map_or(1, |n| n.get()),
        n => n,
    };
    if threads <= 1 {
        return None;
    }
    rayon::ThreadPoolBuilder::new()
        .num_threads(threads)
        .thread_name(|i| format!("algopalette-{i}"))
        .build()
        .ok()
}

/// Jeden przebieg: pula startów → lokalna minimalizacja. `None`, gdy przebieg przerwano.
///
/// `others` to rozwiązania, od których przebieg ma się odpychać (puste w fali 1). Liczba
/// wywołań `value_grad` nie przekracza `opts.budget`.
pub(crate) fn run_one<O: Objective>(
    obj: &O,
    opts: &DriverOpts,
    ctl: &Control,
    stop: &(dyn Fn() -> bool + Sync),
    run: u32,
    wave: u32,
    others: &[Vec<f64>],
) -> Option<Candidate> {
    let n = obj.dim();
    let (lower, upper) = obj.bounds();
    let mut rng = Rng::new(opts.seed, u64::from(run));
    let eval = |x: &[f64], grad: &mut [f64]| {
        let mut f = obj.value_grad(x, grad);
        if !others.is_empty() {
            f += obj.repulsion(x, others, opts.min_diversity, grad);
        }
        ctl.add_done(1);
        f
    };

    // Pula startów: przebieg 0 zaczyna od bieżącej palety, potem losowania.
    let samples = pool_size(opts.budget);
    let starts = (samples + usize::from(run == 0)).min(opts.budget).max(1);
    let mut x = vec![0.0; n];
    let mut grad = vec![0.0; n];
    let mut best_x = vec![0.0; n];
    let mut best_grad = vec![0.0; n];
    let mut best_f = f64::INFINITY;
    let mut used = 0;
    for k in 0..starts {
        if run == 0 && k == 0 {
            obj.current(&mut x);
        } else {
            obj.sample(&mut rng, &mut x);
        }
        if used >= opts.budget {
            // budżet 0: pierwszy punkt bez oceny
            best_x.copy_from_slice(&x);
            break;
        }
        if stop() {
            return None;
        }
        let f = eval(&x, &mut grad);
        used += 1;
        if k == 0 || f < best_f {
            best_f = f;
            best_x.copy_from_slice(&x);
            best_grad.copy_from_slice(&grad);
        }
    }

    let settings = Settings { max_evals: opts.budget - used, ..Settings::default() };
    let known = (used > 0).then_some((best_f, best_grad.as_slice()));
    let minimum = lbfgsb::minimize(eval, lower, upper, &best_x, known, &settings, stop);
    if minimum.stop == Stop::Interrupted {
        return None;
    }
    used += minimum.evals;
    // niewykorzystany budżet liczy się jako wykonany: postęp dochodzi do 1 mimo wczesnej zbieżności
    ctl.add_done(opts.budget.saturating_sub(used) as u64);
    ctl.add_candidate();
    let score = obj.score(&minimum.x);
    Some(Candidate { x: minimum.x, score, run, wave, diverse: true })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::optim::select::rank;
    use crate::optim::testutil::Wells;
    use std::sync::atomic::Ordering;
    use std::time::{Duration, Instant};

    fn opts(n: usize, budget: usize, threads: usize) -> DriverOpts {
        DriverOpts {
            n,
            seed: 7,
            budget,
            time_cap: Duration::from_secs(60),
            min_diversity: 0.5,
            threads,
        }
    }

    fn first_wave(n: usize) -> u32 {
        (n + 4).max((3 * n).div_ceil(2)) as u32
    }

    fn bits(o: &Outcome) -> Vec<Vec<u64>> {
        o.chosen.iter().map(|c| c.x.iter().map(|v| v.to_bits()).collect()).collect()
    }

    #[test]
    fn separated_minima_give_n_diverse_candidates() {
        let obj = Wells::grid(4);
        let o = generate(&obj, &opts(6, 200, 4), &Control::new());
        assert_eq!(o.chosen.len(), 6);
        assert!(!o.timed_out && !o.cancelled);
        assert!(o.chosen.iter().all(|c| c.diverse));
        for (i, a) in o.chosen.iter().enumerate() {
            for b in &o.chosen[i + 1..] {
                let d = obj.distance(&a.x, &b.x);
                assert!(d >= 0.5, "kandydaci {} i {} odlegli o {d}", a.run, b.run);
            }
            // każdy kandydat to dno którejś studni, a ocena nie zawiera kary odpychającej
            let (k, f) = obj.well(&a.x);
            assert!((f - obj.depths[k]).abs() <= 1e-9, "przebieg {}: f = {f}", a.run);
            assert_eq!(a.score.total, f);
        }
    }

    #[test]
    fn single_minimum_is_filled_with_non_diverse_after_three_waves() {
        let obj = Wells::single();
        let n = 5;
        let o = generate(&obj, &opts(n, 200, 4), &Control::new());
        assert_eq!(o.chosen.len(), n);
        assert_eq!(o.chosen.iter().filter(|c| !c.diverse).count(), n - 1);
        assert!(o.chosen[0].diverse, "najlepszy kandydat jest zawsze różnorodny");
        // fale 2 i 3 dokładają po ceil(1.5 · brakujących) przebiegów; czwartej fali nie ma
        let later = (3 * (n as u32 - 1)).div_ceil(2);
        assert_eq!(o.runs, first_wave(n) + 2 * later);
        assert!(o.chosen.iter().all(|c| (1..=3).contains(&c.wave)));
    }

    #[test]
    fn enough_diverse_candidates_in_first_wave_means_one_wave() {
        let obj = Wells::grid(4);
        let mut options = opts(2, 200, 4);
        options.min_diversity = 0.0; // każdy kandydat jest różny
        let o = generate(&obj, &options, &Control::new());
        assert_eq!(o.runs, first_wave(2));
        assert!(o.chosen.iter().all(|c| c.wave == 1 && c.diverse));
    }

    #[test]
    fn result_does_not_depend_on_thread_count() {
        let obj = Wells::grid(4);
        let reference = generate(&obj, &opts(8, 120, 1), &Control::new());
        assert_eq!(reference.chosen.len(), 8);
        // funkcja jest wielomodalna: wybrani kandydaci leżą w różnych studniach
        let mut wells: Vec<usize> = reference.chosen.iter().map(|c| obj.well(&c.x).0).collect();
        wells.sort_unstable();
        wells.dedup();
        assert!(wells.len() >= 6, "studnie: {wells:?}");
        for threads in [1, 2, 8, 0] {
            let o = generate(&obj, &opts(8, 120, threads), &Control::new());
            assert_eq!(o, reference, "wątki: {threads}");
            assert_eq!(bits(&o), bits(&reference), "wątki: {threads}");
        }
        // inne ziarno daje inny wynik (test nie jest pusty)
        let mut other = opts(8, 120, 8);
        other.seed = 8;
        assert_ne!(bits(&generate(&obj, &other, &Control::new())), bits(&reference));
    }

    #[test]
    fn chosen_is_ordered_feasible_first_then_by_total() {
        let mut obj = Wells::grid(3);
        obj.feasible_below = 0.035; // studnie 0–3 bez twardych naruszeń, 4–8 z naruszeniami
        let o = generate(&obj, &opts(7, 200, 4), &Control::new());
        assert_eq!(o.chosen.len(), 7);
        let feasible = o.chosen.iter().filter(|c| c.score.feasible).count();
        assert!((1..7).contains(&feasible), "bez naruszeń: {feasible}");
        for pair in o.chosen.windows(2) {
            assert_ne!(rank(&pair[0], &pair[1]), std::cmp::Ordering::Greater, "{pair:?}");
        }
        assert!(o.chosen[..feasible].iter().all(|c| c.score.feasible));
        assert!(o.chosen[feasible..].iter().all(|c| !c.score.feasible));
    }

    #[test]
    fn one_run_never_exceeds_its_budget() {
        let others = [vec![0.5, 0.5]];
        for budget in [1, 2, 7, 8, 9, 10, 20, 64, 200, 3000] {
            for run in [0, 5] {
                for repel in [&[][..], &others[..]] {
                    let obj = Wells::grid(4);
                    let ctl = Control::new();
                    let options = opts(4, budget, 1);
                    let cand = run_one(&obj, &options, &ctl, &|| false, run, 1, repel);
                    let calls = obj.calls.load(Ordering::Relaxed);
                    assert!(
                        calls >= 1 && calls <= budget,
                        "budżet {budget}, przebieg {run}: {calls}"
                    );
                    assert!(cand.is_some());
                    // niewykorzystany budżet jest doliczony do postępu
                    assert_eq!(ctl.evals_done(), budget as u64);
                    assert_eq!(ctl.candidates(), 1);
                }
            }
        }
    }

    #[test]
    fn all_evaluations_stay_within_the_plan_and_progress_reaches_one() {
        let obj = Wells::single();
        let ctl = Control::new();
        assert_eq!(ctl.progress(), 0.0);
        let o = generate(&obj, &opts(5, 40, 4), &ctl);
        let calls = obj.calls.load(Ordering::Relaxed) as u64;
        assert_eq!(ctl.evals_planned(), u64::from(o.runs) * 40);
        assert!(calls <= ctl.evals_planned());
        assert_eq!(ctl.evals_done(), ctl.evals_planned());
        assert_eq!(ctl.candidates(), o.runs as usize);
        assert_eq!(ctl.progress(), 1.0);
    }

    #[test]
    fn run_zero_includes_the_current_palette_as_a_start() {
        // bieżący punkt (środek pudełka) leży dokładnie w dnie jedynej studni
        let obj = Wells::single();
        let o = generate(&obj, &opts(1, 50, 1), &Control::new());
        assert_eq!(o.chosen[0].run, 0);
        assert_eq!(o.chosen[0].x, [0.5, 0.5]);
        assert_eq!(o.chosen[0].score.total, 0.0);
    }

    #[test]
    fn cancel_returns_within_100_ms_with_completed_runs_only() {
        let mut obj = Wells::grid(4);
        obj.delay = Some(Duration::from_millis(1));
        let ctl = Control::new();
        let options = opts(20, 30, 2);
        let (outcome, lag) = std::thread::scope(|scope| {
            let canceller = scope.spawn(|| {
                std::thread::sleep(Duration::from_millis(80));
                ctl.cancel();
                Instant::now()
            });
            let outcome = generate(&obj, &options, &ctl);
            let returned = Instant::now();
            let cancelled_at = canceller.join().expect("wątek anulujący");
            (outcome, returned.saturating_duration_since(cancelled_at))
        });
        assert!(outcome.cancelled && !outcome.timed_out);
        assert!(lag <= Duration::from_millis(100), "powrót po {lag:?}");
        assert!(outcome.runs >= 1 && outcome.runs < first_wave(20), "przebiegi: {}", outcome.runs);
        assert_eq!(outcome.runs as usize, ctl.candidates());
        assert!(!outcome.chosen.is_empty() && outcome.chosen.len() <= outcome.runs as usize);
        // przerwany przebieg nie trafia do wyniku: każdy kandydat doszedł do dna studni
        for c in &outcome.chosen {
            let (k, f) = obj.well(&c.x);
            assert!((f - obj.depths[k]).abs() <= 1e-9, "niedokończony przebieg {}", c.run);
        }
        assert!(ctl.progress() < 1.0);
    }

    #[test]
    fn cancel_before_start_returns_nothing() {
        let obj = Wells::grid(4);
        let ctl = Control::new();
        ctl.cancel();
        let o = generate(&obj, &opts(6, 200, 4), &ctl);
        assert!(o.cancelled && o.chosen.is_empty());
        assert_eq!((o.runs, obj.calls.load(Ordering::Relaxed)), (0, 0));
    }

    #[test]
    fn exceeded_time_cap_marks_the_result_timed_out() {
        let mut obj = Wells::grid(4);
        obj.delay = Some(Duration::from_millis(1));
        let mut options = opts(20, 30, 2);
        options.time_cap = Duration::from_millis(80);
        let started = Instant::now();
        let o = generate(&obj, &options, &Control::new());
        let elapsed = started.elapsed();
        assert!(o.timed_out && !o.cancelled);
        assert!(elapsed <= Duration::from_millis(180), "powrót po {elapsed:?}");
        assert!(o.runs >= 1 && o.runs < first_wave(20));
        assert!(!o.chosen.is_empty());
    }

    #[test]
    fn degenerate_requests_do_not_panic() {
        let obj = Wells::grid(2);
        // zero rozwiązań
        let o = generate(&obj, &opts(0, 50, 2), &Control::new());
        assert!(o.chosen.is_empty() && o.runs == 0);
        // więcej rozwiązań niż studni: kara odpychająca daje punkty poza dnem studni, a reszta
        // listy to dopełnienie; różnorodni są parami odlegli, każdy nieróżnorodny ma bliskiego
        // lepszego sąsiada
        let o = generate(&obj, &opts(9, 50, 2), &Control::new());
        assert_eq!(o.chosen.len(), 9);
        let diverse: Vec<&Candidate> = o.chosen.iter().filter(|c| c.diverse).collect();
        assert!(diverse.len() >= 4, "różnorodnych: {}", diverse.len());
        for (i, a) in diverse.iter().enumerate() {
            for b in &diverse[i + 1..] {
                assert!(obj.distance(&a.x, &b.x) >= 0.5);
            }
        }
        for (i, c) in o.chosen.iter().enumerate().filter(|(_, c)| !c.diverse) {
            let near = o.chosen[..i].iter().any(|b| b.diverse && obj.distance(&b.x, &c.x) < 0.5);
            assert!(near, "kandydat {} oznaczony jako nieróżnorodny bez powodu", c.run);
        }
        // funkcja bez zmiennych (wszystkie kolory pod kłódką)
        let empty = Wells {
            centers: vec![vec![]],
            depths: vec![0.25],
            lower: vec![],
            upper: vec![],
            ..Wells::grid(1)
        };
        let o = generate(&empty, &opts(3, 50, 2), &Control::new());
        assert_eq!(o.chosen.len(), 3);
        assert!(o.chosen.iter().all(|c| c.x.is_empty() && c.score.total == 0.25));
        assert_eq!(o.chosen.iter().filter(|c| c.diverse).count(), 1);
    }
}
