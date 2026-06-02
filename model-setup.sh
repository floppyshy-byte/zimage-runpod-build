#!/bin/bash
set -e

# Symlink Z-Image model files from RunPod's HF cache into ComfyUI model directories.
#
# Expected HF repo structure (e.g. floppyshy-byte/z-image-models):
#   qwen_3_4b.safetensors
#   z_image_turbo_bf16.safetensors
#   ae.safetensors
#
# These are linked into:
#   /comfyui/models/text_encoders/
#   /comfyui/models/diffusion_models/
#   /comfyui/models/vae/

HF_CACHE="/runpod-volume/huggingface-cache/hub"
REPO="${ZIMAGE_HF_REPO:-floppyshy-byte/z-image-models}"
REPO_DIR="models--${REPO//\//--}"

link_model() {
    local src="$1"
    local dst_dir="$2"
    local dst="$dst_dir/$(basename "$src")"

    mkdir -p "$dst_dir"

    if [ ! -L "$dst" ] || [ "$(readlink "$dst")" != "$src" ]; then
        ln -sf "$src" "$dst"
        echo "[model-setup] Linked $(basename "$src") -> $dst_dir"
    else
        echo "[model-setup] Already linked: $(basename "$src")"
    fi
}

if [ -f "$HF_CACHE/$REPO_DIR/refs/main" ]; then
    SNAP=$(cat "$HF_CACHE/$REPO_DIR/refs/main")
    BASE="$HF_CACHE/$REPO_DIR/snapshots/$SNAP"

    echo "[model-setup] Using cached HF snapshot: $SNAP for repo $REPO"

    # Text encoder
    if [ -f "$BASE/qwen_3_4b.safetensors" ]; then
        link_model "$BASE/qwen_3_4b.safetensors" /comfyui/models/text_encoders
    else
        echo "[model-setup] WARNING: qwen_3_4b.safetensors not found in HF cache"
    fi

    # Diffusion model (link to both diffusion_models and unet for compatibility)
    if [ -f "$BASE/z_image_turbo_bf16.safetensors" ]; then
        link_model "$BASE/z_image_turbo_bf16.safetensors" /comfyui/models/diffusion_models
        link_model "$BASE/z_image_turbo_bf16.safetensors" /comfyui/models/unet
    else
        echo "[model-setup] WARNING: z_image_turbo_bf16.safetensors not found in HF cache"
    fi

    # VAE
    if [ -f "$BASE/ae.safetensors" ]; then
        link_model "$BASE/ae.safetensors" /comfyui/models/vae
    else
        echo "[model-setup] WARNING: ae.safetensors not found in HF cache"
    fi

    # Also support GGUF variants if present
    for gguf in "$BASE"/*.gguf; do
        [ -e "$gguf" ] || continue
        # GGUF diffusion models go to diffusion_models, GGUF text encoders to text_encoders
        case "$(basename "$gguf")" in
            *diffusion*|*z_image*)
                link_model "$gguf" /comfyui/models/diffusion_models
                ;;
            *qwen*|*clip*)
                link_model "$gguf" /comfyui/models/text_encoders
                ;;
            *)
                link_model "$gguf" /comfyui/models/diffusion_models
                ;;
        esac
    done

else
    echo "[model-setup] WARNING: HF cache not found at $HF_CACHE/$REPO_DIR/refs/main"
    echo "[model-setup] Models may not be available. Continuing anyway..."
fi

# Delegate to the original base-image startup (starts ComfyUI + handler)
exec "$@"
