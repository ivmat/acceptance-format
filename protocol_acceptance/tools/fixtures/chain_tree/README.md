---
type: reference
digest: Source tree for the protocol chain fixtures; edge packages and decision stores are generated at test time.
---

# Checked stacking fixture

`paint-app` calls `raster-draw`, which calls `geom-math`. All three crates are released
together at one commit. The example cannot attribute a defect observed at the top to a
layer by swapping independent versions, and claims no such attribution.

The fixture runner creates full specification/package/decision triples for each edge.
The accepted artifacts are these edge packages. The source tree contains no nested git
repository; the checkout tests create a temporary repository with hooks disabled and
commit the edge packages after the subject commit.

Run `python3 protocol_acceptance/tools/fixtures/chain_cases.py` from the repository root.
