"""AI client seam (mirrors v1's get_recommender() philosophy).

get_ai_client() returns a client for the configured provider when the master
switch is on, else a NullClient. Every caller must handle AIUnavailable — the
system is fully functional without AI.

Two providers share this seam:

* OllamaClient  — on-premises, loopback-only by default (V2's model, kept
  intact for agencies running the system on their own hardware).
* HostedClient  — a hosted API, for cloud deployments where no GPU host is
  available. The credential comes from the server environment, never the DB.

Both return plain text and both raise AIUnavailable on any failure, so no
caller has to care which one is active.
"""
import json
import logging
import time
import urllib.request
import urllib.error

from django.conf import settings as django_settings

from ai.models import AISetting, AIJob

logger = logging.getLogger(__name__)

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


class HostedClient:
    """Hosted-API provider for cloud deployments (Anthropic Messages API).

    The API key is read from the server environment, not from AISetting, so an
    administrator can switch providers through the UI without ever being able
    to read or set the credential. No key configured == provider unavailable,
    which degrades exactly like an unreachable Ollama: features report 503 and
    the rest of the system carries on.
    """

    available = True

    def __init__(self, model, api_key, base_url="", max_tokens=8000, timeout=120):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.timeout = timeout

    def generate(self, prompt, system=None):
        if not self.api_key:
            raise AIUnavailable(
                "Hosted AI provider is selected but no API key is configured on "
                "the server (AI_HOSTED_API_KEY)."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise AIUnavailable(f"Hosted AI provider SDK is not installed: {exc}") from exc

        client_kwargs = {"api_key": self.api_key, "timeout": self.timeout}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = anthropic.Anthropic(**client_kwargs)

        request = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            # Child-protection casework legitimately discusses abuse, neglect
            # and self-harm, which safety classifiers can decline. Server-side
            # fallbacks re-run a declined request on another model inside the
            # same call, so a routine clinical draft is not lost to a false
            # positive. A refusal that survives the whole chain is handled below.
            "betas": ["server-side-fallback-2026-07-01"],
            "fallbacks": "default",
        }
        if system:
            request["system"] = system

        try:
            response = client.beta.messages.create(**request)
        except anthropic.APIStatusError as exc:
            raise AIUnavailable(
                f"Hosted AI provider returned {exc.status_code}: {exc.message}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise AIUnavailable(f"Hosted AI provider unreachable: {exc}") from exc

        # stop_reason must be checked before touching content: a refused
        # request returns HTTP 200 with an empty or partial content list.
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise AIUnavailable(
                "The hosted AI provider declined this request"
                + (f" ({category})." if category else ".")
                + " Write the note manually — no draft was produced."
            )

        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()


def get_ai_client(setting=None):
    setting = setting or AISetting.load()
    if not setting.enabled:
        return NullClient()
    if setting.provider == AISetting.HOSTED:
        return HostedClient(
            model=setting.hosted_model,
            api_key=django_settings.AI_HOSTED_API_KEY,
            base_url=django_settings.AI_HOSTED_BASE_URL,
            max_tokens=django_settings.AI_HOSTED_MAX_TOKENS,
            timeout=django_settings.AI_HOSTED_TIMEOUT,
        )
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
                             error=str(exc)[:255], model_used=setting.active_model,
                             created_by=user)
        raise
    text = _normalize_output(text)
    latency = int((time.monotonic() - started) * 1000)
    job = AIJob.objects.create(
        job_type=job_type, input_ref=input_ref, output_text=text,
        model_used=setting.active_model, latency_ms=latency, ok=True, created_by=user)
    return text, job
