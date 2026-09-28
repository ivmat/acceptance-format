"""Per-profile protocol selftest fixture chains (revision).

Each module here owns one bound profile's Instance-rung fixture data and case chain — moved out
of `acceptance_protocol.py`'s embedded `--selftest` so the Class-rung tool names no profile
vocabulary directly (protocol.md P11). Every module exposes `run() -> list[tuple[str, bool,
object]]`, the raw `(case name, ok, detail)` list; `acceptance_protocol.run_selftest` aggregates
every bound chain and does the one print/exit.
"""
