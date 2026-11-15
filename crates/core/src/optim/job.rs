//! Generowanie jako zadanie w tle: wątek Rusta, stan atomowy, nieblokujące odpytywanie.
//!
//! GUI uruchamia [`Job::spawn`], odpytuje [`Job::poll`] zegarem i na końcu odbiera
//! [`Job::result`]. Zadanie nie potrzebuje wątków Pythona ani GIL. Panika w funkcji celu nie
//! przerywa procesu: zadanie przechodzi w stan [`JobState::Failed`] z opisem.

use std::any::Any;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::atomic::{AtomicU8, Ordering};
use std::sync::{Arc, Mutex, PoisonError};
use std::time::{Duration, Instant};

use crate::objective::Objective;

use super::{Control, DriverOpts, Outcome, generate};

/// Stan zadania.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobState {
    Running,
    Done,
    Cancelled,
    Failed,
}

impl JobState {
    /// Nazwa przekazywana do Pythona (`poll()["state"]`).
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Running => "running",
            Self::Done => "done",
            Self::Cancelled => "cancelled",
            Self::Failed => "failed",
        }
    }

    fn from_u8(v: u8) -> Self {
        match v {
            0 => Self::Running,
            1 => Self::Done,
            2 => Self::Cancelled,
            _ => Self::Failed,
        }
    }
}

/// Migawka stanu zadania.
#[derive(Debug, Clone, PartialEq)]
pub struct JobStatus {
    pub state: JobState,
    /// Postęp w [0, 1], niemalejący.
    pub progress: f64,
    /// Liczba ukończonych przebiegów (gotowych kandydatów).
    pub candidates: usize,
    /// Opis błędu w stanie [`JobState::Failed`].
    pub error: Option<String>,
}

/// Wynik zakończonego zadania.
#[derive(Debug, Clone, PartialEq)]
pub struct JobResult {
    pub outcome: Outcome,
    /// Czas od wywołania [`Job::spawn`] do zakończenia generowania.
    pub elapsed: Duration,
}

/// Dlaczego nie ma wyniku.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum JobError {
    /// Zadanie jeszcze trwa.
    Running,
    /// Zadanie zakończyło się paniką; w środku jej opis.
    Failed(String),
}

impl std::fmt::Display for JobError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Running => f.write_str("job is still running"),
            Self::Failed(message) => write!(f, "job failed: {message}"),
        }
    }
}

impl std::error::Error for JobError {}

struct Shared {
    control: Control,
    state: AtomicU8,
    /// Wynik albo opis paniki; zapisywany raz, tuż przed zmianą stanu.
    finished: Mutex<Option<Result<JobResult, String>>>,
}

/// Uchwyt zadania generowania. Porzucenie uchwytu anuluje zadanie.
pub struct Job {
    shared: Arc<Shared>,
}

