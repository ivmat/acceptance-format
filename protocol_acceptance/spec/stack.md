---
type: reference
digest: Draft specification of the neighbouring protocols that compose with acceptance.
---

# The protocol stack around acceptance — specified, not built (DRAFT, 2026-09-16)

`protocol.md` §9 says how the acceptance protocol composes with each neighbour. This note gives the
neighbours that do not yet exist as typed protocols their minimal shape, so the acceptance protocol
can be applied without waiting for them, and so nobody builds a second obligation or authority
model by accident. Everything here is generic (no artifact or tool vocabulary); the same
projection mechanism as `protocol.md` §6.6 applies.

## 1. Work contract — the envelope whose *verify* step is the acceptance protocol

Roles: **initiator** (the consumer-to-be), **participant** (the producer-to-be). Acts, taken from
FIPA Contract Net / Request with two additions, every message carrying `conversation_id`,
`in_reply_to`, `reply_by`, `idempotency_key` (= payload digest), `base_digest` and `by`:

| act | from → to | carries | note |
|---|---|---|---|
| `cfp` / `request` | initiator → participant(s) | the acceptance **contract** (draft or issued) + delivery constraints | `reply_by` = proposal deadline; late proposals auto-rejected |
| `propose` / `refuse` | participant → initiator | a proposal referencing the contract id + hash (or a counter-draft with `issued_by = producer`) | a counter-draft binds only after `ratify` |
| `accept-proposal` / `reject-proposal` | initiator → participant | the contract in `issued`/`ratified` status | binding from here (FIPA: "the proposal is binding once accepted") |
| `extension-request` (new) | participant → initiator | a new `reply_by` and reason | initiator answers `agree` / `refuse`; no silent slip |
| `inform-result` (= deliver) | participant → initiator | the artifact identity + the **package** | idempotent by package hash |
| `verify` (new) | initiator (or its verifier) | the **decision** | this act IS `protocol.md` §5–§6 |
| `inform-done` (= close) | initiator → participant | the decision id and verdict | `accepted` closes; `accepted-with-conditions` closes with minted obligations; `rejected` / `evidence-requested` re-enter at `inform-result` |
| `cancel` | either | reason | FIPA cancel meta-protocol; answered `inform-done` or `failure` |
| `failure` | participant → initiator | reason | no package will come |

State per conversation: `open → proposed → agreed → delivered → verified → closed | cancelled |
failed`. Safety: at most one `agreed` contract per conversation; liveness: every `delivered` reaches
`verified` or `cancelled` within `reply_by`. A Scribble/nuscr or P model is the place to check
these once the protocol is built; the table above is enough to apply the acceptance protocol by
hand (an existing minimal envelope already applies this shape to a one-requirement contract).

## 2. Authority and grant — a reference, not a model

The contract's `[acceptance].authority` and the decision's `issuer` are strings that must resolve
outside the protocol: internally to an applicable grant or authority record (an owner-approved
authority for consequential artifacts; a deterministic oracle for auto-acceptable ones); externally to a signer
identity (DSSE key id, SPIFFE id, X.509 subject) plus, where a verifier acts for the consumer, an
RFC 8693 `act` chain. The one rule the protocol itself enforces is P5 (issuer ≠ producer, issuer
= authority). Non-widening delegation (a verifier may not grant itself more than the consumer
granted) is a rule of whatever authority/grant model a consumer runs, inherited here rather than
redefined.

## 3. Consequential-effect gate — takes a decision as input

A consequential-effect gate — a consumer's own pipeline of propose → check authority + evidence →
allow / condition / deny / escalate → execute → attest. An acceptance decision is *evidence* to that gate: "publish this artifact" is
allowed only with an **effect-eligible** decision (`protocol.md` §5.0a: valid, current, unexpired,
under a `final`-phase contract, `provisional` absent or false, verdict `accepted` — or
`accepted-with-conditions` only where the gate's policy allows outstanding conditions) bound to
the exact commit being published. A one-requirement receipt gate is a degenerate instance of the
same pattern. The gate is
not part of the acceptance protocol and never issues decisions.

## 4. Transaction and compensation — deferred

When an acceptance triggers effects across systems (merge, publish, pay), the effect gate's steps
form a saga: each step declares its compensation before executing, or the gate escalates;
messages are keyed by idempotency key + payload digest (409 in-flight / 422 mismatch / 400
missing); a journal entry precedes each effect (outbox). No acceptance-protocol object changes.

## 5. Offline reconciliation — built into the documents

A verifier that takes contract + package offline and returns a decision later presents `[binds]`;
the consumer compares: all equal → the decision stands as a valid record (effect still needs §5.0a); only inputs outside every relied-on
record's declared input set changed → the decision is re-bound (a new decision document citing the
old as `supersedes`, with the change-impact table attached); any bound hash or a declared input
changed → `stale`, re-assess. This is `protocol.md` §8 applied to the decision itself.

## 6. Context expansion and improvement experiments — out of scope

Both are real (a context-expansion instance of the §1 work envelope; an improvement ledger); neither touches acceptance semantics.
Context expansion is a grant lifecycle (request → policy → grant/deny → measure); improvement is
an observation → hypothesis → experiment → promote loop over acceptance records as its data.
Recorded here so they are not mistaken for gaps in this protocol.
