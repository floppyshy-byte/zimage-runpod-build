FROM runpod/worker-comfyui:5.8.5-base

# Prevent custom nodes from auto-downloading models during build
RUN touch /comfyui/custom_nodes/skip_download_model

# ── Local custom nodes ───────────────────────────────────────────────────────

# ComfyUI-GGUF — supports GGUF quantized models (Q5_K_S, etc.) for low VRAM
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/city96/ComfyUI-GGUF && \
    cd ComfyUI-GGUF && \
    pip install -r requirements.txt -q

# Local custom nodes
COPY comfyui_custom_nodes /comfyui/custom_nodes/comfyui_custom_nodes

# ── HANDLER + SETUP ─────────────────────────────────────────────────────────

# Install cryptography for AES-256-GCM payload encryption
RUN pip install --no-cache-dir cryptography

# Override the base image handler with our custom one
COPY handler.py /handler.py
COPY comfy_worker /comfy_worker

# Pre-start hook: runs model setup before the base image starts ComfyUI
COPY pre-start.sh /pre-start.sh
RUN chmod +x /pre-start.sh

# Wrap the original startup so setup runs before ComfyUI starts
ENTRYPOINT ["/pre-start.sh"]
