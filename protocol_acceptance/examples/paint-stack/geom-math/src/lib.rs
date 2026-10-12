#![forbid(unsafe_code)]
//! `geom-math` — the bottom layer of the paint-stack example (`geom-math` -> `raster-draw` ->
//! `paint-app`). Two primitives, both proved over their FULL input domain by Kani (no bounded
//! narrowing needed — see each function's doc comment for why the proof is tractable):
//!
//! - [`isqrt`]: floor integer square root of a `u32`, via the classic "digit-by-digit" bit
//!   algorithm (Wikipedia "Integer square root", the binary variant). No multiplication inside the
//!   loop — only shifts, comparison and subtraction — which is why CBMC can verify it over the
//!   full `u32` domain in a fixed, small number of loop iterations (16) rather than needing a
//!   Newton-style iteration count that depends on the input.
//! - [`dist2`]: squared Euclidean distance between two integer offsets, overflow-free by
//!   construction (widens to `u64` before squaring, so even `i32::MIN` on both axes cannot
//!   overflow — see the function's doc comment for the exact bound).
//!
//! No dependencies, no heap allocation, no `unsafe`.

/// Floor integer square root: the unique `r` such that `r*r <= n < (r+1)*(r+1)`.
///
/// **Algorithm.** The classic bit-by-bit / "digit by digit" integer square root: process the
/// input two bits at a time, from the most significant pair down, using `bit` as a probe that
/// starts just below the highest set pair of bits in `n` and shifts right by two each iteration.
/// This is Kani-friendly by construction — no multiplication in the loop at all (`res`, `bit` and
/// `n` are only shifted, compared and subtracted), and the loop runs at most 16 times for a `u32`
/// regardless of the symbolic value of `n` (16 = 32 bits / 2 bits per iteration), so the proof
/// below (`isqrt_correct_full_domain`) covers the ENTIRE `u32` domain, not a bounded slice of it.
///
/// Never panics, never overflows (`res + bit` cannot exceed `res`'s and `bit`'s combined
/// contribution to a value already known to be `<= n <= u32::MAX`; proved alongside correctness
/// below via Kani's default arithmetic-overflow checks).
pub fn isqrt(n: u32) -> u32 {
    let mut res: u32 = 0;
    let mut bit: u32 = 1u32 << 30; // the highest even bit position for a 32-bit value
    while bit > n {
        bit >>= 2;
    }
    let mut n = n;
    while bit != 0 {
        if n >= res + bit {
            n -= res + bit;
            res = (res >> 1) + bit;
        } else {
            res >>= 1;
        }
        bit >>= 2;
    }
    res
}

/// Squared Euclidean distance between the integer offset `(dx, dy)` and the origin, i.e.
/// `dx*dx + dy*dy` computed without ever overflowing.
///
/// **Why this cannot overflow, for ANY `i32` `dx`/`dy` including `i32::MIN`.** Each magnitude is
/// widened to `u64` (`unsigned_abs()` handles `i32::MIN` correctly — its magnitude, `2^31`, fits
/// in a `u32` and therefore in a `u64` — a plain `.abs()` would itself overflow/panic on
/// `i32::MIN`, which is exactly why `unsigned_abs` is used instead). The largest possible
/// magnitude is `2^31`, so the largest possible squared term is `(2^31)^2 = 2^62`, and the sum of
/// two such terms is at most `2^63`, which fits in a `u64` (max `2^64 - 1`) with room to spare.
/// Proved for the full `i32 x i32` domain below (`dist2_never_overflows_full_domain`).
pub fn dist2(dx: i32, dy: i32) -> u64 {
    let a = dx.unsigned_abs() as u64;
    let b = dy.unsigned_abs() as u64;
    a * a + b * b
}

#[cfg(kani)]
mod verification {
    //! Both harnesses below cover the FULL domain of their function — no `KANI_BOUND`-style
    //! narrowing was needed (contrast `raster-draw`'s harnesses, which bound the circle radius).
    //! See each function's doc comment for why: `isqrt`'s loop count is fixed at 16 regardless of
    //! `n`, and `dist2`'s widening makes overflow structurally impossible for any `i32` input.

    /// `isqrt` is correct for every `u32`: `r*r <= n < (r+1)*(r+1)`, computed in `u64` to state
    /// the upper bound without itself overflowing (the postcondition's own arithmetic, not
    /// `isqrt`'s).
    #[kani::proof]
    #[kani::unwind(18)]
    fn isqrt_correct_full_domain() {
        let n: u32 = kani::any();
        let r = crate::isqrt(n);
        let r64 = r as u64;
        let n64 = n as u64;
        assert!(r64 * r64 <= n64);
        assert!(n64 < (r64 + 1) * (r64 + 1));
    }

    /// `dist2` never panics/overflows for any `i32` pair, full domain (no `kani::assume` at all).
    #[kani::proof]
    fn dist2_never_overflows_full_domain() {
        let dx: i32 = kani::any();
        let dy: i32 = kani::any();
        let _ = crate::dist2(dx, dy);
    }

    // A third proof (`dist2`'s sign-symmetry identity, `dist2(dx,dy) == dist2(-dx,dy) == ...`)
    // was attempted and DROPPED: CBMC did not return within several minutes on this machine (the
    // two multiplications on each side of four `assert_eq!`s over the full i32xi32 domain, rather
    // than one inequality, appears to cost CBMC much more than either proof above). It is not one
    // of this crate's weighted claims (raster-draw's own 8-way-symmetry property test covers the
    // consequence this would have supported), so it was cut rather than left to run unbounded —
    // see the example README's "what was simplified" section.

}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn isqrt_known_values() {
        assert_eq!(isqrt(0), 0);
        assert_eq!(isqrt(1), 1);
        assert_eq!(isqrt(3), 1);
        assert_eq!(isqrt(4), 2);
        assert_eq!(isqrt(8), 2);
        assert_eq!(isqrt(9), 3);
        assert_eq!(isqrt(15), 3);
        assert_eq!(isqrt(16), 4);
        assert_eq!(isqrt(u32::MAX), 65535); // 65535^2 = 4294836225 <= u32::MAX < 65536^2
    }

    #[test]
    fn isqrt_exhaustive_small_range() {
        // A dynamic double-check over a real (non-symbolic) range, independent of the Kani proof
        // above — cheap enough to run on every `cargo test`, and a second, differently-shaped
        // witness of the same property (protocol_acceptance profile guidance: prefer more than
        // one independent evidence shape per weighted claim where it is cheap to add).
        for n in 0u32..200_000 {
            let r = isqrt(n);
            assert!((r as u64) * (r as u64) <= (n as u64), "n={n} r={r}");
            assert!((n as u64) < (r as u64 + 1) * (r as u64 + 1), "n={n} r={r}");
        }
    }

    #[test]
    fn dist2_known_values() {
        assert_eq!(dist2(0, 0), 0);
        assert_eq!(dist2(3, 4), 25);
        assert_eq!(dist2(-3, 4), 25);
        assert_eq!(dist2(-3, -4), 25);
        assert_eq!(dist2(i32::MIN, 0), (1u64 << 31) * (1u64 << 31));
        assert_eq!(dist2(i32::MIN, i32::MIN), 2 * (1u64 << 31) * (1u64 << 31));
    }

    #[test]
    fn dist2_extremes_do_not_panic() {
        // The whole point of dist2's widening: these must not panic (a naive i32 multiply would).
        let _ = dist2(i32::MIN, i32::MIN);
        let _ = dist2(i32::MAX, i32::MAX);
        let _ = dist2(i32::MIN, i32::MAX);
    }
}

