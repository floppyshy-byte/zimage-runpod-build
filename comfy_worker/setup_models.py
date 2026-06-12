#!/usr/bin/env python3
"""
Generic ComfyUI model cache linker.

Mirrors the Hugging Face cached model repo into /comfyui/models using file-level
symlinks. Assumes the cache is already laid out in ComfyUI model-directory format, e.g.:

    text_encoders/
    diffusion_models/
    unet/
    vae/
    loras/
    checkpoints/

Any directory tree is preserved; only files are symlinked, so ComfyUI sees the
cached models in the standard locations without copying them.
"""

import os
from pathlib import Path

from .env import env

TARGET_BASE = env.target_base
HF_CACHE = Path("/runpod-volume/huggingface-cache/hub")

JUNK_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
}
JUNK_NAMES = {
    ".gitattributes",
    ".gitignore",
}


def log(message: str) -> None:
    print(f"[model-setup] {message}")


def resolve_cache_dir() -> Path | None:
    """Return the source cache directory from the HF cache snapshot."""
    org = env.hf_org
    repo = env.hf_repo
    if not org or not repo:
        return None

    repo_id = f"{org}/{repo}"
    repo_dir = HF_CACHE / f"models--{repo_id.replace('/', '--')}"
    ref_file = repo_dir / "refs" / "main"
    if not ref_file.exists():
        return None

    snapshot = ref_file.read_text().strip()
    snapshot_dir = repo_dir / "snapshots" / snapshot
    if snapshot_dir.is_dir():
        return snapshot_dir

    return None


def is_junk(path: Path) -> bool:
    """Return True for files ComfyUI should not scan."""
    return (
        path.suffix.lower() in JUNK_SUFFIXES
        or path.name in JUNK_NAMES
        or any(part.startswith(".git") for part in path.parts)
    )


def mirror_tree(cache_dir: Path, target_base: Path) -> None:
    """Symlink every file under cache_dir into target_base preserving structure."""
    target_base.mkdir(parents=True, exist_ok=True)

    for src in cache_dir.rglob("*"):
        if not src.is_file():
            continue
        if is_junk(src):
            continue

        rel = src.relative_to(cache_dir)
        dst = target_base / rel

        if dst.is_symlink():
            current_target = os.readlink(dst)
            if current_target == str(src):
                log(f"OK: {rel}")
                continue
            dst.unlink()

        if dst.exists():
            log(f"SKIP: {rel} (target exists and is not a symlink)")
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(src)
        log(f"LINK: {rel}")


def cleanup_broken_links(target_base: Path) -> None:
    """Remove broken symlinks under target_base so ComfyUI doesn't scan them."""
    if not target_base.exists():
        return

    for path in target_base.rglob("*"):
        if path.is_symlink() and not path.exists():
            log(f"REMOVE: broken link {path.relative_to(target_base)}")
            path.unlink()


def setup_models(target_base: Path = TARGET_BASE) -> int:
    """Link cached models into target_base and clean stale symlinks."""
    cache_dir = resolve_cache_dir()
    if cache_dir is None:
        log("WARNING: HF_ORG and HF_REPO not set and no HF cache found")
        log("Continuing without linking models...")
        return 0

    if not cache_dir.is_dir():
        log(f"WARNING: cache directory does not exist: {cache_dir}")
        log("Continuing without linking models...")
        return 0

    log(f"Mirroring {cache_dir} -> {target_base}")
    mirror_tree(cache_dir, target_base)
    cleanup_broken_links(target_base)
    log("Model linking complete")
    return 0


def main() -> int:
    return setup_models()


if __name__ == "__main__":
    raise SystemExit(main())
