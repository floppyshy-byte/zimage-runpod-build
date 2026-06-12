#!/bin/bash
set -e

# Pre-start hook for the RunPod ComfyUI worker.
#
# Runs any one-time setup that must happen before ComfyUI starts (model cache
# linking, cleanup, etc.) and then delegates to the base image's /start.sh.

echo "[pre-start] Linking extra_model_paths.yaml if present..."
if [ -e /comfyui/models/extra_model_paths.yaml ]; then
    if [ ! -e /comfyui/extra_model_paths.yaml ]; then
        ln -s /comfyui/models/extra_model_paths.yaml /comfyui/extra_model_paths.yaml
        echo "[pre-start] Linked /comfyui/extra_model_paths.yaml -> /comfyui/models/extra_model_paths.yaml"
    else
        echo "[pre-start] /comfyui/extra_model_paths.yaml already exists, skipping"
    fi
fi

echo "[pre-start] Linking cached models into ComfyUI model paths..."
python3 /comfy_worker/setup_models.py

echo "[pre-start] Starting ComfyUI via /start.sh..."
exec /start.sh
