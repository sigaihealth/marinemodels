"""Ask the OOI loopback vision model about one or more local ROV images."""
import base64
import io
import json
from pathlib import Path
import urllib.request

from PIL import Image, ImageOps

ROOT = Path.home() / "data/ocean-platform/visual-transect"
MODEL = "Qwen3-VL-8B-Instruct"


def ask(images, question):
    """Accept ordered (display name, filename or bytes) pairs and return the model reply."""
    if not images or len(images) > 8:
        raise ValueError("Choose between one and eight images.")
    if not question.strip():
        raise ValueError("Enter a question about the selected images.")
    content = [{"type": "text", "text": question.strip()}]
    for label, src in images:
        if isinstance(src, (bytes, bytearray, memoryview)):
            src = io.BytesIO(src)
        with Image.open(src) as raw:
            img = ImageOps.exif_transpose(raw).convert("RGB")
            img.thumbnail((768, 768))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=90)
        encoded = base64.b64encode(out.getvalue()).decode("ascii")
        content.extend([{"type": "text", "text": label},
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}}])
    body = {"model": MODEL, "temperature": 0.1, "max_tokens": 700, "stream": False,
            "messages": [{"role": "system", "content": "You are assisting a marine survey reviewer. Separate visible evidence from inference. Cite the supplied frame names. Flag uncertainty for identity, exact counts and taxonomy."},
                         {"role": "user", "content": content}]}
    request = urllib.request.Request("http://127.0.0.1:18733/v1/chat/completions",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + (ROOT / ".vision-key").read_text().strip()},
        data=json.dumps(body).encode())
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=240) as response:
        result = json.load(response)
    if result["model"] != MODEL:
        raise RuntimeError("Unexpected served model")
    choice = result["choices"][0]
    return choice["message"]["content"] + ("\n[Response reached the token limit.]" if choice["finish_reason"] == "length" else "")
