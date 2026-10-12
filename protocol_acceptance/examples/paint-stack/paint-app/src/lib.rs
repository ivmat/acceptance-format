#![forbid(unsafe_code)]
//! `paint-app` — the top layer of the paint-stack example (`geom-math` -> `raster-draw` ->
//! `paint-app`): a tiny CLI, `paint circle --cx N --cy N --r N --out FILE.ppm`, that renders a
//! circle to a binary PPM (P6) file using `raster-draw::draw_circle`.
//!
//! **The consumer-facing claim, precisely.** "Draws a circle correctly" means: every property
//! `raster-draw` proves/tests about `circle_points` (accuracy, 8-way symmetry, closedness) holds
//! of the actual bytes written to the output FILE, not merely of the in-memory `Canvas` — this is
//! why this crate's own tests round-trip through [`canvas_to_ppm`]/[`parse_ppm`] rather than
//! stopping at the `Canvas` layer (a bug in the PPM encoder would otherwise go uncaught). See
//! `acceptance-specification.toml` for the consumer's exact requirements and
//! `acceptance-package.toml`/`acceptance-decision.toml` for the real 0.3.1 evidence.

use raster_draw::Canvas;
use std::fmt;
use std::path::PathBuf;

/// Fixed margin (pixels) added around the circle when auto-sizing the canvas — enough that the
/// circle's own bounding box never touches the canvas edge for a circle centered at
/// `(cx, cy) >= (r, r)`, without needing separate `--width`/`--height` flags (the CLI's brief is
/// deliberately minimal: `--cx --cy --r --out`).
pub const CANVAS_MARGIN: u32 = 3;

/// A drawn ("ink") pixel's raw `Canvas` value; `0` (the `Canvas` default) is background. Never
/// `0`, so a drawn pixel is always distinguishable from background — see [`canvas_to_ppm`]'s doc
/// comment for how this becomes black-on-white in the output file.
pub const INK: u8 = 255;

// ---------------------------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CircleArgs {
    pub cx: u32,
    pub cy: u32,
    pub r: u32,
    pub out: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ArgError {
    NoSubcommand,
    UnknownSubcommand(String),
    MissingFlag(&'static str),
    UnknownFlag(String),
    MissingValue(String),
    BadValue { flag: String, value: String },
    DuplicateFlag(String),
}

impl fmt::Display for ArgError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ArgError::NoSubcommand => write!(f, "no subcommand given (expected `circle`)"),
            ArgError::UnknownSubcommand(s) => write!(f, "unknown subcommand {s:?} (expected `circle`)"),
            ArgError::MissingFlag(name) => write!(f, "missing required flag --{name}"),
            ArgError::UnknownFlag(s) => write!(f, "unknown flag {s:?}"),
            ArgError::MissingValue(flag) => write!(f, "flag {flag} given with no value"),
            ArgError::BadValue { flag, value } => write!(f, "flag {flag} has an invalid value: {value:?}"),
            ArgError::DuplicateFlag(flag) => write!(f, "flag {flag} given more than once"),
        }
    }
}

