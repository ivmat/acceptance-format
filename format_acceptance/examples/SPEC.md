---
type: reference
digest: Version v1 of the illustrative example-lib specification, defining non-panicking addition and division by zero handling.
---

# example-lib specification — v1

This specification defines the two clauses used by `minimal.acceptance.toml`.
The manifest illustrates one evidenced claim and one explicit gap; it is not a
certificate for an implementation supplied with this example.

## S-1. Addition does not panic

For every pair of `i32` inputs, `src/lib.rs::add` must return without panicking,
including when the mathematical sum lies outside the `i32` range.
This clause imposes no requirement on the returned value.

## S-2. Division rejects a zero divisor

For every `i32` dividend and a zero divisor, `src/lib.rs::div` must return `Err`.
The manifest records this requirement as a gap, not as a verified property.
