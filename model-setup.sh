#!/bin/bash
set -e

# Symlink Z-Image model files from RunPod's HF cache into ComfyUI model directories.
#
# Supports two repo structures:
#   1. Custom repo (files at root):
#      qwen_3_4b.safetensors
#      z_image_bf16.safetensors (or z_image_turbo_bf16.safetensors)
#      ae.safetensors
#
#   2. HF repo with split_files/ (e.g. Floppyshy/z_image):
#      split_files/text_encoders/qwen_3_4b.safetensors
#      split_files/diffusion_models/z_image_bf16.safetensors
#      split_files/vae/ae.safetensors
#      split_files/loras/*.safetensors
#
# These are linked into:
#   /comfyui/models/text_encoders/
#   /comfyui/models/diffusion_models/
#   /comfyui/models/unet/
#   /comfyui/models/vae/
#   /comfyui/models/loras/

HF_CACHE="/runpod-volume/huggingface-cache/hub"
REPO="${ZIMAGE_HF_REPO:-Comfy-Org/z_image_turbo}"
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

find_in_cache() {
    local base="$1"
    local filename="$2"
    local subpath="$3"

    # Try root first
    if [ -f "$base/$filename" ]; then
        echo "$base/$filename"
        return 0
    fi

    # Try split_files/ subdirectory (official Comfy-Org repo structure)
    if [ -n "$subpath" ] && [ -f "$base/$subpath/$filename" ]; then
        echo "$base/$subpath/$filename"
        return 0
    fi

    return 1
}

if [ -f "$HF_CACHE/$REPO_DIR/refs/main" ]; then
    SNAP=$(cat "$HF_CACHE/$REPO_DIR/refs/main")
    BASE="$HF_CACHE/$REPO_DIR/snapshots/$SNAP"

    echo "[model-setup] Using cached HF snapshot: $SNAP for repo $REPO"

    # Text encoder
    SRC=$(find_in_cache "$BASE" "qwen_3_4b.safetensors" "split_files/text_encoders")
    if [ -n "$SRC" ]; then
        link_model "$SRC" /comfyui/models/text_encoders
    else
        echo "[model-setup] WARNING: qwen_3_4b.safetensors not found in HF cache"
    fi

    # Diffusion model (non-turbo base, or fallback to turbo for backwards compat)
    # Link to both diffusion_models and unet for compatibility
    SRC=$(find_in_cache "$BASE" "z_image_bf16.safetensors" "split_files/diffusion_models")
    if [ -n "$SRC" ]; then
        link_model "$SRC" /comfyui/models/diffusion_models
        link_model "$SRC" /comfyui/models/unet
    else
        # Fallback: look for legacy turbo filename
        SRC=$(find_in_cache "$BASE" "z_image_turbo_bf16.safetensors" "split_files/diffusion_models")
        if [ -n "$SRC" ]; then
            link_model "$SRC" /comfyui/models/diffusion_models
            link_model "$SRC" /comfyui/models/unet
        else
            echo "[model-setup] WARNING: No diffusion model found in HF cache"
        fi
    fi

    # VAE
    SRC=$(find_in_cache "$BASE" "ae.safetensors" "split_files/vae")
    if [ -n "$SRC" ]; then
        link_model "$SRC" /comfyui/models/vae
    else
        echo "[model-setup] WARNING: ae.safetensors not found in HF cache"
    fi

    # LoRAs (e.g. step reducer for txt2img speedup)
    for lora in "$BASE"/*.safetensors "$BASE"/split_files/loras/*.safetensors; do
        [ -e "$lora" ] || continue
        link_model "$lora" /comfyui/models/loras
    done

    # Also support GGUF variants if present
    for gguf in "$BASE"/*.gguf "$BASE"/split_files/*/*.gguf; do
        [ -e "$gguf" ] || continue
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
exec /start.sh
