"""ComfyUI node that downloads and loads an image from a URL."""

from urllib.error import URLError
from urllib.request import Request, urlopen

from .shared import _load_image_tensor, _suffix_from_content_type, _write_temp_image


class LoadImageUrl:
    """Download an image from a public URL and load it into ComfyUI.

    Usage:
        Connect a STRING output containing an image URL to the ``url`` input.
        The node downloads the image, saves it to ComfyUI's input directory,
        and returns the standard IMAGE/MASK tensors.

    Inputs:
        url (STRING): A public HTTP or HTTPS URL pointing to an image.

    Outputs:
        image (IMAGE): The downloaded image as a ComfyUI IMAGE tensor.
        mask (MASK): Alpha mask, or a blank mask if the image has no alpha.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"multiline": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image_url"
    CATEGORY = "image"

    def load_image_url(self, url: str):
        req = Request(
            url.strip(),
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; RunPod-ComfyUI-Worker/1.0)"
            },
        )

        try:
            with urlopen(req, timeout=30) as resp:
                img_bytes = resp.read()
                content_type = resp.headers.get("Content-Type", "")
        except URLError as exc:
            raise RuntimeError(f"Failed to download image from URL: {exc}") from exc

        suffix = _suffix_from_content_type(content_type) or ".png"
        name = _write_temp_image(img_bytes, suffix=suffix)
        return _load_image_tensor(name)
