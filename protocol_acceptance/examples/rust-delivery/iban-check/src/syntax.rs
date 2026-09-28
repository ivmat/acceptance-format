//! Country-code -> IBAN length table and character-set primitives (ISO 13616 §5).
//!
//! Operates on raw bytes rather than `&str`/`char`, deliberately: [`validate`]
//! never needs Unicode semantics (IBAN characters are always `[A-Z0-9]`), and
//! working in byte space avoids `core`'s `&str`-slicing and UTF-8-boundary
//! machinery, which is expensive for the Kani proof in `src/lib.rs` to
//! symbolically explore even on branches that never fire (see that module's
//! doc comment for the measured difference).
//!
//! The table below is a REPRESENTATIVE SUBSET of the ISO 13616 registry (ten
//! SEPA/eurozone-adjacent countries), not the complete list — an IBAN whose
//! country code is not one of these ten returns
//! [`crate::IbanError::UnknownCountry`], which is a statement about this
//! crate's table, not about whether the code is a real ISO 13616 country.

/// Returns the official IBAN length (in bytes, after space-stripping) for a
/// two-letter, upper-case ISO 3166-1 alpha-2 country code, for the subset of
/// countries this crate knows.
pub(crate) fn country_length(country: [u8; 2]) -> Option<usize> {
    match &country {
        b"AD" => Some(24), // Andorra
        b"AT" => Some(20), // Austria
        b"BE" => Some(16), // Belgium
        b"CH" => Some(21), // Switzerland
        b"DE" => Some(22), // Germany
        b"ES" => Some(24), // Spain
        b"FR" => Some(27), // France
        b"GB" => Some(22), // United Kingdom
        b"IT" => Some(27), // Italy
        b"NL" => Some(18), // Netherlands
        _ => None,
    }
}

/// True iff `b` is one of the bytes an IBAN body may contain after
/// space-stripping: `A`-`Z` or `0`-`9`. Lower-case letters are deliberately
/// NOT accepted — an IBAN is printed upper-case, and silently folding case
/// would let two visually different strings validate identically.
pub(crate) fn is_iban_byte(b: u8) -> bool {
    b.is_ascii_uppercase() || b.is_ascii_digit()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_countries_have_known_lengths() {
        assert_eq!(country_length(*b"GB"), Some(22));
        assert_eq!(country_length(*b"DE"), Some(22));
        assert_eq!(country_length(*b"BE"), Some(16));
        assert_eq!(country_length(*b"FR"), Some(27));
    }

    #[test]
    fn unknown_country_is_none() {
        assert_eq!(country_length(*b"ZZ"), None);
        assert_eq!(country_length(*b"US"), None); // real country, not in our table
    }

    #[test]
    fn charset_accepts_only_upper_and_digit() {
        assert!(is_iban_byte(b'A'));
        assert!(is_iban_byte(b'9'));
        assert!(!is_iban_byte(b'a'));
        assert!(!is_iban_byte(b' '));
        assert!(!is_iban_byte(b'-'));
        assert!(!is_iban_byte(0xE9)); // a raw non-ASCII byte (e.g. from 'e' with an accent in UTF-8)
    }
}
