#!/usr/bin/env python3
"""
Custom RunPod handler for ComfyUI with Z-Image Turbo models pre-cached.

All models (text encoder, diffusion model, VAE) are pre-cached via RunPod model
caching from a HuggingFace repo and symlinked into place by model-setup.sh before
ComfyUI starts. This handler does NOT download any models at runtime.

Input format:
{
  "workflow": { ...ComfyUI API node graph... },
  "images": [{"name": "input.png", "image": "<base64>"}],  // optional
  "init_image": "<base64>",                                // optional img2img
  "denoise": 0.75                                          // optional (default 0.75)
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
import uuid

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


def _apply_img2img(workflow: dict, init_image_b64: str, denoise: float | None = None) -> None:
    """Patch a txt2img-style workflow so the KSampler uses an uploaded init image.

    Finds the first KSampler whose latent_image input comes from an empty latent
    node (EmptySD3LatentImage / EmptyLatentImage), removes that node, and inserts
    LoadImage -> VAEEncode in its place. The init image is uploaded to ComfyUI's
    input folder. If denoise is provided, the KSampler's denoise value is updated.
    """
    denoise = 0.75 if denoise is None else float(denoise)

    img_name = f"init_img_{uuid.uuid4().hex[:8]}.png"
    _upload_image(img_name, init_image_b64)

    ksampler_id: str | None = None
    latent_source_id: str | None = None
    for node_id, node in workflow.items():
        if node.get("class_type") == "KSampler":
            latent_input = node.get("inputs", {}).get("latent_image")
            if isinstance(latent_input, list) and len(latent_input) == 2:
                ksampler_id = node_id
                latent_source_id = str(latent_input[0])
            break

    if not ksampler_id or not latent_source_id:
        raise RuntimeError(
            "img2img: no KSampler with a latent_image input found in workflow"
        )

    source_node = workflow.get(latent_source_id)
    if not source_node:
        raise RuntimeError(
            f"img2img: latent source node {latent_source_id} referenced by KSampler not found"
        )

    source_type = source_node.get("class_type", "")
    if source_type not in ("EmptySD3LatentImage", "EmptyLatentImage"):
        raise RuntimeError(
            f"img2img: KSampler latent source is {source_type}, expected EmptySD3LatentImage or EmptyLatentImage"
        )

    vae_loader_id: str | None = None
    for node_id, node in workflow.items():
        if node.get("class_type") in ("VAELoader", "VAELoaderTAESD"):
            vae_loader_id = node_id
            break

    if not vae_loader_id:
        raise RuntimeError("img2img: no VAELoader node found in workflow")

    load_id = f"init_load_{uuid.uuid4().hex[:4]}"
    encode_id = f"init_encode_{uuid.uuid4().hex[:4]}"

    del workflow[latent_source_id]

    workflow[load_id] = {
        "inputs": {"image": img_name},
        "class_type": "LoadImage",
    }
    workflow[encode_id] = {
        "inputs": {
            "pixels": [load_id, 0],
            "vae": [vae_loader_id, 0],
        },
        "class_type": "VAEEncode",
    }

    workflow[ksampler_id]["inputs"]["latent_image"] = [encode_id, 0]
    workflow[ksampler_id]["inputs"]["denoise"] = denoise


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

    # Encryption mode: triggered by "encryption": true or legacy "encrypted" field
    encryption_enabled = job_input.get("encryption") is True or "encrypted" in job_input
    was_fully_encrypted = "encrypted" in job_input

    if encryption_enabled and not _ENCRYPTION_KEY:
        return {"error": "Encryption is enabled but COMFY_ENCRYPTION_KEY is not set"}

    # Decrypt full payload if it arrived in the legacy "encrypted" field
    if was_fully_encrypted:
        try:
            job_input = json.loads(_aes_decrypt(job_input["encrypted"]))
        except Exception as exc:
            return {"error": f"Failed to decrypt job input: {exc}"}

    workflow = job_input.get("workflow")
    images = job_input.get("images") or []

    if not workflow:
        return {"error": "No workflow provided"}

    # Decrypt individual prompt if encryption mode is on and "encrypted_prompt" is provided
    encrypted_prompt = job_input.get("encrypted_prompt")
    if encryption_enabled and encrypted_prompt and _ENCRYPTION_KEY:
        try:
            decrypted_prompt = _aes_decrypt(encrypted_prompt).decode("utf-8")
            injected = False
            for node in workflow.values():
                if node.get("class_type") == "CLIPTextEncode":
                    node["inputs"]["text"] = decrypted_prompt
                    injected = True
            if not injected:
                return {"error": "encrypted_prompt provided but no CLIPTextEncode node found in workflow"}
        except Exception as exc:
            return {"error": f"Failed to decrypt prompt: {exc}"}

    # Convenience img2img: patch a txt2img workflow to use an init image.
    # If you prefer full control, provide a workflow with LoadImage nodes and use "images".
    init_image = job_input.get("init_image")
    if init_image:
        try:
            _apply_img2img(workflow, init_image, job_input.get("denoise"))
        except Exception as exc:
            return {"error": str(exc)}

    # Upload input images (e.g. for raw workflows with LoadImage nodes)
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

    # Collect output images as base64, encrypting if encryption mode is enabled
    output_images = []
    for node_output in result.get("outputs", {}).values():
        for img_info in node_output.get("images", []):
            b64 = _fetch_image_b64(
                img_info["filename"],
                img_info.get("subfolder", ""),
                img_info.get("type", "output"),
            )
            if encryption_enabled:
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
