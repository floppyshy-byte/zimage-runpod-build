"""ComfyUI node that decrypts an image payload, then loads it from URL or base64."""

# Reuse the worker's crypto helper when running inside the container.
try:
    from zimage_worker.crypto import ENCRYPTION_KEY, aes_decrypt
except Exception:
    ENCRYPTION_KEY = None
    aes_decrypt = None

from .load_image_base64 import LoadImageBase64
from .load_image_url import LoadImageUrl


class LoadImageEncrypted:
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
                "zimage_worker.crypto could not be imported or COMFY_ENCRYPTION_KEY is not set"
            )

        try:
            plaintext = aes_decrypt(encrypted_base64.strip())
        except Exception as exc:
            raise RuntimeError(f"Failed to decrypt image payload: {exc}") from exc

        text = plaintext.decode("utf-8", errors="replace").strip()

        if text.startswith("http://") or text.startswith("https://"):
            return LoadImageUrl().load_image_url(text)

        return LoadImageBase64().load_image_base64(text)
