# RunPod ComfyUI Serverless Endpoint

A generic [RunPod](https://www.runpod.io/) serverless worker for [ComfyUI](https://github.com/comfyanonymous/ComfyUI). Built on top of the official RunPod ComfyUI base image with model caching via RunPod's HuggingFace integration.

## Features

- **Raw ComfyUI workflow JSON** input — full flexibility for any model, LoRA, ControlNet, etc.
- **Pre-cached models** — fast cold starts via RunPod HF Model Cache
- **AES-256-GCM payload encryption** for all requests and responses
- **Custom image-loading nodes** — load images from base64, URL, or encrypted payloads
- **GGUF support** via ComfyUI-GGUF custom node for lower VRAM setups

## Quick Start

### 1. Upload Models to HuggingFace

Create a private or public HF repo and upload your model files in the same layout ComfyUI expects under `models/`:

```bash
# Example structure
huggingface-cli upload your-username/comfy-models text_encoders/your_encoder.safetensors
huggingface-cli upload your-username/comfy-models diffusion_models/your_model.safetensors
huggingface-cli upload your-username/comfy-models vae/your_vae.safetensors
huggingface-cli upload your-username/comfy-models loras/your_lora.safetensors
```

The model-setup script mirrors this tree into `/comfyui/models/` at startup, so any ComfyUI model directory (e.g. `unet/`, `checkpoints/`, `clip/`, `loras/`) is supported automatically.

### 2. Build the Docker Image

Push to this repo's `main` branch — GitHub Actions will build and push to GHCR automatically.

Or build locally:

```bash
docker build -t runpod-comfyui-worker .
```

### 3. Create RunPod Serverless Endpoint

1. Go to [RunPod Serverless Console](https://www.runpod.io/console/serverless)
2. Click **New Endpoint**
3. Under **Source**, connect this GitHub repo
4. Select branch: `main`
5. Under **Model Caching**, add your HF repo ID (e.g. `your-username/comfy-models`)
6. GPU: Select a GPU with enough VRAM for your chosen models
7. Set the `COMFY_ENCRYPTION_KEY` environment variable (required for AES encryption)
8. Deploy

### 4. Send a Request

All requests must be encrypted with AES-256-GCM using the `COMFY_ENCRYPTION_KEY`. The `input` object must contain a base64-encoded `"encrypted"` field whose decrypted value is the request JSON.

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d '{
    "input": {
      "encrypted": "<base64(nonce + ciphertext)>"
    }
  }'
```

The decrypted payload must contain `workflow`. Images must be embedded directly in the workflow using `LoadImageBase64`, `LoadImageUrl`, or `LoadImageEncrypted` nodes; the legacy `images` array is no longer accepted.

## API Reference

### Input

The request body sent to RunPod must be:

```json
{
  "input": {
    "encrypted": "<base64(nonce + ciphertext)>"
  }
}
```

The decrypted payload contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow` | object | ✅ | ComfyUI API workflow JSON (node graph) |

### Output

```json
{
  "images": [
    {
      "data": "<base64(nonce + ciphertext)>",
      "type": "png",
      "encrypted": true
    }
  ]
}
```

### Payload Encryption

Requests and responses are encrypted with AES-256-GCM using the `COMFY_ENCRYPTION_KEY` (64 hex chars = 32 bytes). The request body must contain an `encrypted` field:

```json
{
  "input": {
    "encrypted": "<base64(nonce + ciphertext)>"
  }
}
```

The decrypted payload must be a JSON object with `workflow`. Images must be embedded directly in the workflow using `LoadImageBase64`, `LoadImageUrl`, or `LoadImageEncrypted` nodes. Output images are returned encrypted and include `"encrypted": true`.

## Custom Nodes

The worker ships with three custom image-loading nodes under `comfyui_custom_nodes/load_image/`. They can be used in raw ComfyUI workflows in place of the built-in `LoadImage` node.

### `LoadImageBase64`

Accepts a base64-encoded image string and returns `(IMAGE, MASK)` tensors just like ComfyUI's `LoadImage`.

| Input | Type | Description |
|-------|------|-------------|
| `image_base64` | `STRING` | Base64-encoded PNG/JPEG (data-URI prefix such as `data:image/png;base64,` is allowed) |

### `LoadImageUrl`

Downloads an image from a public URL and returns `(IMAGE, MASK)` tensors.

| Input | Type | Description |
|-------|------|-------------|
| `url` | `STRING` | Public image URL (`http://` or `https://`) |

### `LoadImageEncrypted`

Decrypts an AES-256-GCM encrypted payload with `COMFY_ENCRYPTION_KEY`, then delegates to `LoadImageUrl` if the plaintext is a URL or `LoadImageBase64` if it is base64 image data.

| Input | Type | Description |
|-------|------|-------------|
| `encrypted_base64` | `STRING` | AES-256-GCM encrypted base64 string. Decrypted plaintext must be either a URL or base64 image data. |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_BASE` | `/comfyui/models` | Root directory where cached models are symlinked |
| `HF_ORG` | *(none)* | Hugging Face organization / user that owns the model repo |
| `HF_REPO` | *(none)* | Hugging Face repo name containing the cached models |
| `COMFY_ENCRYPTION_KEY` | *(none)* | **Required.** 64 hex chars for AES-256-GCM encryption |

## Low VRAM / GGUF

For GPUs with limited VRAM, use GGUF quantized models with the pre-installed `ComfyUI-GGUF` custom node. Use the `GGUFModelLoader` and `GGUFCLIPLoader` nodes in your workflow.

## Project Structure

```
.
├── Dockerfile                  # ComfyUI base image + custom nodes
├── handler.py                  # Thin RunPod serverless entrypoint
├── comfyui_custom_nodes/       # ComfyUI custom nodes
│   └── load_image/
│       ├── __init__.py
│       ├── load_image_base64.py
│       ├── load_image_url.py
│       ├── load_image_encrypted.py
│       └── shared.py
├── comfy_worker/               # Handler implementation package
│   ├── __init__.py
│   ├── crypto.py               # AES-256-GCM encryption helpers
│   ├── comfy_client.py         # ComfyUI HTTP client
│   ├── env.py                  # Centralized environment variables
│   ├── setup_models.py         # Links cached models into ComfyUI model paths
│   └── core.py                 # Request handler orchestration
├── pre-start.sh                # Pre-start hook: model setup, then /start.sh
├── .github/workflows/
│   └── docker-build.yml        # GitHub Actions CI/CD
└── README.md                   # This file
```

## License

This worker code is provided as-is for deployment convenience.
