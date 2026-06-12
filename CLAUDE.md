# CLAUDE.md — RunPod ComfyUI Worker

This file captures project conventions and context for Claude Code sessions.

## Project purpose

A generic [RunPod](https://www.runpod.io/) serverless worker for [ComfyUI](https://github.com/comfyanonymous/ComfyUI). The worker receives encrypted ComfyUI workflow JSON, runs it, and returns encrypted output images. Models are pre-cached via RunPod's HuggingFace integration and symlinked into `/comfyui/models` at startup.

## Architecture

- `handler.py` — RunPod serverless entrypoint.
- `comfy_worker/core.py` — Request/response orchestration.
- `comfy_worker/comfy_client.py` — ComfyUI HTTP client.
- `comfy_worker/crypto.py` — AES-256-GCM encryption helpers.
- `comfy_worker/env.py` — Centralized environment variables.
- `comfy_worker/setup_models.py` — Mirrors HF cache into `/comfyui/models` via symlinks.
- `comfy_worker/model_downloader.py` — Runtime LoRA downloader; skips files already present in the model cache.
- `comfyui_custom_nodes/load_image/` — Custom ComfyUI nodes for base64/URL/encrypted images.
- `pre-start.sh` — Pre-start hook: links `extra_model_paths.yaml` if present, runs model setup, then execs `/start.sh`.
- `Dockerfile` — Builds on the official RunPod ComfyUI base image; includes GGUF support and shared nodes used by prompt-studio / ModelRouter workflows (`LoRA Stacker`, `KSampler //Inspire`, Comfyroll nodes).
- `.github/workflows/docker-build.yml` — CI/CD to GHCR.

## Development conventions

- **Python target version:** 3.12.
- **Linter/formatter:** Ruff. Configuration lives in `pyproject.toml`.
  ```bash
  ruff check .
  ruff format --check .   # or `ruff format .` to apply
  ```
- All Python code must pass `ruff check` and `ruff format` before merging.
- Use `pathlib.Path` for filesystem paths.
- Environment variables are read through `comfy_worker/env.py`; do not read `os.environ` directly elsewhere.

## Encryption

All request and response payloads use AES-256-GCM. The key is read from `COMFY_ENCRYPTION_KEY` (64 hex chars = 32 bytes). Workflows receive images via custom nodes (`LoadImageBase64`, `LoadImageUrl`, `LoadImageEncrypted`); the legacy `images` array is not supported.

## Model setup

At container startup:

1. `pre-start.sh` checks for `/comfyui/models/extra_model_paths.yaml`. If present, it symlinks it to `/comfyui/extra_model_paths.yaml` so ComfyUI picks it up.
2. `comfy_worker/setup_models.py` resolves the HF cache snapshot for `HF_ORG/HF_REPO` and symlinks every file into `TARGET_BASE` (default `/comfyui/models`), preserving directory structure.
3. Broken symlinks under `TARGET_BASE` are cleaned up.

## Common commands

Build the Docker image locally:
```bash
docker build -t runpod-comfyui-worker .
```

Run linting/formatting:
```bash
ruff check .
ruff format --check .
```

## Things to be careful about

- `setup_models.py` runs inside the container where `/runpod-volume/huggingface-cache/hub` is mounted by RunPod. Do not assume the cache exists in local development.
- ComfyUI is started by `/start.sh` from the base image; `pre-start.sh` must `exec` it so it becomes PID 1.
- The `upload_image` helper in `comfy_client.py` is a temporary bridge while workflow patching lives partly outside ComfyUI.
