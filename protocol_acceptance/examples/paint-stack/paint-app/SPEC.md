---
type: reference
digest: paint-app's own producer-stated spec clauses (S-1..S-4) for its INTRINSIC (producer-only) acceptance.toml. The separate consumer-facing requirements live in acceptance-specification.toml, representing the simulated consumer role.
---

# paint-app — producer spec clauses (intrinsic)

**Domain (all of S-2..S-4): circles fully inside the canvas only** — `cx >= r` and `cy >= r`. A
request outside this domain is rejected outright (part of S-1's "malformed invocation" set), never
silently clipped to an open, asymmetric arc (cross-vendor review 2026-09-26, Blocker #2).

S-1. **CLI robustness.** `paint circle --cx N --cy N --r N --out FILE.ppm` parses any well-formed,
in-domain invocation regardless of flag order, and rejects every malformed or out-of-domain
invocation (missing flags, non-numeric values, unknown subcommand/flags, duplicated flags, empty
output path, or a circle that does not fit entirely inside the auto-sized canvas) with a nonzero
exit code and a clean error message on stderr — never a panic.

S-2. **Output accuracy.** For every circle fully inside the canvas, every ink pixel ACTUALLY FOUND
in the output PPM file (by an exhaustive scan of the real file bytes) is within 0.5 of the declared
radius from the declared center — checked by a formula re-derived from scratch in `paint-app`'s own
tests, independently of `raster-draw`'s `circle_points`/`accuracy_ok`, over a disclosed domain (see
`src/lib.rs`'s `DOMAINS`: 8 (cx, cy, r) combinations, radii 0..=30; the same tuples run through the binary in tests/cli.rs).

S-3. **Output symmetry.** For every circle fully inside the canvas, the ink pixels ACTUALLY FOUND in
the output PPM file are 8-way symmetric about the declared center — checked on the scanned pixel
set itself, not on what the renderer claims it drew, over the same disclosed domain as S-2.

S-4. **Output closedness.** For every circle fully inside the canvas, the ink pixels ACTUALLY FOUND
in the output PPM file form exactly one 8-connected component (a real flood-fill from any one ink
pixel reaches every other), and an angularly ordered cycle with Chebyshev-adjacent consecutive pixels including wraparound — checked over the same disclosed domain as S-2. This is
NOT Kani-proved at the paint-app level (contrast `raster-draw`'s own S-2, which IS Kani-proved for
`fill_octant`'s intra-octant adjacency at radius <= 6): here it uses independent flood-fill and cyclic-adjacency tests, over the disclosed finite domain.
