#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

if ! command -v buildozer >/dev/null 2>&1; then
  echo "buildozer not found. Run ./setup_wsl_build.sh first."
  exit 1
fi

echo "Starting Android debug build..."
buildozer android debug

echo ""
echo "Build finished. APK files:"
ls -lh bin/*.apk
