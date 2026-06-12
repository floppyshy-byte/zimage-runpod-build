"""ComfyUI node that loads an image from a base64-encoded string."""

import base64

from .shared import _load_image_tensor, _write_temp_image


class LoadImageBase64:
    """Load an image from a base64-encoded string.

    Usage:
        Connect a STRING output containing base64 image data to the
        ``image_base64`` input. Data-URI prefixes such as
        ``data:image/png;base64,`` are stripped automatically.

    Inputs:
        image_base64 (STRING): A base64-encoded PNG, JPEG, WEBP, or GIF.
            Multi-line text widget.

    Outputs:
        image (IMAGE): The decoded image as a ComfyUI IMAGE tensor.
        mask (MASK): Alpha mask, or a blank mask if the image has no alpha.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_base64": ("STRING", {"multiline": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image_base64"
    CATEGORY = "image"

    def load_image_base64(self, image_base64: str):
        b64 = image_base64.strip()
        if b64.startswith("data:"):
            b64 = b64.split(",", 1)[-1]

        try:
            img_bytes = base64.b64decode(b64, validate=True)
        except Exception as exc:
            raise RuntimeError(f"Invalid base64 image data: {exc}") from exc

        name = _write_temp_image(img_bytes)
        return _load_image_tensor(name)
