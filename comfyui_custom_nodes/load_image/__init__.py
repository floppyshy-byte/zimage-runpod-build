from .load_image_base64 import LoadImageBase64
from .load_image_encrypted import LoadImageEncrypted
from .load_image_url import LoadImageUrl

NODE_CLASS_MAPPINGS = {
    "LoadImageBase64": LoadImageBase64,
    "LoadImageUrl": LoadImageUrl,
    "LoadImageEncrypted": LoadImageEncrypted,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageBase64": "Load Image (Base64)",
    "LoadImageUrl": "Load Image (URL)",
    "LoadImageEncrypted": "Load Image (Encrypted)",
}
