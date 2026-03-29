#!/usr/bin/env bash
# build.sh — Run by Render as the Build Command
# Installs system-level dependencies that pip cannot provide.

set -e  # exit immediately on any error

echo ">>> Installing system dependencies..."
apt-get update -y
apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    libglib2.0-0

echo ">>> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ">>> Build complete."