/// Parses `paint circle --cx N --cy N --r N --out FILE.ppm` (any flag order). Never panics on any
/// input, including empty input, an unknown subcommand, non-numeric values, missing flags,
/// duplicated flags, or a flag with no following value — every one of those is a distinct `Err`
/// variant, not a panic (this crate's `no_panic` test in `tests/cli.rs` fuzzes exactly this
/// surface, including through the compiled binary).
pub fn parse_args(args: &[String]) -> Result<CircleArgs, ArgError> {
    let mut it = args.iter();
    match it.next() {
        None => return Err(ArgError::NoSubcommand),
        Some(s) if s == "circle" => {}
        Some(s) => return Err(ArgError::UnknownSubcommand(s.clone())),
    }

    let mut cx: Option<u32> = None;
    let mut cy: Option<u32> = None;
    let mut r: Option<u32> = None;
    let mut out: Option<PathBuf> = None;

    while let Some(flag) = it.next() {
        let value = it.next().ok_or_else(|| ArgError::MissingValue(flag.clone()))?;
        match flag.as_str() {
            "--cx" => {
                if cx.is_some() {
                    return Err(ArgError::DuplicateFlag(flag.clone()));
                }
                cx = Some(value.parse::<u32>().map_err(|_| ArgError::BadValue {
                    flag: flag.clone(),
                    value: value.clone(),
                })?);
            }
            "--cy" => {
                if cy.is_some() {
                    return Err(ArgError::DuplicateFlag(flag.clone()));
                }
                cy = Some(value.parse::<u32>().map_err(|_| ArgError::BadValue {
                    flag: flag.clone(),
                    value: value.clone(),
                })?);
            }
            "--r" => {
                if r.is_some() {
                    return Err(ArgError::DuplicateFlag(flag.clone()));
                }
                r = Some(value.parse::<u32>().map_err(|_| ArgError::BadValue {
                    flag: flag.clone(),
                    value: value.clone(),
                })?);
            }
            "--out" => {
                if out.is_some() {
                    return Err(ArgError::DuplicateFlag(flag.clone()));
                }
                if value.is_empty() {
                    return Err(ArgError::BadValue { flag: flag.clone(), value: value.clone() });
                }
                out = Some(PathBuf::from(value));
            }
            other => return Err(ArgError::UnknownFlag(other.to_string())),
        }
    }

    Ok(CircleArgs {
        cx: cx.ok_or(ArgError::MissingFlag("cx"))?,
        cy: cy.ok_or(ArgError::MissingFlag("cy"))?,
        r: r.ok_or(ArgError::MissingFlag("r"))?,
        out: out.ok_or(ArgError::MissingFlag("out"))?,
    })
}

// ---------------------------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RenderError {
    /// `cx`/`cy`/`r` are large enough that the auto-sized canvas dimensions would not fit a
    /// `u32` — reported cleanly rather than panicking or silently wrapping.
    DimensionsOverflow,
    /// The requested circle does not fit ENTIRELY inside the auto-sized canvas: `cx < r` or
    /// `cy < r` (the lower-edge case; the upper edge, `cx + r >= width` / `cy + r >= height`, is
    /// also checked, though the auto-sizing below makes it unreachable today — see the doc
    /// comment on [`render_circle`]). Rejected up front, with a clear error, rather than silently
    /// drawing a clipped arc: a consumer contract this narrow ("circles fully inside the canvas")
    /// is what this crate's claims are honestly scoped to (Blocker #2, cross-vendor review
    /// 2026-09-26 — a `cx=0, cy=0, r=2` circle used to silently render an open, asymmetric arc,
    /// `(0,2),(1,2),(2,0),(2,1)`, contradicting the symmetry/closedness claims outright).
    CircleNotFullyInsideCanvas,
}

impl fmt::Display for RenderError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RenderError::DimensionsOverflow => {
                write!(f, "cx/cy/r are too large: the canvas dimensions would not fit")
            }
            RenderError::CircleNotFullyInsideCanvas => {
                write!(
                    f,
                    "the circle (cx, cy, r) does not fit entirely inside the canvas: \
                     cx and cy must each be >= r"
                )
            }
        }
    }
}

/// Renders a circle of radius `r` centered at `(cx, cy)` onto a freshly auto-sized [`Canvas`]:
/// `width = cx + r + CANVAS_MARGIN`, `height = cy + r + CANVAS_MARGIN` (checked arithmetic — see
/// [`RenderError::DimensionsOverflow`]).
///
/// **Domain: circles fully inside the canvas, only.** `(cx, cy)` are canvas-local coordinates, and
/// this function REJECTS any input where the circle would not fit entirely inside the canvas
/// (`cx < r`, `cy < r`, or — unreachable given the auto-sizing above, but checked anyway for
/// robustness — `cx + r >= width` or `cy + r >= height`), returning
/// [`RenderError::CircleNotFullyInsideCanvas`] rather than silently drawing a clipped, asymmetric
/// arc. This is a deliberate narrowing (cross-vendor review 2026-09-26, Blocker #2): a center
/// nearer an edge than the radius used to be silently accepted and clipped, which contradicted
/// this crate's own symmetry/closedness claims (a `cx=0, cy=0, r=2` circle rendered only
/// `(0,2),(1,2),(2,0),(2,1)` — an open, asymmetric arc, not a circle). `raster-draw`'s own
/// `Canvas`/`draw_circle` still clip silently at the LIBRARY level (that claim, `RD-004`, is
/// real and unchanged) — this crate's consumer-facing claims are scoped to the narrower domain
/// this check enforces.
pub fn render_circle(cx: u32, cy: u32, r: u32) -> Result<Canvas, RenderError> {
    if cx < r || cy < r {
        return Err(RenderError::CircleNotFullyInsideCanvas);
    }
    let width = cx
        .checked_add(r)
        .and_then(|v| v.checked_add(CANVAS_MARGIN))
        .ok_or(RenderError::DimensionsOverflow)?;
    let height = cy
        .checked_add(r)
        .and_then(|v| v.checked_add(CANVAS_MARGIN))
        .ok_or(RenderError::DimensionsOverflow)?;
    // Upper-edge check: unreachable today (CANVAS_MARGIN > 0 guarantees cx + r < width and
    // cy + r < height by construction), but stated and checked explicitly rather than assumed,
    // in case a future revision adds explicit --width/--height flags.
    if cx.checked_add(r).is_none_or(|v| v >= width) || cy.checked_add(r).is_none_or(|v| v >= height) {
        return Err(RenderError::CircleNotFullyInsideCanvas);
    }
    let mut canvas = Canvas::new(width, height);
    raster_draw::draw_circle(&mut canvas, cx as i32, cy as i32, r, INK);
    Ok(canvas)
}

