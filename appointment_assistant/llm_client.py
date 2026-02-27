from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - handled gracefully at runtime
    OpenAI = None  # type: ignore


def _get_client() -> Optional["OpenAI"]:
    """
    Returns an OpenAI client if OPENAI_API_KEY is set and the library is installed.
    Otherwise returns None so callers can gracefully fall back.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    return OpenAI(api_key=api_key)


def parse_appointment_with_llm(user_text: str) -> Optional[Dict[str, Any]]:
    """
    Use a real LLM to parse the user's message into an appointment structure.

    Expected return structure (matches the rule-based parser in agents.py):
    {
        "title": str,
        "start": datetime,
        "end": datetime,
        "location": Optional[str],
        "notes": str,
        "date_only": bool,
        "duration_minutes": int,
    }
    """
    client = _get_client()
    if client is None:
        return None

    now_iso = datetime.now().isoformat()

    system_prompt = (
        "You are an assistant that extracts structured appointment information from a user's message.\n"
        "Always respond with a single JSON object ONLY, no extra text.\n"
        "Fields:\n"
        "- title: short description of the appointment (string)\n"
        "- start: ISO 8601 datetime string for when the appointment starts (e.g. '2026-03-01T15:00:00')\n"
        "- end: ISO 8601 datetime string for when the appointment ends\n"
        "- location: string or null\n"
        "- notes: echo or lightly cleaned version of the user's request (string)\n"
        "- duration_minutes: integer duration in minutes\n"
        "- date_only: boolean – true if the user clearly specified only a date (no explicit time);\n"
        "  in that case, choose a reasonable default time but still fill start/end.\n\n"
        f"Assume the current datetime is {now_iso}. Use it to interpret words like 'today' or 'tomorrow'."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "User message:\n"
                f"{user_text}\n\n"
                "Return ONLY the JSON object, nothing else."
            ),
        },
    ]

    try:
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content or ""
        data = json.loads(content)
    except Exception:
        # Any error (API, JSON parsing, etc.) -> fall back to rule-based parser
        return None

    try:
        start_raw = data.get("start")
        end_raw = data.get("end")
        if not start_raw or not end_raw:
            return None
        start_dt = datetime.fromisoformat(start_raw)
        end_dt = datetime.fromisoformat(end_raw)

        duration_minutes = data.get("duration_minutes")
        if duration_minutes is None:
            duration_minutes = int((end_dt - start_dt).total_seconds() // 60) or 30

        parsed: Dict[str, Any] = {
            "title": data.get("title") or "appointment",
            "start": start_dt,
            "end": end_dt,
            "location": data.get("location"),
            "notes": data.get("notes") or user_text,
            "date_only": bool(data.get("date_only", False)),
            "duration_minutes": int(duration_minutes),
        }
        return parsed
    except Exception:
        # If the LLM output isn't in the expected format, let the caller fall back.
        return None

