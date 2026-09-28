//! Hand-rolled fuzz loop: `validate` must never panic on ANY input,
//! including invalid UTF-8 byte strings, wildly wrong lengths, and mixed
//! garbage. This is the dynamic-evidence companion to the Kani harness in
//! `src/lib.rs` (`#[cfg(kani)] mod verification`) — the same property,
//! checked over a much larger but non-exhaustive sample instead of proved.
//!
//! No external fuzzing crate: a small xorshift64 generator is hand-rolled
//! (deterministic, seeded, dependency-free) rather than pulling in `arbitrary`
//! or `quickcheck`.

use iban_check::validate;

/// xorshift64 — a minimal, fast, non-cryptographic PRNG.
struct Xorshift64 {
    state: u64,
}

impl Xorshift64 {
    fn new(seed: u64) -> Self {
        // xorshift64 is undefined at state 0; guarantee a nonzero seed.
        Xorshift64 { state: if seed == 0 { 0xDEAD_BEEF_CAFE_F00D } else { seed } }
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.state = x;
        x
    }

    fn next_byte(&mut self) -> u8 {
        (self.next_u64() & 0xFF) as u8
    }

    fn next_len(&mut self, max: usize) -> usize {
        (self.next_u64() as usize) % (max + 1)
    }
}

const TRIALS: usize = 20_000;
const MAX_LEN: usize = 128; // well past any real IBAN (34 bytes) and past validate's own tables

#[test]
fn random_byte_strings_never_panic() {
    let mut rng = Xorshift64::new(0x5EED_1234_ABCD_EF01);
    let mut utf8_trials = 0usize;
    let mut non_utf8_trials = 0usize;

    for _ in 0..TRIALS {
        let len = rng.next_len(MAX_LEN);
        let bytes: Vec<u8> = (0..len).map(|_| rng.next_byte()).collect();

        match std::str::from_utf8(&bytes) {
            Ok(s) => {
                utf8_trials += 1;
                // Must not panic; result is not otherwise constrained here.
                let _ = validate(s);
            }
            Err(_) => {
                // Not a valid &str at all — validate's signature makes this
                // uncallable directly; count it so the run's coverage over
                // "random bytes broadly" is visible, and additionally drive
                // validate with the longest valid UTF-8 PREFIX of the
                // invalid sequence, which IS a legal &str and a case worth
                // covering (truncated multi-byte sequences are exactly
                // where naive byte-slicing panics).
                non_utf8_trials += 1;
                if let Err(e) = std::str::from_utf8(&bytes) {
                    let valid_up_to = e.valid_up_to();
                    let prefix = std::str::from_utf8(&bytes[..valid_up_to]).unwrap();
                    let _ = validate(prefix);
                }
            }
        }
    }

    assert_eq!(utf8_trials + non_utf8_trials, TRIALS);
    // Both branches should fire across 20,000 random trials over the full
    // byte range — otherwise this "fuzz loop" would quietly only be
    // exercising one of them.
    assert!(utf8_trials > 0, "expected at least some valid-UTF-8 samples");
    assert!(non_utf8_trials > 0, "expected at least some non-UTF-8 samples");
}

#[test]
fn adversarial_ascii_near_miss_lengths_never_panic() {
    // Deliberately walk every length from 0 to 40 with all-'A' and all-'0'
    // bodies (near the real length table's boundaries, where an off-by-one
    // slice bound is most likely to panic).
    for len in 0..=40 {
        let letters: String = std::iter::repeat('A').take(len).collect();
        let digits: String = std::iter::repeat('0').take(len).collect();
        let mixed: String = (0..len)
            .map(|i| if i % 2 == 0 { 'A' } else { '1' })
            .collect();
        let _ = validate(&letters);
        let _ = validate(&digits);
        let _ = validate(&mixed);
    }
}

#[test]
fn empty_and_whitespace_only_never_panic() {
    let _ = validate("");
    let _ = validate(" ");
    let _ = validate("    ");
    let _ = validate("\u{0}");
    let _ = validate("😀😀😀");
}
