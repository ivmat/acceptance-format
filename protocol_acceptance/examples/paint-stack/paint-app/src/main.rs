#![forbid(unsafe_code)]
//! `paint` — CLI entry point. All logic lives in `paint_app` (the library half of this crate) so
//! it is directly unit-testable; this file is a thin, deliberately panic-free shell: parse,
//! render, write, or print a clean error and exit nonzero.

use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let circle = match paint_app::parse_args(&args) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {e}");
            eprintln!("usage: paint circle --cx N --cy N --r N --out FILE.ppm");
            return ExitCode::from(2);
        }
    };
    let canvas = match paint_app::render_circle(circle.cx, circle.cy, circle.r) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::from(1);
        }
    };
    let bytes = paint_app::canvas_to_ppm(&canvas);
    match std::fs::write(&circle.out, &bytes) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: could not write {:?}: {e}", circle.out);
            ExitCode::from(1)
        }
    }
}
