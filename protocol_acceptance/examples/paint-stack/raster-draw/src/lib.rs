#![forbid(unsafe_code)]
//! `raster-draw` — a tiny pixel [`Canvas`] and a midpoint-circle rasterizer, built on
//! a verification helper using `geom-math`'s [`geom_math::dist2`]. The middle layer of the paint-stack example
//! (`geom-math` -> `raster-draw` -> `paint-app`).
//! [`draw_circle`] does not call `dist2`; [`accuracy_ok`] uses it for verification/tests.
//! Rendered accuracy, symmetry and closedness apply only to fully-inside circles.
//! Library drawing still clips out-of-canvas pixels.
//!
//! **The algorithm, and why it is built the way it is.** [`fill_octant`] computes ONE octant of
//! the circle boundary (the 0..=45 degree arc, `dx >= dy >= 0`) with the classic integer midpoint
//! circle algorithm (Bresenham's circle variant) — no floating point anywhere. It writes into a
//! caller-provided fixed-size buffer rather than allocating, which is what makes the bounded Kani
//! harnesses below tractable (same "fixed buffers for Kani" pattern as `iban-check` in the
//! sibling `rust-delivery` example). [`octant_points`] and [`circle_points`] are thin `Vec`-based
//! wrappers for ordinary (non-Kani) callers, including this crate's own property tests and
//! `paint-app`.
//!
//! **Assembling the full circle from one octant (`circle_points`).** The other seven octants are
//! exact reflections of the first: swap `(x, y)` for the 45-90 arc, then negate `x` and/or `y` for
//! the other three quadrants. `circle_points` walks these in a single continuous cyclic order (see
//! its doc comment for the exact construction) so that the returned `Vec` is a closed,
//! 8-connected path around the circle, not merely an unordered set of pixels — this is what makes
//! the "closed, no gaps" claim checkable directly on the returned list (consecutive pairs,
//! wraparound included, per `raster-draw`'s own property tests).
//!
//! **What is proved (Kani) versus tested (property/unit tests) — stated honestly, not implied.**
//! [`fill_octant`]'s two core invariants — every point is within 0.5 of the true radius
//! ([`accuracy_ok`]), and consecutive octant points (including the seam into the mirrored second
//! octant) are 8-connected — are proved by Kani for every radius up to [`KANI_MAX_R`] (6), and
//! checked by property tests (a hand-rolled LCG sampling many radii, see the `tests` module) up to
//! radius 2000. The FULL assembled circle's closedness-as-a-cycle and 8-way symmetry (both of
//! which additionally depend on the quadrant-reflection assembly in `circle_points`, not just
//! `fill_octant`) are checked only by property tests and unit tests, never by Kani — assembling
//! four reflected copies of a `Vec` inside a bounded-model-checking harness buys little beyond
//! what `fill_octant`'s own proof already establishes (the reflections are pure data movement, not
//! new arithmetic), so this crate does not spend Kani's cost there. This is a bounded/empirical
//! argument for the assembled circle, disclosed as such — not a machine-checked one.

pub use geom_math::dist2;

/// A radius large enough that its `fill_octant` proof is a real, if boundedy, check (not just
/// `r=0,1`), while staying inside a human-scale Kani time-box. See the crate's evidence/ for the
/// measured wall-clock time.
pub const KANI_MAX_R: u32 = 6;

/// Fixed capacity for a `fill_octant` buffer at [`KANI_MAX_R`] — used by the Kani harnesses below
/// (no heap allocation inside a bounded-model-checking proof). `octant_len_bound` gives the
/// general-purpose (non-Kani) version of this same bound.
pub const KANI_OCTANT_CAP: usize = (KANI_MAX_R as usize) + 2;

/// An upper bound on how many points [`fill_octant`] can write for a given radius: `y` runs from
/// `0` up to at most `r` (the loop condition `x >= y` cannot hold once `y > r`), so `r + 2` is
/// always enough capacity (the `+2` is slack, not a tight bound).
pub const fn octant_len_bound(r: u32) -> usize {
    r as usize + 2
}

