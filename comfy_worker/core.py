"""RunPod serverless handler orchestration."""

import json

from .comfy_client import COMFYUI_URL, ComfyClient
from .crypto import ENCRYPTION_KEY, aes_decrypt, aes_encrypt
from .model_downloader import download_loras


def handler(job: dict) -> dict:
    job_input = job.get("input", {})

    # Only full payload encryption is accepted.
    if "encrypted" not in job_input:
        return {"error": "Only encrypted payloads are accepted"}

    if not ENCRYPTION_KEY:
        return {"error": "Encryption is enabled but COMFY_ENCRYPTION_KEY is not set"}

    try:
        job_input = json.loads(aes_decrypt(job_input["encrypted"]))
    except Exception as exc:
        return {"error": f"Failed to decrypt job input: {exc}"}

    if "images" in job_input or "init-image" in job_input:
        return {
            "error": (
                '"images" and "init-image" are no longer accepted. '
                "Pass images directly in the workflow using LoadImageBase64, "
                "LoadImageUrl, or LoadImageEncrypted nodes"
            )
        }

    workflow = job_input.get("workflow")

    if not workflow:
        return {"error": "No workflow provided"}

    # Download any runtime LoRAs that are not already in the model cache.
    try:
        download_loras(job_input.get("loras") or [])
    except RuntimeError as exc:
        return {"error": str(exc)}

    client = ComfyClient(COMFYUI_URL)

    # Queue the workflow prompt
    try:
        prompt_id = client.queue_prompt(workflow)
    except Exception as exc:
        return {"error": f"Failed to queue prompt: {exc}"}

    # Wait for completion
    try:
        result = client.poll_history(prompt_id)
    except TimeoutError as exc:
        return {"error": str(exc)}

    # Collect output images as base64 and encrypt them
    output_images = []
    for node_output in result.get("outputs", {}).values():
        for img_info in node_output.get("images", []):
            b64 = client.fetch_image_b64(
                img_info["filename"],
                img_info.get("subfolder", ""),
                img_info.get("type", "output"),
            )
            enc = aes_encrypt(b64.encode())
            output_images.append({"data": enc, "encrypted": True, "type": "png"})

    if not output_images:
        return {"error": "ComfyUI returned no output images"}

    return {"images": output_images}
