#!/usr/bin/env python3
"""
Custom RunPod serverless handler for ComfyUI.

Models are pre-cached via RunPod model caching from a HuggingFace repo and
symlinked into place before ComfyUI starts. Per-workflow LoRAs can also be
downloaded at job time; any LoRA already present in the model cache is skipped.

Input format (encrypted payload only):
{
  "encrypted": "<base64(nonce + ciphertext)>"  // AES-256-GCM encrypted JSON object
}

The decrypted payload must contain:
{
  "workflow": { ...ComfyUI API node graph... },
  "loras": [  // optional runtime LoRAs
    {"lora_name": "filename.safetensors", "lora_url": "https://..."}
  ],
  "init_image": "<base64>",  // optional img2img (deprecated, embed in workflow)
  "denoise": 0.75            // optional (default 0.75)
}

Images must be embedded directly in the workflow using LoadImageBase64,
LoadImageUrl, or LoadImageEncrypted nodes. The legacy "images" field is no
longer accepted.

Environment variables:
  COMFY_ENCRYPTION_KEY  — required; 64 hex chars for AES-256-GCM payload encryption
  CIVITAI_API_KEY       — optional; Bearer token for CivitAI LoRA downloads
  GITHUB_TOKEN          — optional; token for GitHub release asset downloads
  GH_FLOPPY_TOKEN       — optional; fallback for GitHub token (backward compat)
"""

import runpod

from comfy_worker import COMFYUI_URL, ComfyClient, handler

if __name__ == "__main__":
    print("[handler] Waiting for ComfyUI...")
    ComfyClient(COMFYUI_URL).wait_for_comfyui()
    print("[handler] ComfyUI ready — starting RunPod serverless handler")
    runpod.serverless.start({"handler": handler})
