#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Updating apt packages..."
sudo apt update

echo "[2/5] Installing system dependencies..."
sudo apt install -y \
  python3-pip \
  python3-venv \
  git \
  zip \
  unzip \
  openjdk-17-jdk \
  autoconf \
  libtool \
  pkg-config \
  zlib1g-dev \
  libncurses5-dev \
  libffi-dev \
  libssl-dev

echo "[3/5] Installing Buildozer + Cython..."
python3 -m pip install --user --upgrade pip
python3 -m pip install --user buildozer cython

if ! grep -q 'PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc"; then
  echo "[4/5] Adding ~/.local/bin to PATH in ~/.bashrc..."
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

echo "[5/5] Verifying Buildozer installation..."
export PATH="$HOME/.local/bin:$PATH"
buildozer --version

echo ""
echo "Done. Open a new shell, then run:"
echo "  cd android_app"
echo "  ./build_apk.sh"
