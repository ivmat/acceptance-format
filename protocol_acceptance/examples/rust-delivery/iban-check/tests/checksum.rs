//! Checksum acceptance tests: known-valid public IBAN examples, and a
//! hand-rolled property test (no dependency on a crate PRNG — see
//! `Lcg` below) that flipping one digit of a known-valid IBAN always
//! changes the verdict. That property is the falsifiability witness this
//! crate's consumer cares about: a checksum check that accepts everything
//! is worthless, and this test is what shows it does not.

use iban_check::{validate, IbanError};

/// Ten publicly documented, independently verifiable valid IBANs (Wikipedia
/// "International Bank Account Number" examples and national banking-body
/// specimens), one per country in `iban_check`'s table.
const KNOWN_VALID: &[&str] = &[
    "GB82 WEST 1234 5698 7654 32",
    "GB29 NWBK 6016 1331 9268 19",
    "DE89 3704 0044 0532 0130 00",
    "BE68 5390 0754 7034",
    "NL91 ABNA 0417 1643 00",
    "CH93 0076 2011 6238 5295 7",
    "IT60 X054 2811 1010 0000 0123 456",
    "ES91 2100 0418 4502 0005 1332",
    "FR14 2004 1010 0505 0001 3M02 606",
    "AT61 1904 3002 3457 3201",
];

#[test]
fn all_known_valid_ibans_pass() {
    for iban in KNOWN_VALID {
        assert_eq!(validate(iban), Ok(()), "expected {iban:?} to validate");
    }
}

#[test]
fn a_wrong_checksum_is_rejected() {
    // GB82 WEST ... with the check digits corrupted (82 -> 83); length and
    // charset stay valid, so this isolates BadChecksum specifically.
    let corrupted = "GB83 WEST 1234 5698 7654 32";
    assert_eq!(validate(corrupted), Err(IbanError::BadChecksum));
}

// --------------------------------------------------------------------------
// Hand-rolled LCG (no external PRNG dependency, per the no-dependency rule)
// --------------------------------------------------------------------------

/// A minimal linear congruential generator (Numerical Recipes constants),
/// good enough for picking test indices/positions — NOT cryptographic, and
/// not meant to be.
struct Lcg {
    state: u64,
}

impl Lcg {
    fn new(seed: u64) -> Self {
        Lcg { state: seed ^ 0x9E3779B97F4A7C15 }
    }

    fn next_u64(&mut self) -> u64 {
        // Numerical Recipes LCG: state_{n+1} = state_n * a + c (mod 2^64).
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    fn next_range(&mut self, bound: usize) -> usize {
        (self.next_u64() % (bound as u64)) as usize
    }
}

/// Digits are the characters an IBAN's check-digit/BBAN numeric positions
/// use; flipping to a DIFFERENT digit than the original guarantees an
/// actual change (never a same-value "flip" that would defeat the test).
fn flip_one_digit(iban_no_spaces: &str, mut lcg: Lcg) -> String {
    let chars: Vec<char> = iban_no_spaces.chars().collect();
    // Find candidate positions that are ASCII digits (avoid flipping into
    // the letters of a BBAN like WEST/NWBK, which would still be a valid
    // perturbation but is less legible as "one digit flipped").
    let digit_positions: Vec<usize> = chars
        .iter()
        .enumerate()
        .filter(|(_, c)| c.is_ascii_digit())
        .map(|(i, _)| i)
        .collect();
    assert!(!digit_positions.is_empty(), "expected at least one digit");
    let pick = digit_positions[lcg.next_range(digit_positions.len())];
    let original = chars[pick];
    let original_digit = original.to_digit(10).unwrap();
    // pick a different digit (1..=9 offset, mod 10) so it is guaranteed distinct
    let offset = 1 + lcg.next_range(9) as u32;
    let new_digit = (original_digit + offset) % 10;
    let mut out: Vec<char> = chars;
    out[pick] = char::from_digit(new_digit, 10).unwrap();
    out.into_iter().collect()
}

#[test]
fn flipping_one_digit_of_a_valid_iban_always_changes_the_verdict() {
    // Deterministic but not hand-picked: a fixed seed drives 200 trials
    // across the 10 known-valid IBANs, each with a different, LCG-chosen
    // digit position flipped to a different digit. Every single trial must
    // turn a Ok(()) IBAN into an Err(_) IBAN — this is the "checksum
    // actually decides something" witness (0.1-DRAFT.md §4.1 terms), not
    // merely "checksum returns Ok on the examples we typed in".
    let mut lcg = Lcg::new(0xC0FFEE_u64);
    let mut trials = 0usize;
    for iban in KNOWN_VALID {
        let no_spaces: String = iban.chars().filter(|&c| c != ' ').collect();
        assert_eq!(
            validate(iban),
            Ok(()),
            "fixture {iban:?} must itself be valid before we can test perturbations of it"
        );
        for _ in 0..20 {
            let seed = lcg.next_u64();
            let flipped = flip_one_digit(&no_spaces, Lcg::new(seed));
            assert_ne!(
                flipped, no_spaces,
                "the perturbation must actually change the string"
            );
            let verdict = validate(&flipped);
            assert!(
                verdict.is_err(),
                "flipping one digit of a valid IBAN must break it: {no_spaces:?} -> {flipped:?} still validated as {verdict:?}"
            );
            trials += 1;
        }
    }
    assert_eq!(trials, KNOWN_VALID.len() * 20);
}
