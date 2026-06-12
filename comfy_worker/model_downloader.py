"""Runtime LoRA downloader.

Downloads per-workflow LoRAs into the ComfyUI LoRA directory, skipping any
file that already exists (e.g. pre-cached by RunPod's HuggingFace integration).
"""

import subprocess
from pathlib import Path

from .env import env


def download_loras(loras: list[dict]) -> None:
    """Download a list of LoRAs, skipping any that are already present.

    Each item must contain ``lora_name`` and ``lora_url``.
    """
    for lora in loras:
        name = lora.get("lora_name", "").strip()
        url = lora.get("lora_url", "").strip()
        if not name or not url:
            continue
        download_lora(name, url)


def download_lora(lora_name: str, lora_url: str) -> None:
    """Download a single LoRA if it is not already present on disk.

    Models pre-cached by RunPod's HuggingFace integration are symlinked into
    the same directory, so checking for the target file's existence also
    catches cached models.
    """
    loras_dir = env.target_base / "loras"
    dest = loras_dir / lora_name

    if dest.exists():
        print(f"[handler] LoRA already present, skipping: {lora_name}")
        return

    print(f"[handler] Downloading LoRA: {lora_name} from {lora_url}")
    loras_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    try:
        cmd = [
            "curl",
            "-L",
            "-s",
            "-f",
            "--connect-timeout",
            "10",
            "--max-time",
            "300",
            "-o",
            str(tmp),
            lora_url,
        ]

        civitai_key = env.civitai_api_key
        if civitai_key and "civitai" in lora_url:
            cmd += ["-H", f"Authorization: Bearer {civitai_key}"]

        github_key = env.github_token
        if github_key and "github.com" in lora_url:
            cmd += ["-H", f"Authorization: token {github_key}"]

        subprocess.check_call(cmd)
        tmp.replace(dest)
        print(f"[handler] LoRA ready: {lora_name}")
    except Exception as exc:
        raise RuntimeError(f"Failed to download LoRA {lora_name}: {exc}") from exc
    finally:
        # Ensure the temp file is cleaned up if it still exists.
        if tmp.exists():
            tmp.unlink(missing_ok=True)
