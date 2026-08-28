# examples/rs-verified-der

This directory is the worked example. It is based on the format's real first subject, the
rs-verified-der crate.

`acceptance.toml` is an illustrative manifest. It is marked `illustrative = true`, and its evidence
record pointers are deliberately left unresolved — it is here to teach the format's shape, not to
certify anything.

`ENVELOPE.md` is the frozen legacy carrier that preceded the TOML format. It is kept here as
provenance and is retired: the TOML format is the authority now (ADR-001).

The subject's real, live manifest ships with the rs-verified-der repo itself, not here.