// ---------------------------------------------------------------------------------------------
// PPM (P6, binary) encode/decode
// ---------------------------------------------------------------------------------------------

/// Encodes `canvas` as a binary PPM (P6), grayscale-as-RGB, INK pixels rendered black on a white
/// background: `Canvas` value `0` (background) -> RGB `(255,255,255)`; [`INK`] (`255`) -> RGB
/// `(0,0,0)`; any other stored value is linearly inverted the same way (`255 - v`), though this
/// crate only ever writes `0` or `INK`.
///
/// Header is the fixed, exact form `"P6\n{w} {h}\n255\n"` — [`parse_ppm`] is this format's exact
/// inverse (a real, general-purpose PPM reader would tolerate comments/whitespace variation;
/// this one deliberately does not, since it exists to let this crate's own tests parse this
/// crate's own output, not arbitrary third-party PPM files).
pub fn canvas_to_ppm(canvas: &Canvas) -> Vec<u8> {
    let (w, h) = (canvas.width(), canvas.height());
    let mut out = Vec::with_capacity(20 + (w as usize * h as usize * 3));
    out.extend_from_slice(format!("P6\n{w} {h}\n255\n").as_bytes());
    for y in 0..h as i32 {
        for x in 0..w as i32 {
            let v = canvas.pixel(x, y).unwrap_or(0);
            let gray = 255u8.wrapping_sub(v);
            out.push(gray);
            out.push(gray);
            out.push(gray);
        }
    }
    out
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PpmParseError {
    BadHeader,
    TruncatedBody,
}

/// The exact inverse of [`canvas_to_ppm`]'s fixed header form: returns `(width, height, gray)`
/// where `gray[y * width + x]` is the RGB gray level (`0..=255`) at `(x, y)` (this format writes
/// R=G=B, so one channel is kept).
pub fn parse_ppm(bytes: &[u8]) -> Result<(u32, u32, Vec<u8>), PpmParseError> {
    let text_prefix_end = bytes.iter().position(|&b| b == b'\n').and_then(|first_nl| {
        let rest = &bytes[first_nl + 1..];
        rest.iter().position(|&b| b == b'\n').map(|second_nl| first_nl + 1 + second_nl + 1)
    });
    let header_end = text_prefix_end.and_then(|end_of_dims_line| {
        let rest = &bytes[end_of_dims_line..];
        rest.iter().position(|&b| b == b'\n').map(|third_nl| end_of_dims_line + third_nl + 1)
    });
    let header_end = header_end.ok_or(PpmParseError::BadHeader)?;
    let header = std::str::from_utf8(&bytes[..header_end]).map_err(|_| PpmParseError::BadHeader)?;
    let mut lines = header.lines();
    if lines.next() != Some("P6") {
        return Err(PpmParseError::BadHeader);
    }
    let dims = lines.next().ok_or(PpmParseError::BadHeader)?;
    let mut parts = dims.split(' ');
    let w: u32 = parts.next().and_then(|s| s.parse().ok()).ok_or(PpmParseError::BadHeader)?;
    let h: u32 = parts.next().and_then(|s| s.parse().ok()).ok_or(PpmParseError::BadHeader)?;
    if parts.next().is_some() {
        return Err(PpmParseError::BadHeader);
    }
    if lines.next() != Some("255") {
        return Err(PpmParseError::BadHeader);
    }
    if lines.next().is_some() {
        return Err(PpmParseError::BadHeader);
    }

    let body = &bytes[header_end..];
    let expected_len = w as usize * h as usize * 3;
    if body.len() != expected_len {
        return Err(PpmParseError::TruncatedBody);
    }
    let mut gray = Vec::with_capacity(w as usize * h as usize);
    for chunk in body.chunks_exact(3) {
        gray.push(chunk[0]);
    }
    Ok((w, h, gray))
}

#[cfg(test)]
mod tests {
    use super::*;

    // ---- CLI argument parsing --------------------------------------------------------------

    fn args(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn parses_a_well_formed_invocation_in_any_flag_order() {
        let a = parse_args(&args(&["circle", "--cx", "10", "--cy", "20", "--r", "5", "--out", "x.ppm"])).unwrap();
        assert_eq!(a, CircleArgs { cx: 10, cy: 20, r: 5, out: "x.ppm".into() });
        let b = parse_args(&args(&["circle", "--out", "x.ppm", "--r", "5", "--cy", "20", "--cx", "10"])).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn rejects_every_malformed_invocation_without_panicking() {
        let cases: &[&[&str]] = &[
            &[],
            &["paintbrush"],
            &["circle"],
            &["circle", "--cx", "10"],
            &["circle", "--cx", "ten", "--cy", "1", "--r", "1", "--out", "x.ppm"],
            &["circle", "--cx", "1", "--cy", "1", "--r", "notanumber", "--out", "x.ppm"],
            &["circle", "--cx", "-5", "--cy", "1", "--r", "1", "--out", "x.ppm"],
            &["circle", "--cx", "1", "--cy", "1", "--r", "1"],
            &["circle", "--cx", "1", "--cy", "1", "--r", "1", "--out"],
            &["circle", "--cx", "1", "--cy", "1", "--r", "1", "--out", ""],
            &["circle", "--bogus", "1", "--cy", "1", "--r", "1", "--out", "x.ppm"],
            &["circle", "--cx", "1", "--cx", "2", "--cy", "1", "--r", "1", "--out", "x.ppm"],
            &["circle", "--cx", "99999999999999999999", "--cy", "1", "--r", "1", "--out", "x.ppm"],
        ];
        for case in cases {
            let result = parse_args(&args(case));
            assert!(result.is_err(), "expected an error for {case:?}, got {result:?}");
        }
    }

    // ---- Rendering + PPM round-trip --------------------------------------------------------

    #[test]
    fn render_circle_dimension_overflow_is_reported_not_panicked() {
        // Both cx and cy must be >= r to reach the overflow check at all (see the domain-rejection
        // test below) -- cx = cy = r = u32::MAX clears the domain check (cx >= r, cy >= r, both
        // equalities) and then overflows computing `width`/`height`.
        assert_eq!(render_circle(u32::MAX, u32::MAX, u32::MAX).err(), Some(RenderError::DimensionsOverflow));
    }

    /// Blocker #2 (cross-vendor review 2026-09-26): the exact counterexample the review named.
    /// Before this fix, `cx=0, cy=0, r=2` silently rendered an open, asymmetric 4-pixel arc
    /// (`(0,2),(1,2),(2,0),(2,1)`) instead of a circle — contradicting the symmetry/closedness
    /// claims outright. It must now be REJECTED, cleanly, with the domain-specific error.
    #[test]
    fn circle_not_fully_inside_canvas_is_rejected_not_silently_clipped() {
        assert_eq!(render_circle(0, 0, 2).err(), Some(RenderError::CircleNotFullyInsideCanvas));
        assert_eq!(render_circle(1, 5, 2).err(), Some(RenderError::CircleNotFullyInsideCanvas)); // cx < r
        assert_eq!(render_circle(5, 1, 2).err(), Some(RenderError::CircleNotFullyInsideCanvas)); // cy < r
        // The boundary case cx == r, cy == r is legal (the circle's leftmost/topmost point sits
        // exactly on column/row 0, still fully inside a canvas whose origin is (0,0)).
        assert!(render_circle(2, 2, 2).is_ok());
    }

    /// Golden-image test: `circle --cx 15 --cy 15 --r 10` must produce byte-for-byte the same PPM
    /// file stored as hex text at `tests/fixtures/circle_cx15_cy15_r10.ppm.hex` (generated once by actually
    /// running the compiled `paint` binary — see the example README's generation instructions —
    /// never hand-authored). A regression in the encoder, the rasterizer, or the CLI's own
    /// argument-to-canvas wiring that still passes every property test would still be caught here
    /// if it happens to change this one frozen, real output.
    #[test]
    fn golden_image_matches_fixture() {
        let canvas = render_circle(15, 15, 10).unwrap();
        let bytes = canvas_to_ppm(&canvas);
        let hex: String = include_str!("../tests/fixtures/circle_cx15_cy15_r10.ppm.hex")
            .split_whitespace().collect();
        assert_eq!(hex.len() % 2, 0, "fixture must contain complete bytes");
        let fixture: Vec<u8> = (0..hex.len()).step_by(2)
            .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).expect("invalid fixture hex"))
            .collect();
        assert_eq!(bytes.as_slice(), fixture.as_slice(), "golden image regenerated differently than the checked-in fixture");
    }

    // ---- Independent output-file verification (cross-vendor review 2026-09-26, Major #3) -----
    //
    // The tests below deliberately do NOT use `raster_draw::circle_points` (or any other
    // `raster-draw` function) as their oracle — that would only prove the encoder agrees with the
    // rasterizer, not that either is actually correct. Each check below is re-derived from first
    // principles, independently, directly against the bytes `parse_ppm` reads back from what
    // `canvas_to_ppm` wrote:
    // - accuracy: the exact-integer distance formula, hand-written here (not calling
    //   `geom_math::dist2` or `raster_draw::accuracy_ok` either);
    // - symmetry: an exhaustive scan of every ink pixel actually present in the file, each checked
    //   against its own 8 reflections (also scanned, not enumerated by the renderer);
    // - 8-connectivity: a real BFS flood-fill over every ink pixel actually
    //   present in the bytes, asserting one component. The CLI test also checks cyclic adjacency.
    //
    // **Disclosed domain**: `DOMAINS` below — 8 (cx, cy, r) combinations, including the r==cx==cy
    // boundary case, radii from 0 to 30. This is the tested envelope; nothing about any of these
    // properties is claimed for radii or centers outside it (see `acceptance.toml`'s own `bounds`
    // fields for the same disclosure at the claim level).

    const DOMAINS: &[(u32, u32, u32)] = &[(0, 0, 0), (1, 1, 1), (3, 3, 3), (10, 10, 4), (25, 25, 15), (8, 40, 8), (45, 10, 10), (35, 40, 30)];

    /// The exact-integer restatement of `|dist((dx,dy), (0,0)) - r| <= 0.5`, re-derived here from
    /// scratch (NOT calling `raster_draw::accuracy_ok` or `geom_math::dist2`) so this check is a
    /// genuinely independent oracle, not a restatement of the code under test.
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

    fn scan_ink_pixels(w: u32, h: u32, gray: &[u8]) -> Vec<(i32, i32)> {
        let mut out = Vec::new();
        for y in 0..h as i32 {
            for x in 0..w as i32 {
                if gray[y as usize * w as usize + x as usize] < 128 {
                    out.push((x, y));
                }
            }
        }
        out
    }

    /// A real, independent 8-connectivity flood-fill: asserts every pixel in `pixels` is reachable
    /// from the first one via 8-connected steps THROUGH OTHER MEMBERS OF `pixels` — i.e. `pixels`
    /// is exactly one connected component. This alone does not establish closedness.
    fn assert_single_8_connected_component(pixels: &[(i32, i32)]) {
        assert!(!pixels.is_empty(), "no ink pixels at all");
        let set: std::collections::HashSet<(i32, i32)> = pixels.iter().copied().collect();
        let mut visited: std::collections::HashSet<(i32, i32)> = std::collections::HashSet::new();
        let mut stack = vec![pixels[0]];
        visited.insert(pixels[0]);
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
        assert_eq!(
            visited.len(),
            set.len(),
            "ink pixels are NOT all one 8-connected component ({} of {} reachable) -- a gap exists",
            visited.len(),
            set.len()
        );
    }

    #[test]
    fn independent_accuracy_over_disclosed_domain() {
        for &(cx, cy, r) in DOMAINS {
            let canvas = render_circle(cx, cy, r).unwrap();
            let bytes = canvas_to_ppm(&canvas);
            let (w, h, gray) = parse_ppm(&bytes).unwrap();
            let pixels = scan_ink_pixels(w, h, &gray);
            assert!(!pixels.is_empty(), "cx={cx} cy={cy} r={r}: no ink pixels at all");
            for &(x, y) in &pixels {
                let (dx, dy) = (x as i64 - cx as i64, y as i64 - cy as i64);
                assert!(
                    independent_accuracy_ok(r, dx, dy),
                    "cx={cx} cy={cy} r={r}: pixel ({x},{y}) offset ({dx},{dy}) fails the independent accuracy check"
                );
            }
        }
    }

    #[test]
    fn independent_symmetry_over_disclosed_domain() {
        for &(cx, cy, r) in DOMAINS {
            let canvas = render_circle(cx, cy, r).unwrap();
            let bytes = canvas_to_ppm(&canvas);
            let (w, h, gray) = parse_ppm(&bytes).unwrap();
            let ink_at = |x: i32, y: i32| -> bool {
                x >= 0 && y >= 0 && (x as u32) < w && (y as u32) < h && gray[y as usize * w as usize + x as usize] < 128
            };
            let pixels = scan_ink_pixels(w, h, &gray);
            for &(x, y) in &pixels {
                let (dx, dy) = (x - cx as i32, y - cy as i32);
                for &(u, v) in &[(dx, dy), (-dx, dy), (dx, -dy), (-dx, -dy), (dy, dx), (-dy, dx), (dy, -dx), (-dy, -dx)] {
                    assert!(
                        ink_at(cx as i32 + u, cy as i32 + v),
                        "cx={cx} cy={cy} r={r}: missing reflected ink at offset ({u},{v}) of scanned pixel ({x},{y})"
                    );
                }
            }
        }
    }

    #[test]
    fn independent_closedness_8_connectivity_over_disclosed_domain() {
        for &(cx, cy, r) in DOMAINS {
            let canvas = render_circle(cx, cy, r).unwrap();
            let bytes = canvas_to_ppm(&canvas);
            let (w, h, gray) = parse_ppm(&bytes).unwrap();
            let pixels = scan_ink_pixels(w, h, &gray);
            assert_single_8_connected_component(&pixels);
        }
    }

    /// Internal CONSISTENCY check only (not the independent oracle — see the `independent_*` tests
    /// above for that): the output file's ink set matches exactly what `raster_draw::circle_points`
    /// claims it drew. This catches an encoder bug that disagrees with the rasterizer; it proves
    /// nothing about whether the rasterizer itself is right (a shared bug would pass this check).
    #[test]
    fn ppm_consistent_with_circle_points_not_independent() {
        let (cx, cy, r) = (30u32, 30u32, 12u32);
        let canvas = render_circle(cx, cy, r).unwrap();
        let bytes = canvas_to_ppm(&canvas);
        let (w, h, gray) = parse_ppm(&bytes).unwrap();
        assert_eq!((w, h), (canvas.width(), canvas.height()));
        let ink_at = |x: i32, y: i32| -> bool {
            if x < 0 || y < 0 || x as u32 >= w || y as u32 >= h {
                return false;
            }
            gray[y as usize * w as usize + x as usize] < 128
        };
        let expected: std::collections::HashSet<(i32, i32)> = raster_draw::circle_points(r)
            .into_iter()
            .map(|(dx, dy)| (cx as i32 + dx, cy as i32 + dy))
            .collect();
        for &(x, y) in &expected {
            assert!(ink_at(x, y), "expected ink at ({x},{y})");
        }
        for y in 0..h as i32 {
            for x in 0..w as i32 {
                if ink_at(x, y) {
                    assert!(expected.contains(&(x, y)), "unexpected ink at ({x},{y})");
                }
            }
        }
    }

    #[test]
    fn parse_ppm_rejects_truncated_and_malformed_input_without_panicking() {
        assert_eq!(parse_ppm(b""), Err(PpmParseError::BadHeader));
        assert_eq!(parse_ppm(b"P6\n"), Err(PpmParseError::BadHeader));
        assert_eq!(parse_ppm(b"P6\n2 2\n255\n\x00"), Err(PpmParseError::TruncatedBody));
        assert_eq!(parse_ppm(b"NOTPPM\n2 2\n255\n"), Err(PpmParseError::BadHeader));
    }
}
