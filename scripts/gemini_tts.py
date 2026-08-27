#!/usr/bin/env python3
"""Isolated Gemini TTS adapter for the Hindi animated story writer skill.

Uses ONLY the Python 3 standard library (json, os, base64, wave,
urllib.request, urllib.error). No third-party packages.

This is the ONLY file that knows how to talk to Gemini. All Gemini-specific
request shaping, endpoint details, and response parsing live here so the rest
of the pipeline stays provider-agnostic.

Key handling:
  - The API key is read from the GEMINI_API_KEY environment variable
    (or passed explicitly). It is NEVER hardcoded, NEVER committed, and
    NEVER printed in full. Error messages mask it via _mask().

There is NO network activity at import time.

Public API:
  get_api_key(explicit=None) -> str
  synthesize_line(text, voice_name, language_code="hi-IN", api_key=None,
                  model="gemini-2.5-flash-preview-tts") -> bytes  (raw PCM)
  pcm_to_wav(pcm_bytes, out_path, rate=24000) -> None
Exceptions:
  GeminiConfigError  — missing/invalid configuration (e.g. no API key).
  GeminiAPIError     — request/transport/parse failure (message masks the key).
"""

import base64
import json
import os
import wave

import urllib.error
import urllib.request


API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
)


class GeminiConfigError(Exception):
    """Raised for missing or invalid configuration (e.g. no API key)."""


class GeminiAPIError(Exception):
    """Raised on request/transport/parse failure. Messages MUST mask the key."""


def get_api_key(explicit=None):
    """Return the Gemini API key.

    Prefers an explicitly provided key, otherwise reads GEMINI_API_KEY from the
    environment. Raises GeminiConfigError if none is available.
    """
    key = explicit if explicit else os.environ.get(API_KEY_ENV)
    if not key or not str(key).strip():
        raise GeminiConfigError(
            "No Gemini API key found. Set the %s environment variable "
            "(export %s=...) or pass api_key explicitly." % (API_KEY_ENV, API_KEY_ENV)
        )
    return str(key).strip()


def _mask(key):
    """Return a masked form of the key, e.g. first4 + '…' + last2.

    Never returns the full key. Safe to embed in error messages/logs.
    """
    if not key:
        return "<none>"
    key = str(key)
    if len(key) <= 6:
        return (key[:1] + "…") if key else "<none>"
    return key[:4] + "…" + key[-2:]


def _scrub(message, key):
    """Ensure the raw key never leaks into a message string."""
    if key and key in message:
        message = message.replace(key, _mask(key))
    return message


def synthesize_line(text, voice_name, language_code="hi-IN", api_key=None,
                    model=DEFAULT_MODEL):
    """Synthesize a single line of speech via Gemini TTS.

    Returns raw PCM audio bytes (signed 16-bit little-endian, mono, 24000 Hz).
    Raises GeminiConfigError if no key; GeminiAPIError on any transport or
    parse failure (with the key masked in the message).
    """
    key = get_api_key(api_key)

    body = {
        "contents": [
            {"parts": [{"text": text}]}
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                },
                "languageCode": language_code,
            },
        },
    }

    url = _ENDPOINT_TEMPLATE % model
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        msg = "Gemini API HTTP error %s (key %s): %s" % (
            getattr(exc, "code", "?"), _mask(key), detail
        )
        raise GeminiAPIError(_scrub(msg, key))
    except urllib.error.URLError as exc:
        msg = "Gemini API connection error (key %s): %s" % (_mask(key), exc.reason)
        raise GeminiAPIError(_scrub(str(msg), key))

    try:
        payload = json.loads(raw.decode("utf-8"))
        b64 = payload["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        pcm = base64.b64decode(b64)
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        msg = "Failed to parse Gemini audio response (key %s): %s" % (
            _mask(key), exc
        )
        raise GeminiAPIError(_scrub(str(msg), key))

    return pcm


def pcm_to_wav(pcm_bytes, out_path, rate=24000):
    """Write raw signed 16-bit mono PCM bytes to a WAV file.

    nchannels=1, sampwidth=2 (16-bit), framerate=rate (default 24000).
    """
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