/// Writes octant-A points (`dx >= dy >= 0`, the 0..=45 degree arc of a circle of radius `r`
/// centered on the origin) into `buf`, in order of strictly increasing `dy` starting at `dy = 0`,
/// and returns how many were written. `buf` must have length `>= octant_len_bound(r)` (panics via
/// a plain slice-index panic otherwise — a caller bug, not an input-dependent failure mode. Every
/// call site in this crate sizes its buffer correctly).
///
/// **No multiplication in the loop** (only comparison, addition, subtraction and one `y`
/// increment per step) — `err` is the classic midpoint decision variable in `i64` (wide enough
/// that it cannot overflow even for radii far larger than anything this crate's Kani proofs
/// exercise; property tests exercise it up to radius 2000).
///
/// **Invariant this function relies on and that its callers (and this crate's proofs) rely on in
/// turn:** `y` increases by exactly 1 every iteration, and `x` decreases by 0 or 1 every
/// iteration — never more. This is the standard midpoint-circle property that makes the octant
/// path 8-connected with no gaps, proved for `r <= KANI_MAX_R` by `octant_adjacent_bounded` below
/// and checked for larger radii by this crate's property tests.
pub fn fill_octant(r: u32, buf: &mut [(i32, i32)]) -> usize {
    let mut x: i32 = r as i32;
    let mut y: i32 = 0;
    let mut err: i64 = 1 - x as i64;
    let mut n = 0usize;
    while x >= y {
        buf[n] = (x, y);
        n += 1;
        y += 1;
        if err < 0 {
            err += 2 * y as i64 + 1;
        } else {
            x -= 1;
            err += 2 * (y - x) as i64 + 1;
        }
    }
    n
}

/// `Vec`-based wrapper over [`fill_octant`] for ordinary (non-Kani) callers.
pub fn octant_points(r: u32) -> Vec<(i32, i32)> {
    let mut buf = vec![(0i32, 0i32); octant_len_bound(r)];
    let n = fill_octant(r, &mut buf);
    buf.truncate(n);
    buf
}

/// The exact-integer restatement of "the pixel at offset `(dx, dy)` from the center is within 0.5
/// of the true radius `r`": `|dist((dx,dy), (0,0)) - r| <= 0.5` iff
/// `(2r-1)^2 <= 4 * dist2(dx,dy) <= (2r+1)^2` (squaring both sides of `|sqrt(d2) - r| <= 0.5`
/// after multiplying through by 2 keeps everything in exact integers — no floating point, no
/// rounding, ever). `r = 0` is handled directly: the only accurate point is the center itself.
pub fn accuracy_ok(r: u32, dx: i32, dy: i32) -> bool {
    if r == 0 {
        return dx == 0 && dy == 0;
    }
    let d2 = dist2(dx, dy) as i128;
    let lo = (2i128 * r as i128 - 1).pow(2);
    let hi = (2i128 * r as i128 + 1).pow(2);
    let scaled = 4i128 * d2;
    lo <= scaled && scaled <= hi
}

