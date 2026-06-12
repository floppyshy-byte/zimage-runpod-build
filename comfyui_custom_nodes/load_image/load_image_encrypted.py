"""ComfyUI node that decrypts an image payload, then loads it from URL or base64."""

# Reuse the worker's crypto helper when running inside the container.
try:
    from comfy_worker.crypto import ENCRYPTION_KEY, aes_decrypt
except Exception:
    ENCRYPTION_KEY = None
    aes_decrypt = None

from .load_image_base64 import LoadImageBase64
from .load_image_url import LoadImageUrl


class LoadImageEncrypted:
    """Decrypt an AES-256-GCM payload, then load the image it contains.

    Usage:
        Connect a STRING output containing an AES-256-GCM encrypted base64
        payload to the ``encrypted_base64`` input. The node decrypts the
        payload using ``COMFY_ENCRYPTION_KEY``, inspects the plaintext, and
        delegates to ``LoadImageUrl`` if it starts with ``http://`` or
        ``https://``, otherwise to ``LoadImageBase64``.

    Inputs:
        encrypted_base64 (STRING): AES-256-GCM encrypted base64 payload.
            Multi-line text widget. Plaintext must be a URL or base64 image.

    Outputs:
        image (IMAGE): The decoded image as a ComfyUI IMAGE tensor.
        mask (MASK): Alpha mask, or a blank mask if the image has no alpha.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "encrypted_base64": ("STRING", {"multiline": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image_encrypted"
    CATEGORY = "image"

    def load_image_encrypted(self, encrypted_base64: str):
        if aes_decrypt is None or ENCRYPTION_KEY is None:
            raise RuntimeError(
                "Encryption support is not available: "
                "comfy_worker.crypto could not be imported or COMFY_ENCRYPTION_KEY is not set"
            )

        try:
            plaintext = aes_decrypt(encrypted_base64.strip())
        except Exception as exc:
            raise RuntimeError(f"Failed to decrypt image payload: {exc}") from exc

        text = plaintext.decode("utf-8", errors="replace").strip()

        if text.startswith("http://") or text.startswith("https://"):
            return LoadImageUrl().load_image_url(text)

        return LoadImageBase64().load_image_base64(text)