impl Job {
    /// Uruchamia generowanie w osobnym wątku i wraca natychmiast.
    pub fn spawn<O: Objective + Send + 'static>(obj: O, opts: DriverOpts) -> Job {
        let shared = Arc::new(Shared {
            control: Control::new(),
            state: AtomicU8::new(JobState::Running as u8),
            finished: Mutex::new(None),
        });
        let worker = Arc::clone(&shared);
        // czas liczony od wywołania `spawn`, nie od startu wątku (ten bywa opóźniony pod obciążeniem)
        let started = Instant::now();
        let body = move || {
            let run = catch_unwind(AssertUnwindSafe(|| generate(&obj, &opts, &worker.control)));
            let (state, finished) = match run {
                Ok(outcome) => {
                    let state =
                        if outcome.cancelled { JobState::Cancelled } else { JobState::Done };
                    (state, Ok(JobResult { outcome, elapsed: started.elapsed() }))
                }
                Err(payload) => (JobState::Failed, Err(panic_message(payload.as_ref()))),
            };
            *worker.finished.lock().unwrap_or_else(PoisonError::into_inner) = Some(finished);
            worker.state.store(state as u8, Ordering::Release);
        };
        let spawned = std::thread::Builder::new().name("algopalette-job".to_owned()).spawn(body);
        if let Err(e) = spawned {
            let message = format!("cannot start job thread: {e}");
            *shared.finished.lock().unwrap_or_else(PoisonError::into_inner) = Some(Err(message));
            shared.state.store(JobState::Failed as u8, Ordering::Release);
        }
        Job { shared }
    }

    /// Stan, postęp i liczba gotowych kandydatów. Nie blokuje.
    pub fn poll(&self) -> JobStatus {
        let state = JobState::from_u8(self.shared.state.load(Ordering::Acquire));
        let error = match state {
            JobState::Failed => match self.result() {
                Err(JobError::Failed(message)) => Some(message),
                _ => None,
            },
            _ => None,
        };
        JobStatus {
            state,
            progress: self.shared.control.progress(),
            candidates: self.shared.control.candidates(),
            error,
        }
    }

    /// Prosi o przerwanie; zadanie kończy się w ≤ 100 ms ze stanem [`JobState::Cancelled`]
    /// i wynikiem złożonym z ukończonych przebiegów.
    pub fn cancel(&self) {
        self.shared.control.cancel();
    }

    /// Wynik zakończonego zadania (także przerwanego). Przed końcem: [`JobError::Running`].
    pub fn result(&self) -> Result<JobResult, JobError> {
        if JobState::from_u8(self.shared.state.load(Ordering::Acquire)) == JobState::Running {
            return Err(JobError::Running);
        }
        match &*self.shared.finished.lock().unwrap_or_else(PoisonError::into_inner) {
            Some(Ok(result)) => Ok(result.clone()),
            Some(Err(message)) => Err(JobError::Failed(message.clone())),
            None => Err(JobError::Running),
        }
    }
}

impl Drop for Job {
    fn drop(&mut self) {
        // wątek zadania jest odłączony; bez tego liczyłby dalej po zniknięciu odbiorcy
        self.shared.control.cancel();
    }
}

