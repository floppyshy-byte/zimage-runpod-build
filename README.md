# Z-Image — RunPod Serverless Endpoint

A [RunPod](https://www.runpod.io/) serverless worker for [Z-Image](https://z-image-ai.org/), Alibaba's 6B parameter AI image generation model. Built on top of ComfyUI with model caching via RunPod's HuggingFace integration.

Uses the **non-turbo base model** for full quality, with an optional **step-reducer LoRA** for fast txt2img.

## Features

- **Z-Image** text-to-image and image-to-image generation via ComfyUI API workflows
- **Non-turbo base model** — full diffusion trajectory for quality img2img transformations
- **Step-reducer LoRA** — distilled speed for txt2img (~8 steps)
- **Pre-cached models** — fast cold starts via RunPod HF Model Cache
- **Raw ComfyUI workflow JSON** input — full flexibility for LoRAs, ControlNet, etc.
- **Optional AES-256-GCM payload encryption** for sensitive requests
- **GGUF support** via ComfyUI-GGUF custom node for lower VRAM setups

## Model Files

| File | Size | Purpose | ComfyUI Path |
|------|------|---------|-------------|
| `qwen_3_4b.safetensors` | ~8GB | Text Encoder (Qwen 3) | `models/text_encoders/` |
| `z_image_bf16.safetensors` | ~12GB | Diffusion Model (base) | `models/diffusion_models/` |
| `z_image_turbo_distill_patch_lora_bf16.safetensors` | ~159MB | Step Reducer LoRA | `models/loras/` |
| `ae.safetensors` | ~335MB | VAE (same as Flux VAE) | `models/vae/` |

**Total:** ~21GB for BF16. GGUF quantized variants are also supported for 8-12GB VRAM GPUs.

## Architecture

| Mode | Model | Steps | CFG | Notes |
|------|-------|-------|-----|-------|
| **txt2img** | Base + Step-Reducer LoRA | 8 | 1.5–2.0 | Fast, distilled quality |
| **img2img** | Base only (no LoRA) | 20–50 | 5–8 | Full iterative capacity for transformations |

## Quick Start

### 1. Upload Models to HuggingFace

Create a private or public HF repo and upload the model files:

```bash
# Text encoder
huggingface-cli upload your-username/z-image split_files/text_encoders/qwen_3_4b.safetensors

# Base diffusion model (non-turbo)
huggingface-cli upload your-username/z-image split_files/diffusion_models/z_image_bf16.safetensors

# Step reducer LoRA (for fast txt2img)
huggingface-cli upload your-username/z-image split_files/loras/z_image_turbo_distill_patch_lora_bf16.safetensors

# VAE
huggingface-cli upload your-username/z-image split_files/vae/ae.safetensors
```

### 2. Build the Docker Image

Push to this repo's `main` branch — GitHub Actions will build and push to GHCR automatically.

Or build locally:

```bash
docker build -t z-image-worker .
```

### 3. Create RunPod Serverless Endpoint

1. Go to [RunPod Serverless Console](https://www.runpod.io/console/serverless)
2. Click **New Endpoint**
3. Under **Source**, connect this GitHub repo (`floppyshy-byte/zimage-runpod-build`)

### Model Options

Under **Model Caching**, add your HF repo ID (default: `Floppyshy/z_image`).
4. Select branch: `main`
5. Under **Model Caching**, add your HF repo ID (e.g. `your-username/z-image-models`)
6. GPU: Select **NVIDIA A100** / **RTX A6000** / **RTX 4090** (16GB+ VRAM for BF16)
7. (Optional) Set `COMFY_ENCRYPTION_KEY` environment variable for AES encryption
8. Deploy

### 4. Send a Request

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d '{
    "input": {
      "workflow": { ...ComfyUI workflow JSON... }
    }
  }'
```

Below is a minimal text-to-image request body. You can find ready-to-use workflow examples in the companion web UI repo (`zimage-web`).

### Image-to-Image

You can do img2img in two ways:

**Option A — Convenience `init_image` field (recommended)**

Send a txt2img workflow plus an `init_image`. The handler automatically replaces the empty latent node with `LoadImage` → `VAEEncode` and sets the denoise strength:

```json
{
  "input": {
    "workflow": { ...txt2img workflow JSON... },
    "init_image": "<base64-encoded PNG/JPEG>",
    "denoise": 0.75
  }
}
```

**Option B — Raw ComfyUI workflow with `LoadImage`**

Pass a complete workflow that includes `LoadImage` → `VAEEncode` → `KSampler` and upload the input image via the `images` array:

```json
{
  "input": {
    "workflow": { ...img2img workflow JSON... },
    "images": [{"name": "input.png", "image": "<base64>"}]
  }
}
```

## API Reference

### Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow` | object | ✅ | ComfyUI API workflow JSON (node graph) |
| `images` | array | ❌ | Input images for raw workflows with `LoadImage` nodes |
| `init_image` | string | ❌ | Base64 PNG/JPEG; auto-patches a txt2img workflow into img2img |
| `denoise` | float | ❌ | Denoise strength for `init_image` mode (default: `0.75`) |

### Output

```json
{
  "images": [
    {
      "data": "<base64-encoded PNG>",
      "type": "png"
    }
  ]
}
```

### Optional: Encrypted Payloads

Set the `COMFY_ENCRYPTION_KEY` environment variable (64 hex chars = 32 bytes) to enable AES-256-GCM encryption:

```json
{
  "input": {
    "encrypted": "<base64(nonce + ciphertext)>"
  }
}
```

The decrypted payload must be a JSON object with `workflow` and optional `images`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZIMAGE_HF_REPO` | `floppyshy-byte/z-image-models` | HF repo ID containing model files |
| `COMFY_ENCRYPTION_KEY` | *(none)* | 64 hex chars for AES-256-GCM encryption |

## Recommended Generation Settings

### txt2img (with step-reducer LoRA)

| Setting | Value | Notes |
|---------|-------|-------|
| Steps | **8** | Sweet spot with the LoRA |
| CFG Scale | **1.5 – 2.0** | Keep low with LoRA; above 2.5 causes artifacts |
| Sampler | **euler** | Fast and consistent |
| Resolution | **1024×1024** | Native resolution |
| CLIP Type | **lumina2** | Required for Qwen 3 text encoder |

### img2img (base model, no LoRA)

| Setting | Value | Notes |
|---------|-------|-------|
| Steps | **20–50** | Full iterative denoising |
| CFG Scale | **5–8** | Standard guidance for structural changes |
| Denoise | **0.75–0.95** | 0.75 for color/style, 0.90+ for subject replacement |
| Sampler | **euler** | Reliable for img2img |
| Resolution | **1024×1024** | Native resolution |

## Low VRAM / GGUF

For GPUs with 8-12GB VRAM, use GGUF quantized models:

- `z_image-Q5_K_S.gguf` (diffusion model)
- `Qwen3-4B.i1-Q5_K_S.gguf` (text encoder)

The `ComfyUI-GGUF` custom node is pre-installed. Use the `GGUFModelLoader` and `GGUFCLIPLoader` nodes in your workflow.

## Project Structure

```
.
├── Dockerfile                  # ComfyUI base image + Z-Image custom nodes
├── handler.py                  # RunPod serverless handler
├── model-setup.sh              # Symlinks HF cached models into ComfyUI
├── .github/workflows/
│   └── docker-build.yml        # GitHub Actions CI/CD
└── README.md                   # This file
```

## License

See Z-Image Turbo's official license. This worker code is provided as-is for deployment convenience.
