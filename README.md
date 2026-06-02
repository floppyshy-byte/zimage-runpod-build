# Z-Image Turbo — RunPod Serverless Endpoint

A [RunPod](https://www.runpod.io/) serverless worker for [Z-Image Turbo](https://z-image-ai.org/), Alibaba's 6B parameter AI image generation model. Built on top of ComfyUI with model caching via RunPod's HuggingFace integration.

## Features

- **Z-Image Turbo** text-to-image generation via ComfyUI API workflows
- **Pre-cached models** — fast cold starts via RunPod HF Model Cache
- **Raw ComfyUI workflow JSON** input — full flexibility for img2img, ControlNet, LoRAs, etc.
- **Optional AES-256-GCM payload encryption** for sensitive requests
- **GGUF support** via ComfyUI-GGUF custom node for lower VRAM setups

## Model Files

| File | Size | Purpose | ComfyUI Path |
|------|------|---------|-------------|
| `qwen_3_4b.safetensors` | ~8GB | Text Encoder (Qwen 3) | `models/text_encoders/` |
| `z_image_turbo_bf16.safetensors` | ~12GB | Diffusion Model | `models/diffusion_models/` |
| `ae.safetensors` | ~1GB | VAE (same as Flux VAE) | `models/vae/` |

**Total:** ~21GB for BF16. GGUF quantized variants are also supported for 8-12GB VRAM GPUs.

## Quick Start

### 1. Upload Models to HuggingFace

Create a private or public HF repo (e.g. `your-username/z-image-models`) and upload the 3 model files:

```bash
huggingface-cli upload your-username/z-image-models qwen_3_4b.safetensors
huggingface-cli upload your-username/z-image-models z_image_turbo_bf16.safetensors
huggingface-cli upload your-username/z-image-models ae.safetensors
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
3. Under **Source**, connect this GitHub repo (`sleungcy/z-image`)
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

See [`workflow-example.json`](workflow-example.json) for a complete text-to-image example.

## API Reference

### Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow` | object | ✅ | ComfyUI API workflow JSON (node graph) |
| `images` | array | ❌ | Input images for img2img / ControlNet |

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

| Setting | Value | Notes |
|---------|-------|-------|
| Steps | **8** | Sweet spot for the distilled model |
| CFG Scale | **1.5 – 2.0** | Keep low! Above 2.5 causes artifacts |
| Sampler | **euler** | Fast and consistent for S3-DiT |
| Resolution | **1024×1024** | Native resolution |
| CLIP Type | **lumina2** | Required for Qwen 3 text encoder |

## Low VRAM / GGUF

For GPUs with 8-12GB VRAM, use GGUF quantized models:

- `z_image_turbo-Q5_K_S.gguf` (diffusion model)
- `Qwen3-4B.i1-Q5_K_S.gguf` (text encoder)

The `ComfyUI-GGUF` custom node is pre-installed. Use the `GGUFModelLoader` and `GGUFCLIPLoader` nodes in your workflow.

## Project Structure

```
.
├── Dockerfile                  # ComfyUI base image + Z-Image custom nodes
├── handler.py                  # RunPod serverless handler
├── model-setup.sh              # Symlinks HF cached models into ComfyUI
├── workflow-example.json       # Example text-to-image workflow
├── .github/workflows/
│   └── docker-build.yml        # GitHub Actions CI/CD
└── README.md                   # This file
```

## License

See Z-Image Turbo's official license. This worker code is provided as-is for deployment convenience.