fn panic_message(payload: &(dyn Any + Send)) -> String {
    if let Some(text) = payload.downcast_ref::<&str>() {
        (*text).to_owned()
    } else if let Some(text) = payload.downcast_ref::<String>() {
        text.clone()
    } else {
        "panic without a message".to_owned()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::optim::testutil::Wells;
    use crate::optim::{Control, generate};
    use std::sync::Arc;
    use std::time::Instant;

    fn opts(n: usize, budget: usize) -> DriverOpts {
        DriverOpts {
            n,
            seed: 7,
            budget,
            time_cap: Duration::from_secs(60),
            min_diversity: 0.5,
            threads: 2,
        }
    }

    fn slow_wells() -> Wells {
        let mut obj = Wells::grid(4);
        obj.delay = Some(Duration::from_millis(1));
        obj
    }

    /// Czeka na zakończenie zadania, odpytując je; zwraca wszystkie odczytane stany.
    fn poll_until_finished(job: &Job) -> Vec<JobStatus> {
        let started = Instant::now();
        let mut seen = Vec::new();
        loop {
            let status = job.poll();
            let finished = status.state != JobState::Running;
            seen.push(status);
            if finished {
                return seen;
            }
            assert!(started.elapsed() < Duration::from_secs(20), "zadanie nie kończy się");
            std::thread::sleep(Duration::from_millis(2));
        }
    }

    #[test]
    fn finished_job_returns_the_same_outcome_as_blocking_generate() {
        let job = Job::spawn(Wells::grid(4), opts(6, 200));
        let seen = poll_until_finished(&job);
        let last = seen.last().unwrap();
        assert_eq!(last.state, JobState::Done);
        assert_eq!((last.progress, last.error.clone()), (1.0, None));
        let result = job.result().expect("wynik ukończonego zadania");
        assert_eq!(result.outcome, generate(&Wells::grid(4), &opts(6, 200), &Control::new()));
        assert_eq!(last.candidates, result.outcome.runs as usize);
        // wynik można odczytać wielokrotnie
        assert_eq!(job.result().unwrap().outcome, result.outcome);
    }

    #[test]
    fn poll_does_not_block_and_progress_is_monotonic() {
        let job = Job::spawn(slow_wells(), opts(8, 30));
        // pierwsze odpytanie tuż po starcie: zadanie jeszcze trwa, a odpowiedź jest natychmiast
        let started = Instant::now();
        let first = job.poll();
        assert!(
            started.elapsed() < Duration::from_millis(20),
            "poll trwał {:?}",
            started.elapsed()
        );
        assert_eq!(first.state, JobState::Running);
        assert_eq!(job.result(), Err(JobError::Running));

        let seen = poll_until_finished(&job);
        assert!(seen.len() > 10, "za mało odczytów w trakcie: {}", seen.len());
        for pair in seen.windows(2) {
            assert!(pair[1].progress >= pair[0].progress, "postęp się cofnął: {pair:?}");
            assert!(pair[1].candidates >= pair[0].candidates);
        }
        assert!(seen.iter().all(|s| (0.0..=1.0).contains(&s.progress)));
        assert!(
            seen.iter().any(|s| s.progress > 0.0 && s.progress < 1.0),
            "brak stanów pośrednich"
        );
        assert_eq!(seen.last().unwrap().progress, 1.0);
    }

    #[test]
    fn cancelled_job_ends_quickly_and_keeps_completed_candidates() {
        let job = Job::spawn(slow_wells(), opts(20, 30));
        std::thread::sleep(Duration::from_millis(80));
        let cancelled_at = Instant::now();
        job.cancel();
        let seen = poll_until_finished(&job);
        assert!(
            cancelled_at.elapsed() <= Duration::from_millis(100),
            "{:?}",
            cancelled_at.elapsed()
        );
        assert_eq!(seen.last().unwrap().state, JobState::Cancelled);
        let result = job.result().expect("wynik przerwanego zadania");
        assert!(result.outcome.cancelled);
        assert!(!result.outcome.chosen.is_empty());
        assert!(result.elapsed >= Duration::from_millis(80));
    }

    #[test]
    fn panic_in_objective_fails_the_job_with_a_description() {
        let mut obj = Wells::grid(4);
        obj.panic_at = Some(40);
        let job = Job::spawn(obj, opts(6, 200));
        let seen = poll_until_finished(&job);
        let last = seen.last().unwrap();
        assert_eq!(last.state, JobState::Failed);
        let message = last.error.clone().expect("opis błędu");
        assert!(message.contains("celowa panika funkcji celu"), "{message}");
        assert_eq!(job.result(), Err(JobError::Failed(message)));
    }

    #[test]
    fn dropping_a_running_job_cancels_it() {
        let obj = Arc::new(slow_wells());
        let job = Job::spawn(Arc::clone(&obj), opts(20, 30));
        std::thread::sleep(Duration::from_millis(30));
        drop(job);
        // wątek zadania kończy się sam: licznik wywołań przestaje rosnąć
        std::thread::sleep(Duration::from_millis(150));
        let calls = obj.calls.load(std::sync::atomic::Ordering::Relaxed);
        std::thread::sleep(Duration::from_millis(60));
        assert_eq!(obj.calls.load(std::sync::atomic::Ordering::Relaxed), calls);
        assert!(calls > 0, "zadanie nie wystartowało");
        assert!(calls < 400, "zadanie nie zostało przerwane: {calls} wywołań");
    }

    #[test]
    fn state_names_match_the_python_contract() {
        let names: Vec<&str> =
            [JobState::Running, JobState::Done, JobState::Cancelled, JobState::Failed]
                .iter()
                .map(|s| s.as_str())
                .collect();
        assert_eq!(names, ["running", "done", "cancelled", "failed"]);
    }
}
