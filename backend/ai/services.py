"""Local AI client seam (mirrors v1's get_recommender() philosophy).

get_ai_client() returns an OllamaClient when the master switch is on, else a
NullClient. Every caller must handle AIUnavailable — the system is fully
functional without AI.
"""
import json
import time
import urllib.request
import urllib.error

from ai.models import AISetting, AIJob

DISCLAIMER = ("AI-drafted decision support, not a diagnosis. The licensed "
              "psychologist reviews, edits, and approves all content.")


class AIUnavailable(Exception):
    pass


class NullClient:
    available = False

    def generate(self, prompt, system=None):
        raise AIUnavailable("AI assistance is switched off.")


class OllamaClient:
    available = True

    def __init__(self, base_url, model):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt, system=None):
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return (data.get("response") or "").strip()
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIUnavailable(f"Local AI runtime unreachable: {exc}") from exc


def get_ai_client(setting=None):
    setting = setting or AISetting.load()
    if not setting.enabled:
        return NullClient()
    return OllamaClient(setting.ollama_url, setting.model_name)


def feature_enabled(feature):
    s = AISetting.load()
    return s.enabled and getattr(s, f"feature_{feature}", False)


_PUNCT_MAP = {"‘": "'", "’": "'", "“": '"', "”": '"',
              "–": "-", "—": "-", " ": " "}


def _normalize_output(text):
    """Small local models emit curly quotes/dashes that render as mojibake in
    some consoles and PDFs — normalize deterministically instead of prompting."""
    for bad, good in _PUNCT_MAP.items():
        text = text.replace(bad, good)
    return text


def run_job(job_type, input_ref, prompt, system, user):
    """Run one audited AI call. Returns (text, job). Raises AIUnavailable."""
    setting = AISetting.load()
    client = get_ai_client(setting)
    started = time.monotonic()
    try:
        text = client.generate(prompt, system=system)
    except AIUnavailable as exc:
        AIJob.objects.create(job_type=job_type, input_ref=input_ref, ok=False,
                             error=str(exc)[:255], model_used=setting.model_name,
                             created_by=user)
        raise
    text = _normalize_output(text)
    latency = int((time.monotonic() - started) * 1000)
    job = AIJob.objects.create(
        job_type=job_type, input_ref=input_ref, output_text=text,
        model_used=setting.model_name, latency_ms=latency, ok=True, created_by=user)
    return text, job
