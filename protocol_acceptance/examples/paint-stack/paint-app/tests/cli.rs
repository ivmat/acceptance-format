//! End-to-end geometry checks on files written by the compiled binary.
//! Oracles use no renderer or math-library helpers.

use std::fs;
use std::process::Command;

fn bin() -> Command {
    Command::new(env!("CARGO_BIN_EXE_paint"))
}

/// The exact-integer restatement of `|dist((dx,dy),(0,0)) - r| <= 0.5`, re-derived from scratch
/// (not calling anything from `paint_app`, `raster_draw` or `geom_math`).
fn independent_accuracy_ok(r: u32, dx: i64, dy: i64) -> bool {
    if r == 0 {
        return dx == 0 && dy == 0;
    }
    let d2 = (dx * dx + dy * dy) as i128;
    let lo = (2i128 * r as i128 - 1).pow(2);
    let hi = (2i128 * r as i128 + 1).pow(2);
    let scaled = 4i128 * d2;
    lo <= scaled && scaled <= hi
}

#[test]
fn valid_invocation_writes_a_real_ppm_file_independently_verified() {
    let dir = std::env::temp_dir().join(format!("paint-app-cli-test-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let out = dir.join("circle.ppm");
    // Disclosed finite domain, including zero/unit radii and canvas-edge tangency.
    for (cx, cy, r) in [(0u32, 0u32, 0u32), (1, 1, 1), (3, 3, 3), (10, 10, 4),
                        (25, 25, 15), (8, 40, 8), (45, 10, 10), (35, 40, 30)] {
        let status = bin()
            .args(["circle", "--cx", &cx.to_string(), "--cy", &cy.to_string(), "--r", &r.to_string(), "--out"])
            .arg(&out)
            .status()
            .expect("failed to run the paint binary");
        assert!(status.success());

        // Read the ACTUAL bytes the binary wrote to disk (not an in-process Canvas) and parse them
        // with the crate's own real parser, then independently re-derive every pixel's accuracy.
        let bytes = fs::read(&out).expect("output file was not written");
        let (w, h, gray) = paint_app::parse_ppm(&bytes).expect("binary wrote an unparseable PPM file");
        assert!(bytes.starts_with(b"P6\n"));

        let ink_at = |x: i32, y: i32| -> bool {
            x >= 0 && y >= 0 && (x as u32) < w && (y as u32) < h && gray[y as usize * w as usize + x as usize] < 128
        };
        let mut ink_pixels = Vec::new();
        for y in 0..h as i32 {
            for x in 0..w as i32 {
                if ink_at(x, y) {
                    ink_pixels.push((x, y));
                }
            }
        }
        assert!(!ink_pixels.is_empty(), "the real output file has no ink pixels at all");

        // Independent accuracy, on every ink pixel actually found in the real file.
        for &(x, y) in &ink_pixels {
            let (dx, dy) = (x as i64 - cx as i64, y as i64 - cy as i64);
            assert!(independent_accuracy_ok(r, dx, dy), "real file: pixel ({x},{y}) fails independent accuracy check");
        }

        // Independent symmetry, on every ink pixel actually found.
        for &(x, y) in &ink_pixels {
            let (dx, dy) = (x - cx as i32, y - cy as i32);
            for &(u, v) in &[(dx, dy), (-dx, dy), (dx, -dy), (-dx, -dy), (dy, dx), (-dy, dx), (dy, -dx), (-dy, -dx)] {
                assert!(ink_at(cx as i32 + u, cy as i32 + v), "real file: missing reflected ink at ({u},{v})");
            }
        }

        // Independent 8-connectivity: a real flood-fill over the pixels actually found in the file.
        let set: std::collections::HashSet<(i32, i32)> = ink_pixels.iter().copied().collect();
        let mut visited = std::collections::HashSet::new();
        let mut stack = vec![ink_pixels[0]];
        visited.insert(ink_pixels[0]);
        while let Some((x, y)) = stack.pop() {
            for ddx in -1..=1i32 {
                for ddy in -1..=1i32 {
                    if ddx == 0 && ddy == 0 {
                        continue;
                    }
                    let n = (x + ddx, y + ddy);
                    if set.contains(&n) && visited.insert(n) {
                        stack.push(n);
                    }
                }
            }
        }
        assert_eq!(visited.len(), set.len(), "real file: ink pixels are not all one 8-connected component");

        // Connectivity alone allows an open arc. Sort the scanned set by polar angle,
        // then check each consecutive pair INCLUDING wraparound for Chebyshev adjacency.
        ink_pixels.sort_by(|&(ax, ay), &(bx, by)| {
            let angle = |x, y| ((y - cy as i32) as f64).atan2((x - cx as i32) as f64);
            angle(ax, ay).total_cmp(&angle(bx, by))
        });
        for i in 0..ink_pixels.len() {
            let (a, b) = (ink_pixels[i], ink_pixels[(i + 1) % ink_pixels.len()]);
            assert!((a.0 - b.0).abs() <= 1 && (a.1 - b.1).abs() <= 1,
                    "real file: angular cycle has a gap: {a:?} -> {b:?}");
        }
    }
    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn every_malformed_invocation_exits_nonzero_and_never_panics() {
    let cases: &[&[&str]] = &[
        &[],
        &["circle"],
        &["paintbrush", "--cx", "1", "--cy", "1", "--r", "1", "--out", "x.ppm"],
        &["circle", "--cx", "notanumber", "--cy", "1", "--r", "1", "--out", "x.ppm"],
        &["circle", "--cx", "1", "--cy", "1", "--out", "x.ppm"],
        &["circle", "--cx", "1", "--cy", "1", "--r", "1"],
        // Blocker #2 (cross-vendor review 2026-09-26): the exact counterexample, through the real
        // binary — a circle that does not fit entirely inside the canvas must be rejected.
        &["circle", "--cx", "0", "--cy", "0", "--r", "2", "--out", "x.ppm"],
    ];
    for case in cases {
        let output = bin().args(*case).output().expect("failed to run the paint binary");
        assert!(!output.status.success(), "expected a nonzero exit for {case:?}");
        let stderr = String::from_utf8_lossy(&output.stderr);
        assert!(stderr.contains("error:"), "missing error message: {stderr}");
        if *case == cases[cases.len() - 1] {
            assert!(stderr.contains("does not fit entirely inside the canvas"));
        }
        assert!(
            !stderr.contains("panicked"),
            "case {case:?} PANICKED (this is exactly what R4 forbids): {stderr}"
        );
    }
}

#[test]
fn golden_image_matches_fixture() {
    let hex: String = include_str!("fixtures/circle_cx15_cy15_r10.ppm.hex")
        .split_whitespace().collect();
    assert_eq!(hex.len() % 2, 0, "fixture must contain complete bytes");
    let fixture: Vec<u8> = (0..hex.len()).step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).expect("invalid fixture hex"))
        .collect();
    let out = std::env::temp_dir().join(format!("paint-app-golden-{}.ppm", std::process::id()));
    let status = bin().args(["circle", "--cx", "15", "--cy", "15", "--r", "10", "--out"])
        .arg(&out).status().expect("failed to run the paint binary");
    assert!(status.success());
    let bytes = fs::read(&out).expect("output file was not written");
    fs::remove_file(&out).unwrap();
    assert_eq!(bytes, fixture, "binary output differs from the golden fixture");
}
