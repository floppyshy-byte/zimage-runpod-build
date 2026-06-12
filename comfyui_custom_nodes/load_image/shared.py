"""Shared helpers for RunPod ComfyUI image-loading custom nodes."""

import base64
import mimetypes
import os
import uuid

import folder_paths
import node_helpers
import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence


def _write_temp_image(data: bytes, suffix: str = ".png") -> str:
    """Write image bytes to ComfyUI's input directory and return the basename."""
    input_dir = folder_paths.get_input_directory()
    os.makedirs(input_dir, exist_ok=True)
    name = f"comfy_worker_{uuid.uuid4().hex[:12]}{suffix}"
    path = os.path.join(input_dir, name)
    with open(path, "wb") as f:
        f.write(data)
    return name


def _load_image_tensor(image_name: str):
    """Return (IMAGE, MASK) tensors exactly like ComfyUI's built-in LoadImage node."""
    image_path = folder_paths.get_annotated_filepath(image_name)
    img = node_helpers.pillow(Image.open, image_path)

    output_images = []
    output_masks = []
    w, h = None, None
    excluded_formats = ["MPO"]

    for i in ImageSequence.Iterator(img):
        i = node_helpers.pillow(ImageOps.exif_transpose, i)

        if i.mode == "I":
            i = i.point(lambda x: x * (1 / 255))
        image = i.convert("RGB")

        if len(output_images) == 0:
            w = image.size[0]
            h = image.size[1]

        if image.size[0] != w or image.size[1] != h:
            continue

        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]

        if "A" in i.getbands():
            mask = np.array(i.getchannel("A")).astype(np.float32) / 255.0
            mask = 1.0 - torch.from_numpy(mask)
        elif i.mode == "P" and "transparency" in i.info:
            mask = np.array(i.convert("RGBA").getchannel("A")).astype(np.float32) / 255.0
            mask = 1.0 - torch.from_numpy(mask)
        else:
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")

        output_images.append(image)
        output_masks.append(mask.unsqueeze(0))

        if img.format in excluded_formats:
            break

    if len(output_images) > 1:
        output_image = torch.cat(output_images, dim=0)
        output_mask = torch.cat(output_masks, dim=0)
    else:
        output_image = output_images[0]
        output_mask = output_masks[0]

    return (output_image, output_mask)


def _suffix_from_content_type(content_type: str) -> str | None:
    """Return a file extension for common image Content-Types, or None."""
    content_type = content_type.split(";")[0].strip().lower()
    ext = mimetypes.guess_extension(content_type)
    if ext:
        return ext

    # Fallback for types mimetypes may not know.
    if "webp" in content_type:
        return ".webp"
    if "png" in content_type:
        return ".png"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "gif" in content_type:
        return ".gif"

    return None
