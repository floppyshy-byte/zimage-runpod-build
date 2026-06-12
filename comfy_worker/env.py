"""Centralized environment variable access for the ComfyUI worker.

All environment variables used anywhere in the worker should be declared
and documented here. Import the ``env`` singleton from this module instead
of reading ``os.environ`` directly.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Environment variables used by the RunPod ComfyUI worker.

    Attributes / properties:
        target_base (Path): Root directory where cached models are symlinked
            for ComfyUI.
            Env var: ``TARGET_BASE``
            Default: ``/comfyui/models``

        hf_org (str | None): Hugging Face organization that owns the cached
            model repo.
            Env var: ``HF_ORG``

        hf_repo (str | None): Hugging Face repository name for the cached
            model repo.
            Env var: ``HF_REPO``

        comfy_encryption_key (str): 64-character hex string used as the
            AES-256-GCM key for decrypting payloads. If empty, encrypted
            nodes will raise a clear error at runtime.
            Env var: ``COMFY_ENCRYPTION_KEY``

        civitai_api_key (str): Bearer token for authenticated CivitAI
            downloads. Optional.
            Env var: ``CIVITAI_API_KEY``

        github_token (str): Token for authenticated GitHub downloads
            (e.g. release assets). Falls back to ``GH_FLOPPY_TOKEN`` for
            backward compatibility. Optional.
            Env vars: ``GITHUB_TOKEN``, ``GH_FLOPPY_TOKEN``
    """

    @property
    def target_base(self) -> Path:
        return Path(os.environ.get("TARGET_BASE", "/comfyui/models"))

    @property
    def hf_org(self) -> str | None:
        return os.environ.get("HF_ORG")

    @property
    def hf_repo(self) -> str | None:
        return os.environ.get("HF_REPO")

    @property
    def comfy_encryption_key(self) -> str:
        return os.environ.get("COMFY_ENCRYPTION_KEY", "")

    @property
    def civitai_api_key(self) -> str:
        return os.environ.get("CIVITAI_API_KEY", "")

    @property
    def github_token(self) -> str:
        return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_FLOPPY_TOKEN", "")


# Module-level singleton. Import this object rather than instantiating
# ``Settings`` directly so every caller sees the same values.
env = Settings()
