//! `algopalette-bench`: benchmarki i uruchamianie silnika na pliku sesji bez GUI.
//!
//! Stan po Tasku 4a: tylko `--version`; pomiary W1–W4 dochodzą w Tasku 16.

use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [flag] if flag == "--version" || flag == "-V" => {
            println!("algopalette-bench {}", algopalette_core::VERSION);
            ExitCode::SUCCESS
        }
        _ => {
            eprintln!("usage: algopalette-bench --version");
            ExitCode::from(2)
        }
    }
}
