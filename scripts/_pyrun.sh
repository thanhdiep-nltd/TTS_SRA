#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Tries python3 → python → py -3 on PATH; on Windows, falls back to common
# Python install locations because Git Bash launched by some hooks gets a
# stripped PATH that omits the Windows Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

is_real_python() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    return 1
  fi
  local cmd_path
  cmd_path=$(command -v "$cmd" 2>/dev/null)
  if [[ "$cmd_path" == *"/WindowsApps/"* || "$cmd_path" == *"\\WindowsApps\\"* ]]; then
    return 1
  fi
  if ! "$cmd" --version >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

if is_real_python python3; then
  PY=python3
elif is_real_python python; then
  PY=python
elif is_real_python py; then
  PY="py -3"
else
  # PATH lookup failed — probe standard Windows install locations.
  PY=""
  shopt -s nullglob 2>/dev/null || true
  for cand in \
    .venv/Scripts/python.exe \
    .venv/bin/python \
    /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
    "/c/Program Files/Python"*/python.exe \
    "/c/Program Files (x86)/Python"*/python.exe \
    /c/Python*/python.exe; do
    if [ -x "$cand" ]; then PY="$cand"; break; fi
  done
  shopt -u nullglob 2>/dev/null || true
  [ -n "$PY" ] || exit 0
fi

# shellcheck disable=SC2086
exec $PY "$@"
