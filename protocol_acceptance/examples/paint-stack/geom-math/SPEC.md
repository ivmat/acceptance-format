---
type: reference
digest: geom-math's own producer-stated spec clauses (S-1, S-2), cited by its intrinsic acceptance.toml [spec] table. Matches the doc comments on isqrt/dist2 in src/lib.rs exactly; this file exists only so [spec] has a real document to point at, per the acceptance protocol's convention (protocol.md sec 3, "the governing document").
---

# geom-math — producer spec clauses

S-1. `isqrt(n: u32) -> u32` returns the floor integer square root of `n`: the unique `r` such that
`r*r <= n < (r+1)*(r+1)`, for every `u32` value of `n` (the full domain, not a bounded slice of
it), and never panics or overflows.

S-2. `dist2(dx: i32, dy: i32) -> u64` returns the squared Euclidean distance `dx*dx + dy*dy`
without ever panicking or overflowing, for every `i32` pair `(dx, dy)` including the extremes
(`i32::MIN`, `i32::MAX`).

The `dist2_never_overflows_full_domain` Kani harness proves only panic/overflow freedom.
The squared-distance postcondition has known-value tests, not a Kani correctness proof.
