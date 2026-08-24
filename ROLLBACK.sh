#!/usr/bin/env bash
set -euo pipefail

target="${1:-MODIFIED_FILE}"
baseline_path="${2:-main.py}"
baseline_commit="${MANTOU_BASELINE_COMMIT:-eaabab80d34f3ba612ebe8c9271f1bab99353944}"

if [[ ! -f "$target" ]]; then
  printf 'ROLLBACK_TARGET_MISSING %s\n' "$target" >&2
  exit 2
fi
if ! git rev-parse --verify "${baseline_commit}:${baseline_path}" >/dev/null 2>&1; then
  printf 'ROLLBACK_BASELINE_MISSING %s:%s\n' "$baseline_commit" "$baseline_path" >&2
  exit 3
fi

temporary_file="$(mktemp)"
trap 'rm -f "$temporary_file"' EXIT
git show "${baseline_commit}:${baseline_path}" > "$temporary_file"
cp "$temporary_file" "$target"
printf 'ROLLBACK_RESTORED target=%s baseline=%s:%s\n' "$target" "$baseline_commit" "$baseline_path"
