#!/usr/bin/env bash
# Fail on every unexpected nonzero; generation checks expected-red controls internally.
set -euo pipefail
cd "$(dirname "$0")"
REPO="../../.."
PROTOCOL_TOOL="$REPO/protocol_acceptance/tools/acceptance_protocol.py"
trap 'find . -type d -name target -prune -exec rm -rf {} +' EXIT

python3 gen_stack.py
for f in geom-math/acceptance.toml raster-draw/acceptance.toml paint-app/acceptance.toml geom-math/acceptance/AC-GEOM-0001/acceptance.toml raster-draw/acceptance/AC-RASTER-0001/acceptance.toml paint-app/acceptance-package.toml; do
  python3 "$REPO/format_acceptance/tools/check_acceptance.py" --strict --strict-weight --root "$REPO" "$f"
  python3 "$REPO/format_acceptance/tools/check_core.py" --strict --strict-weight --root "$REPO" "$f"
done
COMMIT=$(python3 -c 'import tomllib; print(tomllib.load(open("paint-app/acceptance-package.toml", "rb"))["subject"]["commit"])')
CHAIN=(--root "$REPO" --store ochre-accepted=store/ochre-accepted --tree "$COMMIT=$REPO")
for base in geom-math/acceptance/AC-GEOM-0001 raster-draw/acceptance/AC-RASTER-0001 paint-app; do
  package="$base/acceptance.toml"
  if [[ "$base" == paint-app ]]; then package="$base/acceptance-package.toml"; fi
  python3 "$PROTOCOL_TOOL" check-spec "$base/acceptance-specification.toml"
  python3 "$PROTOCOL_TOOL" check-package "$package" --spec "$base/acceptance-specification.toml" "${CHAIN[@]}"
  python3 "$PROTOCOL_TOOL" coverage "$package" --spec "$base/acceptance-specification.toml" --root "$REPO"
  python3 "$PROTOCOL_TOOL" check-decision "$base/acceptance-decision.toml" --spec "$base/acceptance-specification.toml" --package "$package" "${CHAIN[@]}"
done
python3 "$PROTOCOL_TOOL" render paint-app/acceptance-specification.toml paint-app/acceptance-package.toml paint-app/acceptance-decision.toml "${CHAIN[@]}"
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
RUSTDOCFLAGS="-D warnings" cargo doc --no-deps --workspace
echo "== done =="