/// Assembles the full, closed, 8-connected circle boundary for radius `r`, as offsets from the
/// center, in a single continuous cyclic order (the last point is adjacent to the first, not
/// merely a member of the same set).
///
/// **Construction.** `octant_points(r)` gives the 0..=45 degree arc `A` (points `(x, y)`,
/// `x >= y >= 0`, `y` ascending). The 45..=90 degree arc is `A` reversed with coordinates
/// swapped — `(y, x)` continues smoothly from `A`'s last point because swapping `(x, y)` where `x`
/// and `y` are close together moves by at most one step (proved for small `r` by
/// `octant_adjacent_bounded`, the same proof that covers the intra-octant steps). Concatenating
/// these two gives `q0`, the closed 0..=90 degree quarter, starting at `(r, 0)` and ending at
/// `(0, r)`. The remaining three quadrants are exact reflections of `q0`, walked so each one picks
/// up exactly where the previous one ended:
///
/// | quadrant | degrees | points | starts at | ends at |
/// |---|---|---|---|---|
/// | Q0 | 0..90   | `q0` forward                          | `(r, 0)`  | `(0, r)`  |
/// | Q1 | 90..180 | `q0` reversed, `x` negated             | `(0, r)`  | `(-r, 0)` |
/// | Q2 | 180..270| `q0` forward, both negated             | `(-r, 0)` | `(0, -r)` |
/// | Q3 | 270..360| `q0` reversed, `y` negated             | `(0, -r)` | `(r, 0)`  |
///
/// Q3 ends exactly where Q0 started (`(r, 0)`), so the whole sequence is a genuine closed cycle:
/// consecutive elements are 8-connected, WRAPAROUND INCLUDED (`raster-draw`'s own property tests
/// check exactly this, for every radius they sample).
pub fn circle_points(r: u32) -> Vec<(i32, i32)> {
    let a = octant_points(r);
    let mut q0 = Vec::with_capacity(a.len() * 2);
    q0.extend(a.iter().copied());
    q0.extend(a.iter().rev().map(|&(x, y)| (y, x)));

    let mut full = Vec::with_capacity(q0.len() * 4);
    full.extend(q0.iter().copied()); // Q0
    full.extend(q0.iter().rev().map(|&(x, y)| (-x, y))); // Q1
    full.extend(q0.iter().map(|&(x, y)| (-x, -y))); // Q2
    full.extend(q0.iter().rev().map(|&(x, y)| (x, -y))); // Q3
    full
}

/// A pixel canvas: `width * height` single-byte (grayscale-ish) pixels, `0` = background.
#[derive(Debug, Clone)]
pub struct Canvas {
    width: u32,
    height: u32,
    pixels: Vec<u8>,
}

impl Canvas {
    /// Creates a `width x height` canvas, every pixel `0` (background).
    pub fn new(width: u32, height: u32) -> Self {
        Canvas {
            width,
            height,
            pixels: vec![0u8; width as usize * height as usize],
        }
    }

    pub fn width(&self) -> u32 {
        self.width
    }

    pub fn height(&self) -> u32 {
        self.height
    }

    /// Reads the pixel at `(x, y)`. `None` for any out-of-bounds coordinate (negative or
    /// `>= width`/`>= height`) — never panics.
    pub fn pixel(&self, x: i32, y: i32) -> Option<u8> {
        if x < 0 || y < 0 {
            return None;
        }
        let (x, y) = (x as u32, y as u32);
        if x >= self.width || y >= self.height {
            return None;
        }
        Some(self.pixels[(y * self.width + x) as usize])
    }

    /// Sets the pixel at `(x, y)` to `color`. Silently clips (a no-op) for any out-of-bounds
    /// coordinate — never panics, for any `i32` `x`/`y`, including `i32::MIN`/`i32::MAX`. This is
    /// the whole of R4's ("clipping never panics") claim's implementation.
    pub fn set_pixel(&mut self, x: i32, y: i32, color: u8) {
        if x < 0 || y < 0 {
            return;
        }
        let (x, y) = (x as u32, y as u32);
        if x >= self.width || y >= self.height {
            return;
        }
        self.pixels[(y * self.width + x) as usize] = color;
    }

    /// Every set (non-background) pixel's coordinates, for tests that need to inspect the whole
    /// canvas rather than probe individual points.
    pub fn set_pixels(&self) -> Vec<(i32, i32, u8)> {
        let mut out = Vec::new();
        for y in 0..self.height {
            for x in 0..self.width {
                let v = self.pixels[(y * self.width + x) as usize];
                if v != 0 {
                    out.push((x as i32, y as i32, v));
                }
            }
        }
        out
    }
}

/// Draws a circle of radius `r` centered at `(cx, cy)` into `canvas`, in `color`. Never panics —
/// `(cx, cy)` may be anywhere (including entirely off-canvas or at an `i32` extreme), and any
/// resulting out-of-bounds pixel is silently clipped by [`Canvas::set_pixel`].
pub fn draw_circle(canvas: &mut Canvas, cx: i32, cy: i32, r: u32, color: u8) {
    for (dx, dy) in circle_points(r) {
        // `cx`/`cy`/`dx`/`dy` are all `i32`; `checked_add` avoids a debug-mode overflow panic for
        // a center placed at an `i32` extreme with a nonzero offset (an adversarial but legal
        // input) — an add that overflows simply has no on-canvas pixel, which `None` -> skip
        // states honestly rather than wrapping into a bogus in-range coordinate.
        let (Some(x), Some(y)) = (cx.checked_add(dx), cy.checked_add(dy)) else {
            continue;
        };
        canvas.set_pixel(x, y, color);
    }
}

