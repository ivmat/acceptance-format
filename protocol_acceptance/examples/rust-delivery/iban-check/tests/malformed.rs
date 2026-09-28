//! Rejection cases, one per [`IbanError`] variant — this is `validate`'s
//! primary contract: malformed input must be rejected, and rejected for
//! the stated reason (checked in the fixed order `validate`'s own doc
//! comment names: charset, country, length, checksum).

use iban_check::{validate, IbanError};

#[test]
fn bad_character_is_reported_for_a_symbol() {
    // '#' is not in [A-Z0-9]; length and country would otherwise be fine.
    assert_eq!(
        validate("GB82#WEST123456987654 32"),
        Err(IbanError::BadCharacter)
    );
}

#[test]
fn bad_character_is_reported_for_lowercase() {
    assert_eq!(
        validate("gb82west12345698765432"),
        Err(IbanError::BadCharacter)
    );
}

#[test]
fn unknown_country_numeric_prefix() {
    // Starts with digits, not letters -> UnknownCountry (charset passes: digits are legal
    // IBAN characters, just not a legal country-code prefix).
    assert_eq!(
        validate("1282WEST12345698765432"),
        Err(IbanError::UnknownCountry)
    );
}

#[test]
fn unknown_country_not_in_table() {
    // ZZ is a syntactically fine two-letter prefix, but not in our ten-country table.
    assert_eq!(
        validate("ZZ82WEST12345698765432"),
        Err(IbanError::UnknownCountry)
    );
}

#[test]
fn unknown_country_on_short_input() {
    // Fewer than 2 characters total: can't even read a country code.
    assert_eq!(validate("G"), Err(IbanError::UnknownCountry));
    assert_eq!(validate(""), Err(IbanError::UnknownCountry));
}

#[test]
fn bad_length_too_short_for_country() {
    // GB requires 22 characters; this is short by one.
    assert_eq!(
        validate("GB82WEST1234569876543"),
        Err(IbanError::BadLength)
    );
}

#[test]
fn bad_length_too_long_for_country() {
    // GB requires exactly 22; this is one character too many.
    assert_eq!(
        validate("GB82WEST123456987654321"),
        Err(IbanError::BadLength)
    );
}

#[test]
fn bad_checksum_on_otherwise_well_formed_input() {
    // Correct length, correct country, correct charset, wrong check digits.
    assert_eq!(
        validate("GB00WEST12345698765432"),
        Err(IbanError::BadChecksum)
    );
}

#[test]
fn each_error_kind_is_independently_reachable() {
    // A cheap coherence guard: the four fixtures above between them must
    // exercise all four variants, or a future refactor could silently
    // stop reaching one of them without any single test failing.
    use std::collections::HashSet;
    let mut seen: HashSet<IbanError> = HashSet::new();
    seen.insert(validate("GB82#WEST123456987654 32").unwrap_err());
    seen.insert(validate("1282WEST12345698765432").unwrap_err());
    seen.insert(validate("GB82WEST1234569876543").unwrap_err());
    seen.insert(validate("GB00WEST12345698765432").unwrap_err());
    assert_eq!(seen.len(), 4, "expected all four IbanError variants, got {seen:?}");
}
