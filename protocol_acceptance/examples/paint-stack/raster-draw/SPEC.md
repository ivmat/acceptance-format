---
type: reference
digest: raster-draw's own producer-stated spec clauses (S-1..S-4), cited by its intrinsic acceptance.toml [spec] table. Matches raster-draw's own doc comments (fill_octant, circle_points, Canvas::set_pixel) exactly.
---

# raster-draw — producer spec clauses

S-1. **Accuracy.** Every point `circle_points(r)` returns is within 0.5 of the true radius `r` from
the center: `accuracy_ok(r, dx, dy)` holds for every returned `(dx, dy)`.

S-2. **Closed, 8-connected, no gaps.** `circle_points(r)` returns a single cyclic sequence:
consecutive points (wraparound included) are Chebyshev-adjacent (differ by at most 1 in each
coordinate).

S-3. **8-way symmetry.** The set of points `circle_points(r)` returns is closed under all eight
symmetries of the square: `(x,y) -> (-x,y), (x,-y), (-x,-y), (y,x), (-y,x), (y,-x), (-y,-x)`.

S-4. **Clipping never panics.** `Canvas::set_pixel`/`Canvas::pixel` never panic for any `i32`
coordinate, in or out of bounds, and `draw_circle` never panics for any `(cx, cy, r)`, including
`i32` extremes and radii far larger than the canvas.

Rendered-canvas accuracy, symmetry and closedness apply only when the entire circle fits:
`cx-r >= 0`, `cy-r >= 0`, `cx+r < width`, `cy+r < height`. The library still clips other
circles; S-4 describes that behavior, without promising complete-circle geometry after clipping.
Kani proves octant accuracy and intra-octant/mirrored-seam adjacency only for `r <= 6`.
Full-circle accuracy and closedness are property-tested, not Kani-proved.
