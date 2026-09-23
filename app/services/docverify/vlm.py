"""Optional vision-language reasoner (Qwen-VL, Gemini, or any model behind an
OpenAI-compatible /chat/completions endpoint).

Strictly advisory: it only produces a plain-language explanation of the
deterministic evidence. It never decodes QR/barcodes, never evaluates MRZ
check digits, signatures or registries, and never changes a check status.
Disabled unless PRAMAAN_VLM_BASE_URL is set; the document image is sent only
when PRAMAAN_VLM_SEND_IMAGE=true (otherwise only the redacted evidence text).
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.request
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("pramaan.docverify.vlm")

_SYSTEM = (
    "You assist a border officer. Explain, in two or three plain sentences, what the listed verification "
    "evidence means and what the officer may want to look at. Do not declare the document genuine or fake, "
    "do not mention criminality, and do not add facts that are not in the evidence."
)


def explain(evidence_lines: list[str], image_bytes: bytes | None) -> dict[str, Any]:
    s = get_settings()
    if not s.pramaan_vlm_base_url or not s.pramaan_vlm_model:
        return {"status": "NOT_CONFIGURED", "reason": "no vision-language model is configured"}
    content: list[dict[str, Any]] = [{"type": "text", "text": "Evidence:\n- " + "\n- ".join(evidence_lines[:25])}]
    if image_bytes and s.pramaan_vlm_send_image:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()}})
    body = json.dumps({"model": s.pramaan_vlm_model, "temperature": 0,
                       "messages": [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": content}]})
    req = urllib.request.Request(s.pramaan_vlm_base_url.rstrip("/") + "/chat/completions", data=body.encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {s.pramaan_vlm_api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=s.pramaan_vlm_timeout_seconds) as resp:
            data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("VLM call failed: %s", exc)
        return {"status": "ERROR", "reason": f"reasoner unavailable ({type(exc).__name__})"}
    return {"status": "OK", "model": s.pramaan_vlm_model, "text": text.strip()[:1200],
            "image_sent": bool(image_bytes and s.pramaan_vlm_send_image),
            "note": "Advisory explanation only — it does not change any check result."}
