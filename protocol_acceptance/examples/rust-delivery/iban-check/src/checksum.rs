//! ISO 7064 mod-97-10 checksum, computed incrementally (no bignum).
//!
//! The classic description of the algorithm says "move the first four
//! characters to the end, expand letters to two decimal digits (A=10 ..
//! Z=35), interpret the whole thing as one giant decimal integer, and take
//! it mod 97". A real IBAN's expanded digit string can be ~70 decimal
//! digits long, well past `u64`, so this module never forms that integer:
//! it folds each digit into a running remainder as it goes
//! (`remainder = (remainder * 10 + digit) % 97`), which is arithmetically
//! identical to reducing the full number mod 97 (modular arithmetic
//! distributes over the digit-by-digit long-division construction of the
//! decimal value) and never needs more than a `u32`.
//!
//! Operates on `&[u8]` rather than `&str` — see `syntax.rs`'s doc comment
//! for why.

/// Computes ISO 7064 mod-97-10 over `rearranged` (the already-rotated
/// bytes: BBAN + check digits + country code, per [`crate::validate`]'s
/// rearrangement step) and returns `true` iff the remainder is exactly 1,
/// the canonical "valid" result for IBAN's mod-97-10 check.
///
/// `rearranged` MUST already have been validated as containing only
/// `[A-Z0-9]` (see [`crate::syntax::is_iban_byte`]) — a byte outside that
/// set is treated here as digit value 0, which is safe (the function
/// cannot panic or misbehave) but is meaningless as a checksum, which is
/// exactly why [`crate::validate`] always runs the charset check first.
pub(crate) fn mod97_is_valid(rearranged: &[u8]) -> bool {
    let mut remainder: u32 = 0;
    for &b in rearranged {
        if b.is_ascii_digit() {
            let d = (b - b'0') as u32;
            remainder = (remainder * 10 + d) % 97;
        } else if b.is_ascii_uppercase() {
            // A=10 .. Z=35, expanded as two decimal digits.
            let value = (b - b'A') as u32 + 10;
            let tens = value / 10;
            let ones = value % 10;
            remainder = (remainder * 10 + tens) % 97;
            remainder = (remainder * 10 + ones) % 97;
        }
        // else: not an IBAN byte; contributes nothing (see doc comment).
    }
    remainder == 1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_valid_rearrangement_reduces_to_one() {
        // GB82 WEST 1234 5698 7654 32, rearranged (BBAN + check digits + country)
        let rearranged = b"WEST12345698765432GB82";
        assert!(mod97_is_valid(rearranged));
    }

    #[test]
    fn a_flipped_digit_breaks_it() {
        let good = b"WEST12345698765432GB82";
        let bad = b"WEST12345698765412GB82"; // one digit flipped (3->1)
        assert!(mod97_is_valid(good));
        assert!(!mod97_is_valid(bad));
    }

    #[test]
    fn empty_slice_is_zero_remainder_not_one() {
        assert!(!mod97_is_valid(b""));
    }
}
