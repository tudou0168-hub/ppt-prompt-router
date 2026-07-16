#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

bundle=${1:?"usage: macos_clean_room.sh <offline-bundle-root>"}
work=$(mktemp -d "${TMPDIR:-/tmp}/ppt-director-clean-中文.XXXXXX")
trap 'rm -rf "$work"' EXIT
skills="$work/skills"
mkdir -p "$skills"

python3 "$bundle/install.py" install --host generic --skills-dir "$skills"
python3 "$bundle/install.py" validate --host generic --skills-dir "$skills"
python3 "$bundle/install.py" upgrade --host generic --skills-dir "$skills"
python3 "$bundle/install.py" rollback --host generic --skills-dir "$skills"
python3 "$bundle/install.py" uninstall --host generic --skills-dir "$skills" --yes
