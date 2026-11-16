//! `algopalette-bench`: uruchamia silnik na pliku sesji `algopalette.v2` bez GUI i mierzy czas.
//!
//! ```text
//! algopalette-bench <sesja.json> [--threads N] [--repeat K] [--evaluate K] [--micro K]
//! algopalette-bench --version
//! ```
//!
//! Generuje propozycje dla wszystkich kolorów bez kłódki, z parametrami z `globals.optimizer`
//! pliku (`--threads` nadpisuje liczbę wątków). Dla każdego powtórzenia wypisuje czas, liczbę
//! propozycji, ile z nich nie ma twardych naruszeń i ile ma naruszenie „różnorodność”.
//! `--evaluate K` mierzy zamiast tego ocenę naruszeń bieżących wartości (K powtórzeń),
//! `--micro K` — koszt jednego wywołania funkcji celu (profil: K losowych startów + rozwiązania).

use std::process::ExitCode;
use std::time::Instant;

use algopalette_core::optim::{Control, generate};
use algopalette_core::rules::{self, Problem};
use algopalette_core::schema::{self, Session};
use algopalette_core::violation::ViolationKind;

const USAGE: &str = "usage: algopalette-bench <session.json> [--threads N] [--repeat K] [--evaluate K]\n       algopalette-bench --version";

struct Args {
    path: String,
    threads: Option<usize>,
    repeat: usize,
    evaluate: Option<usize>,
    micro: Option<usize>,
}

fn parse_args(args: &[String]) -> Result<Args, String> {
    let mut out =
        Args { path: String::new(), threads: None, repeat: 1, evaluate: None, micro: None };
    let mut it = args.iter();
    while let Some(arg) = it.next() {
        let mut number = |name: &str| -> Result<usize, String> {
            let value = it.next().ok_or_else(|| format!("{name} needs a number"))?;
            value.parse().map_err(|_| format!("{name}: not a number: {value}"))
        };
        match arg.as_str() {
            "--threads" => out.threads = Some(number("--threads")?),
            "--repeat" => out.repeat = number("--repeat")?.max(1),
            "--evaluate" => out.evaluate = Some(number("--evaluate")?.max(1)),
            "--micro" => out.micro = Some(number("--micro")?.max(1)),
            flag if flag.starts_with("--") => return Err(format!("unknown option {flag}")),
            path if out.path.is_empty() => out.path = path.to_owned(),
            extra => return Err(format!("unexpected argument {extra}")),
        }
    }
    if out.path.is_empty() {
        return Err("missing session file".to_owned());
    }
    Ok(out)
}

fn median(sorted: &[f64]) -> f64 {
    let n = sorted.len();
    if n % 2 == 1 { sorted[n / 2] } else { 0.5 * (sorted[n / 2 - 1] + sorted[n / 2]) }
}

fn summary(label: &str, times: &mut [f64]) {
    times.sort_by(f64::total_cmp);
    println!(
        "{label}: min={:.6} median={:.6} max={:.6} (n={})",
        times[0],
        median(times),
        times[times.len() - 1],
        times.len()
    );
}

fn bench_generate(session: &Session, args: &Args) {
    let free: Vec<String> =
        session.slots.iter().filter(|s| !s.locked).map(|s| s.id.clone()).collect();
    let problem = Problem::compile(session, &free);
    let mut opts = rules::driver_opts(session, &problem);
    if let Some(threads) = args.threads {
        opts.threads = threads;
    }
    println!(
        "session={} slots={} free={} proposals={} budget={} threads={} seed={}",
        args.path,
        session.slots.len(),
        free.len(),
        opts.n,
        opts.budget,
        opts.threads,
        opts.seed
    );
    let mut times = Vec::with_capacity(args.repeat);
    for round in 1..=args.repeat {
        let started = Instant::now();
        // kompilacja sesji należy do czasu generowania, tak jak w `_engine.start`
        let problem = Problem::compile(session, &free);
        let control = Control::new();
        let outcome = generate(&problem, &opts, &control);
        let proposals = rules::proposals(&problem, &outcome, opts.min_diversity);
        let elapsed = started.elapsed().as_secs_f64();
        times.push(elapsed);
        let feasible = proposals.iter().filter(|p| p.feasible()).count();
        let similar = proposals
            .iter()
            .filter(|p| p.violations.iter().any(|v| v.kind == ViolationKind::Diversity))
            .count();
        let best = proposals.first().map_or(f64::NAN, |p| p.score);
        println!(
            "run={round} time_s={elapsed:.4} proposals={} feasible={feasible} diversity={similar} \
             runs={} evals={} best_score={best:.6} timed_out={} cancelled={}",
            proposals.len(),
            outcome.runs,
            control.evals_used(),
            outcome.timed_out,
            outcome.cancelled
        );
    }
    summary("generate_time_s", &mut times);
}

