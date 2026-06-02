FROM runpod/worker-comfyui:5.8.5-base

# Prevent custom nodes from auto-downloading models during build
RUN touch /comfyui/custom_nodes/skip_download_model

# ── Z-Image specific custom nodes ────────────────────────────────────────────

# ComfyUI-GGUF — supports GGUF quantized models (Q5_K_S, etc.) for low VRAM
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/city96/ComfyUI-GGUF && \
    cd ComfyUI-GGUF && \
    pip install -r requirements.txt -q

# ── HANDLER + SETUP ─────────────────────────────────────────────────────────

# Install cryptography for AES-256-GCM payload encryption
RUN pip install --no-cache-dir cryptography

# Override the base image handler with our custom one
COPY handler.py /handler.py

# Model setup script: symlinks pre-cached HF models into ComfyUI paths
COPY model-setup.sh /model-setup.sh
RUN chmod +x /model-setup.sh

# Wrap the original startup so models are linked before ComfyUI starts
ENTRYPOINT ["/model-setup.sh"]
CMD ["/start.sh"]
