#!/usr/bin/env python3
"""Reusable text-to-speech via OpenRouter's ``/audio/speech`` endpoint.

Defaults target Fish Audio S2.1 Pro Free (no charge) with a Japanese female
narrator voice. Override ``--model``/``--voice`` for other providers.

Examples:
    scripts/tts.py --file script.txt -o out.mp3
    scripts/tts.py --text "こんにちは" -o hello.mp3
    echo "こんにちは" | scripts/tts.py -o hello.mp3
    scripts/tts.py --file long.txt --model fish-audio/s2.1-pro --voice <voice-id>

Requires ``OPENROUTER_API_KEY`` (override the env var name with --api-key-env).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

_ENDPOINT = "https://openrouter.ai/api/v1/audio/speech"
_DEFAULT_MODEL = "fish-audio/s2.1-pro-free:free"
_DEFAULT_VOICE = "f1d92c18f84e47c6b5bc0cebb80ddaf5"
_MAX_RETRIES = 3
_RETRYABLE = (429, 502, 503)


def _read_input(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _synthesize(
    text: str, *, model: str, voice: str, fmt: str, api_key: str, timeout: int
) -> bytes:
    payload = {"model": model, "input": text, "voice": voice, "response_format": fmt}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/petadimensionlab/AutoResearchClaw",
        "X-Title": "AutoResearchClaw TTS",
    }
    last_error: str = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        request = urllib.request.Request(
            _ENDPOINT, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            if data[:1] == b"{":
                raise RuntimeError(
                    "unexpected JSON response: "
                    + data[:300].decode("utf-8", "replace")
                )
            return data
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            last_error = f"HTTP {exc.code}: {body}"
            if exc.code in _RETRYABLE and attempt < _MAX_RETRIES:
                wait = 2 ** attempt
                print(
                    f"[tts] HTTP {exc.code}; retry {attempt}/{_MAX_RETRIES} in {wait}s",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise RuntimeError(last_error) from exc
        except (urllib.error.URLError, OSError) as exc:
            last_error = str(exc)
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(last_error) from exc
    raise RuntimeError(last_error)


def _default_out(fmt: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("artifacts") / "audio" / f"tts-{stamp}.{fmt}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Text-to-speech via OpenRouter /audio/speech."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="Inline text to synthesize")
    source.add_argument("--file", help="Path to a UTF-8 text file")
    parser.add_argument(
        "-o", "--out", help="Output audio path (default: artifacts/audio/tts-<ts>.<fmt>)"
    )
    parser.add_argument(
        "--model", default=_DEFAULT_MODEL, help=f"TTS model id (default: {_DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--voice", default=_DEFAULT_VOICE, help="Provider voice id"
    )
    parser.add_argument(
        "--format", default="mp3",
        choices=["mp3", "wav", "flac", "opus", "pcm"], help="Audio format",
    )
    parser.add_argument(
        "--api-key-env", default="OPENROUTER_API_KEY",
        help="Env var holding the OpenRouter API key",
    )
    parser.add_argument("--timeout", type=int, default=240, help="Request timeout (s)")
    args = parser.parse_args(argv)

    text = _read_input(args).strip()
    if not text:
        print("error: no input text (use --text/--file or pipe stdin)", file=sys.stderr)
        return 2

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print(f"error: {args.api_key_env} is not set", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else _default_out(args.format)
    out.parent.mkdir(parents=True, exist_ok=True)

    if len(text) > 3000:
        print(
            f"[tts] warning: input is {len(text)} chars; some providers cap at 3000",
            file=sys.stderr,
        )

    print(f"[tts] model={args.model} voice={args.voice} chars={len(text)}")
    try:
        data = _synthesize(
            text, model=args.model, voice=args.voice, fmt=args.format,
            api_key=api_key, timeout=args.timeout,
        )
    except RuntimeError as exc:
        print(f"[tts] error: {exc}", file=sys.stderr)
        return 1

    out.write_bytes(data)
    print(f"[tts] ok bytes={len(data)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
