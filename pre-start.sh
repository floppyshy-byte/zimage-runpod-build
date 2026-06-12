#!/bin/bash
set -e

# Pre-start hook for the RunPod ComfyUI worker.
#
# Runs any one-time setup that must happen before ComfyUI starts (model cache
# linking, cleanup, etc.) and then delegates to the base image's /start.sh.

echo "[pre-start] Linking cached models into ComfyUI model paths..."
python3 /zimage_worker/setup_models.py

echo "[pre-start] Starting ComfyUI via /start.sh..."
exec /start.sh
