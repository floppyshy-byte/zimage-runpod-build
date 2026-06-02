#!/usr/bin/env python3
"""
Custom RunPod handler for ComfyUI with Z-Image Turbo models pre-cached.

All models (text encoder, diffusion model, VAE) are pre-cached via RunPod model
caching from a HuggingFace repo and symlinked into place by model-setup.sh before
ComfyUI starts. This handler does NOT download any models at runtime.

Input format:
{
  "workflow": { ...ComfyUI API node graph... },
  "images": [{"name": "input.png", "image": "<base64>"}]  // optional
}

Environment variables:
  COMFY_ENCRYPTION_KEY  — 64 hex chars for AES-256-GCM payload encryption (optional)
"""

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import runpod

COMFYUI_URL = "http://127.0.0.1:8188"

# AES-256-GCM encryption — enabled when COMFY_ENCRYPTION_KEY is set (64 hex chars)
_ENCRYPTION_KEY: bytes | None = None
_RAW_KEY = os.getenv("COMFY_ENCRYPTION_KEY", "")
if _RAW_KEY:
    _key_bytes = bytes.fromhex(_RAW_KEY)
    if len(_key_bytes) != 32:
        raise RuntimeError("COMFY_ENCRYPTION_KEY must be 64 hex characters (32 bytes)")
    _ENCRYPTION_KEY = _key_bytes


def _aes_decrypt(encoded: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    data = base64.b64decode(encoded)
    nonce, ciphertext = data[:12], data[12:]
    return AESGCM(_ENCRYPTION_KEY).decrypt(nonce, ciphertext, None)


def _aes_encrypt(plaintext: bytes) -> str:
    import secrets
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_ENCRYPTION_KEY).encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_comfyui(timeout: int = 120) -> None:
    """Block until ComfyUI's HTTP API responds or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=3)
            return
        except Exception:
            time.sleep(2)
    print("[handler] FATAL: ComfyUI did not start within %ds, killing container" % timeout)
    os._exit(1)


def _upload_image(name: str, image_b64: str) -> None:
    """Upload a base64-encoded image to ComfyUI's input directory."""
    img_bytes = base64.b64decode(image_b64)
    boundary = "runpod-upload-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + img_bytes + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def _queue_prompt(workflow: dict) -> str:
    """Submit a ComfyUI workflow and return the prompt_id."""
    data = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["prompt_id"]
    except Exception as exc:
        exc_type = type(exc).__name__
        if hasattr(exc, "code") and hasattr(exc, "read"):
            body = exc.read().decode(errors="replace")
            raise RuntimeError(f"ComfyUI /prompt returned {exc.code}: {body}") from exc
        raise RuntimeError(f"ComfyUI /prompt error [{exc_type}]: {exc}") from exc


def _poll_history(prompt_id: str, timeout: int = 600) -> dict:
    """Poll ComfyUI history until prompt completes; return the history entry."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"{COMFYUI_URL}/history/{prompt_id}", timeout=10
            ) as resp:
                history = json.loads(resp.read())
            if prompt_id in history:
                return history[prompt_id]
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError(f"Prompt {prompt_id} did not complete within {timeout}s")


def _fetch_image_b64(filename: str, subfolder: str, folder_type: str) -> str:
    """Fetch an output image from ComfyUI and return as base64."""
    params = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": folder_type}
    )
    with urllib.request.urlopen(
        f"{COMFYUI_URL}/view?{params}", timeout=30
    ) as resp:
        return base64.b64encode(resp.read()).decode()


# ---------------------------------------------------------------------------
# RunPod handler
# ---------------------------------------------------------------------------

def handler(job: dict) -> dict:
    job_input = job.get("input", {})

    # Track whether this request arrived encrypted so we can match the output format
    was_encrypted = "encrypted" in job_input

    # Decrypt payload if it arrived encrypted
    if was_encrypted:
        if not _ENCRYPTION_KEY:
            return {"error": "Received encrypted input but COMFY_ENCRYPTION_KEY is not set"}
        try:
            job_input = json.loads(_aes_decrypt(job_input["encrypted"]))
        except Exception as exc:
            return {"error": f"Failed to decrypt job input: {exc}"}

    workflow = job_input.get("workflow")
    images = job_input.get("images") or []

    if not workflow:
        return {"error": "No workflow provided"}

    # Upload input images (e.g. for img2img)
    for img in images:
        try:
            _upload_image(img["name"], img["image"])
        except Exception as exc:
            return {"error": f"Failed to upload image {img['name']}: {exc}"}

    # Queue the workflow prompt
    try:
        prompt_id = _queue_prompt(workflow)
    except Exception as exc:
        return {"error": f"Failed to queue prompt: {exc}"}

    # Wait for completion
    try:
        result = _poll_history(prompt_id)
    except TimeoutError as exc:
        return {"error": str(exc)}

    # Collect output images as base64, encrypting if key is present
    output_images = []
    for node_output in result.get("outputs", {}).values():
        for img_info in node_output.get("images", []):
            b64 = _fetch_image_b64(
                img_info["filename"],
                img_info.get("subfolder", ""),
                img_info.get("type", "output"),
            )
            if was_encrypted:
                enc = _aes_encrypt(b64.encode())
                output_images.append({"data": enc, "encrypted": True, "type": "png"})
            else:
                output_images.append({"data": b64, "type": "png"})

    if not output_images:
        return {"error": "ComfyUI returned no output images"}

    return {"images": output_images}


if __name__ == "__main__":
    print("[handler] Waiting for ComfyUI...")
    _wait_for_comfyui()
    print("[handler] ComfyUI ready — starting RunPod serverless handler")
    runpod.serverless.start({"handler": handler})