/// Koszt jednego wywołania funkcji celu: w losowych startach, w gotowych rozwiązaniach i kara
/// odpychająca od wszystkich rozwiązań.
fn bench_micro(session: &Session, args: &Args, points: usize) {
    use algopalette_core::objective::Objective;
    use algopalette_core::rng::Rng;
    let free: Vec<String> =
        session.slots.iter().filter(|s| !s.locked).map(|s| s.id.clone()).collect();
    let problem = Problem::compile(session, &free);
    let mut opts = rules::driver_opts(session, &problem);
    if let Some(threads) = args.threads {
        opts.threads = threads;
    }
    let dim = problem.dim();
    let mut rng = Rng::new(opts.seed, 0);
    let starts: Vec<Vec<f64>> = (0..points)
        .map(|_| {
            let mut x = vec![0.0; dim];
            problem.sample(&mut rng, &mut x);
            x
        })
        .collect();
    let outcome = generate(&problem, &opts, &Control::new());
    let solved: Vec<Vec<f64>> = outcome.chosen.iter().map(|c| c.x.clone()).collect();
    let others: Vec<Vec<f64>> = solved.iter().map(|x| problem.prepare(x)).collect();
    let mut grad = vec![0.0; dim];
    let mut time = |label: &str, set: &[Vec<f64>], f: &mut dyn FnMut(&[f64], &mut [f64]) -> f64| {
        let rounds = (200_000 / set.len().max(1)).max(1);
        let started = Instant::now();
        let mut sum = 0.0;
        for _ in 0..rounds {
            for x in set {
                sum += f(x, &mut grad);
            }
        }
        let per = started.elapsed().as_secs_f64() * 1e6 / (rounds * set.len()) as f64;
        println!(
            "{label}: {per:.3} us/call (mean value {:.4e})",
            sum / (rounds * set.len()) as f64
        );
    };
    println!("dim={dim} solutions={} others={}", solved.len(), others.len());
    time("value_grad at random starts", &starts, &mut |x, g| problem.value_grad(x, g));
    time("value_grad at solutions", &solved, &mut |x, g| problem.value_grad(x, g));
    time("polish value_grad at solutions", &solved, &mut |x, g| {
        problem.penalized_grad(x, &[], 0.0, true, g)
    });
    time("value_grad + repulsion at solutions", &solved, &mut |x, g| {
        problem.penalized_grad(x, &others, opts.min_diversity, false, g)
    });
    time("score at solutions", &solved, &mut |x, _| problem.score(x).total);
    time("repulsion at solutions", &solved, &mut |x, g| {
        problem.repulsion(x, &others, opts.min_diversity, g)
    });
    time("repulsion at random starts", &starts, &mut |x, g| {
        problem.repulsion(x, &others, opts.min_diversity, g)
    });
}

fn bench_evaluate(text: &str, repeat: usize) -> Result<(), String> {
    let mut times = Vec::with_capacity(repeat);
    let mut found = 0;
    for _ in 0..repeat {
        let started = Instant::now();
        // razem z rozbiorem JSON-a — tak ocenę widzi Python
        let session = schema::parse(text).map_err(|e| e.to_string())?;
        let evaluation = rules::evaluate(&session);
        times.push(started.elapsed().as_secs_f64() * 1e3);
        found = evaluation.violations.len();
    }
    println!("violations={found}");
    summary("evaluate_time_ms", &mut times);
    Ok(())
}

fn run(args: &Args) -> Result<(), String> {
    let text = std::fs::read_to_string(&args.path).map_err(|e| format!("{}: {e}", args.path))?;
    let session = schema::parse(&text).map_err(|e| format!("{}: {e}", args.path))?;
    match (args.evaluate, args.micro) {
        (Some(repeat), _) => bench_evaluate(&text, repeat),
        (None, Some(points)) => {
            bench_micro(&session, args, points);
            Ok(())
        }
        (None, None) => {
            bench_generate(&session, args);
            Ok(())
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let [flag] = args.as_slice()
        && (flag == "--version" || flag == "-V")
    {
        println!("algopalette-bench {}", algopalette_core::VERSION);
        return ExitCode::SUCCESS;
    }
    let outcome = parse_args(&args).and_then(|parsed| run(&parsed));
    match outcome {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("algopalette-bench: {message}\n{USAGE}");
            ExitCode::from(2)
        }
    }
}
