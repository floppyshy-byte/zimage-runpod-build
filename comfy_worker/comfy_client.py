"""ComfyUI HTTP client."""

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

COMFYUI_URL = "http://127.0.0.1:8188"


class ComfyClient:
    def __init__(self, base_url: str, default_timeout: int = 30):
        self.base_url = base_url
        self.default_timeout = default_timeout

    def wait_for_comfyui(self, timeout: int = 120) -> None:
        """Block until ComfyUI's HTTP API responds or timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{self.base_url}/system_stats", timeout=3)
                return
            except Exception:
                time.sleep(2)
        print(f"[handler] FATAL: ComfyUI did not start within {timeout}s, killing container")
        os._exit(1)

    def upload_image(self, name: str, image_b64: str) -> None:
        """Upload a base64-encoded image to ComfyUI's input directory.

        TODO: This method is only needed while workflow building/patching lives in
        this repo (specifically the `init_image` convenience path). Once all
        workflow construction logic is moved out, remove this method.
        """
        img_bytes = base64.b64decode(image_b64)
        boundary = "runpod-upload-boundary"
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
                f"Content-Type: image/png\r\n\r\n"
            ).encode()
            + img_bytes
            + f"\r\n--{boundary}--\r\n".encode()
        )
        req = urllib.request.Request(
            f"{self.base_url}/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=self.default_timeout) as resp:
            resp.read()

    def queue_prompt(self, workflow: dict) -> str:
        """Submit a ComfyUI workflow and return the prompt_id."""
        data = json.dumps({"prompt": workflow}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.default_timeout) as resp:
                return json.loads(resp.read())["prompt_id"]
        except Exception as exc:
            exc_type = type(exc).__name__
            if hasattr(exc, "code") and hasattr(exc, "read"):
                body = exc.read().decode(errors="replace")
                raise RuntimeError(f"ComfyUI /prompt returned {exc.code}: {body}") from exc
            raise RuntimeError(f"ComfyUI /prompt error [{exc_type}]: {exc}") from exc

    def poll_history(self, prompt_id: str, timeout: int = 600) -> dict:
        """Poll ComfyUI history until prompt completes; return the history entry."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"{self.base_url}/history/{prompt_id}", timeout=10
                ) as resp:
                    history = json.loads(resp.read())
                if prompt_id in history:
                    return history[prompt_id]
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError(f"Prompt {prompt_id} did not complete within {timeout}s")

    def fetch_image_b64(self, filename: str, subfolder: str, folder_type: str) -> str:
        """Fetch an output image from ComfyUI and return as base64."""
        params = urllib.parse.urlencode(
            {"filename": filename, "subfolder": subfolder, "type": folder_type}
        )
        with urllib.request.urlopen(
            f"{self.base_url}/view?{params}", timeout=self.default_timeout
        ) as resp:
            return base64.b64encode(resp.read()).decode()