#[cfg(kani)]
mod verification {
    //! Bounded Kani harnesses over [`fill_octant`], `r <= KANI_MAX_R`. See the crate doc comment
    //! for exactly what is (and is not) covered by Kani versus by this crate's property tests.
    use super::*;

    /// Every point [`fill_octant`] writes for `r <= KANI_MAX_R` is within 0.5 of the true radius
    /// ([`accuracy_ok`]), and lies in the claimed octant (`x >= y >= 0`).
    #[kani::proof]
    #[kani::unwind(10)]
    fn octant_accurate_bounded() {
        let r: u32 = kani::any();
        kani::assume(r <= KANI_MAX_R);
        let mut buf = [(0i32, 0i32); KANI_OCTANT_CAP];
        let n = fill_octant(r, &mut buf);
        let mut i = 0;
        while i < n {
            let (x, y) = buf[i];
            assert!(x >= 0 && y >= 0 && x >= y);
            assert!(accuracy_ok(r, x, y));
            i += 1;
        }
    }

    /// Consecutive octant points are 8-connected (Chebyshev distance <= 1), for `r <=
    /// KANI_MAX_R` — INCLUDING the seam point that `circle_points` mirrors into the next octant
    /// (`|x_last - y_last| <= 1`, checked directly here since it is exactly the property
    /// `circle_points`'s own closedness claim depends on at that boundary).
    #[kani::proof]
    #[kani::unwind(10)]
    fn octant_adjacent_bounded() {
        let r: u32 = kani::any();
        kani::assume(r <= KANI_MAX_R);
        let mut buf = [(0i32, 0i32); KANI_OCTANT_CAP];
        let n = fill_octant(r, &mut buf);
        let mut i = 0;
        while i + 1 < n {
            let (x0, y0) = buf[i];
            let (x1, y1) = buf[i + 1];
            assert!((x0 - x1).abs() <= 1);
            assert!((y0 - y1).abs() <= 1);
            i += 1;
        }
        if n > 0 {
            let (xl, yl) = buf[n - 1];
            assert!((xl - yl).abs() <= 1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // A hand-rolled xorshift64 PRNG (same family as iban-check's dynamic fuzz test in the sibling
    // rust-delivery example) — no dependency on `rand`.
    struct Xorshift64(u64);
    impl Xorshift64 {
        fn next(&mut self) -> u64 {
            let mut x = self.0;
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            self.0 = x;
            x
        }
        fn next_u32_range(&mut self, lo: u32, hi_inclusive: u32) -> u32 {
            lo + (self.next() as u32) % (hi_inclusive - lo + 1)
        }
    }

    fn chebyshev(a: (i32, i32), b: (i32, i32)) -> i32 {
        (a.0 - b.0).abs().max((a.1 - b.1).abs())
    }

    #[test]
    fn octant_known_small_radii() {
        assert_eq!(octant_points(0), vec![(0, 0)]);
        assert_eq!(octant_points(1), vec![(1, 0)]);
        // This crate's own `fill_octant` output for r=5, pinned as a regression fixture (not
        // hand-derived from a textbook table): (5,0) (5,1) (5,2) (4,3) -- every one of these
        // points is independently checked for accuracy/adjacency by the property tests below and
        // by the bounded Kani proofs, so this test exists to catch a REGRESSION in the exact
        // sequence, not to be the sole authority on correctness.
        assert_eq!(octant_points(5), vec![(5, 0), (5, 1), (5, 2), (4, 3)]);
    }

    #[test]
    fn circle_points_r0_is_the_center() {
        // r=0's single octant point (0,0) is mirrored into `q0` (2 copies) and then into all four
        // quadrants (4x), for 8 total -- all the same point, which is correct: a radius-0 circle
        // is one pixel, however many times the construction revisits it.
        assert_eq!(circle_points(0), vec![(0, 0); 8]);
    }

    #[test]
    fn property_accuracy_over_many_radii() {
        let mut rng = Xorshift64(0xDEAD_BEEF_CAFE_F00D);
        for _ in 0..300 {
            let r = rng.next_u32_range(0, 2000);
            for &(dx, dy) in &circle_points(r) {
                assert!(accuracy_ok(r, dx, dy), "r={r} dx={dx} dy={dy}");
            }
        }
    }

    #[test]
    fn property_closed_8_connected_cycle_over_many_radii() {
        let mut rng = Xorshift64(0x1234_5678_9ABC_DEF0);
        for _ in 0..300 {
            let r = rng.next_u32_range(1, 2000); // r=0's single repeated point is covered separately
            let pts = circle_points(r);
            assert!(pts.len() >= 4, "r={r} produced too few points: {pts:?}");
            for w in pts.windows(2) {
                assert!(chebyshev(w[0], w[1]) <= 1, "r={r} gap between {:?} and {:?}", w[0], w[1]);
            }
            // wraparound: last point back to first.
            let first = pts[0];
            let last = *pts.last().unwrap();
            assert!(chebyshev(first, last) <= 1, "r={r} circle not closed: {first:?} .. {last:?}");
        }
    }

    #[test]
    fn property_8way_symmetry_as_a_set() {
        use std::collections::HashSet;
        let mut rng = Xorshift64(0x0BAD_C0DE_1234_5678);
        for _ in 0..200 {
            let r = rng.next_u32_range(1, 1000);
            let set: HashSet<(i32, i32)> = circle_points(r).into_iter().collect();
            for &(x, y) in &set {
                for &(u, v) in &[(x, y), (-x, y), (x, -y), (-x, -y), (y, x), (-y, x), (y, -x), (-y, -x)] {
                    assert!(set.contains(&(u, v)), "r={r} missing reflection ({u},{v}) of ({x},{y})");
                }
            }
        }
    }

    #[test]
    fn set_pixel_and_pixel_never_panic_far_out_of_bounds() {
        let mut c = Canvas::new(4, 4);
        for &(x, y) in &[
            (-1, -1),
            (100, 100),
            (i32::MIN, i32::MIN),
            (i32::MAX, i32::MAX),
            (2, -5),
            (-5, 2),
        ] {
            c.set_pixel(x, y, 7);
            assert_eq!(c.pixel(x, y), None);
        }
    }

    #[test]
    fn draw_circle_on_tiny_canvas_with_large_radius_does_not_panic() {
        // A radius far larger than the canvas, centered at an extreme coordinate -- every pixel
        // clips. The claim under test is purely "never panics"; drawing nothing is a correct,
        // honest outcome for a circle entirely off-canvas.
        let mut c = Canvas::new(3, 3);
        draw_circle(&mut c, i32::MAX - 2, i32::MAX - 2, 500, 9);
        draw_circle(&mut c, i32::MIN + 2, i32::MIN + 2, 500, 9);
        draw_circle(&mut c, 1, 1, 100_000, 9);
    }

    #[test]
    fn draw_circle_sets_pixels_matching_circle_points() {
        let r = 8u32;
        let (cx, cy) = (20, 20);
        let mut c = Canvas::new(41, 41);
        draw_circle(&mut c, cx, cy, r, 5);
        for (dx, dy) in circle_points(r) {
            assert_eq!(c.pixel(cx + dx, cy + dy), Some(5));
        }
        // Every set pixel is accounted for by some circle_points offset (no stray pixels).
        let expected: std::collections::HashSet<(i32, i32)> =
            circle_points(r).into_iter().map(|(dx, dy)| (cx + dx, cy + dy)).collect();
        for (x, y, v) in c.set_pixels() {
            assert_eq!(v, 5);
            assert!(expected.contains(&(x, y)), "unexpected set pixel at ({x},{y})");
        }
    }
}
