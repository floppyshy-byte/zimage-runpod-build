"""Workflow patching helpers."""

import uuid

from .comfy_client import ComfyClient


def apply_img2img(
    workflow: dict,
    init_image_b64: str,
    client: ComfyClient,
    denoise: float | None = None,
) -> None:
    """Patch a txt2img-style workflow so the KSampler uses an uploaded init image.

    Finds the first KSampler whose latent_image input comes from an empty latent
    node (EmptySD3LatentImage / EmptyLatentImage), removes that node, and inserts
    LoadImage -> VAEEncode in its place. The init image is uploaded to ComfyUI's
    input folder. If denoise is provided, the KSampler's denoise value is updated.
    """
    denoise = 0.75 if denoise is None else float(denoise)

    img_name = f"init_img_{uuid.uuid4().hex[:8]}.png"
    client.upload_image(img_name, init_image_b64)

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
