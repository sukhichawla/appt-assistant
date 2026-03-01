from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type, datetime, timedelta, time
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from appointment_assistant.calendar_store import Appointment, CalendarStore, check_business_hours
from appointment_assistant.llm_client import parse_appointment_with_llm


def _is_greeting(text: str) -> bool:
    """True if the user is only greeting or asking how we are (no booking/cancel/reschedule intent)."""
    t = text.lower().strip()
    greetings = (
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "howdy", "hi there", "hello there", "greetings", "hey there",
        "what's up", "sup", "yo", "good day", "morning", "afternoon",
    )
    if t in greetings:
        return True
    if len(t) <= 25 and t.endswith(("!", "?")) and any(g in t for g in ("hi", "hello", "hey")):
        return True
    # "How are you?" style – treat as greeting so we can reply warmly
    if any(p in t for p in ("how are you", "how're you", "how r u", "how are u", "how do you do")):
        return True
    return False


def _is_how_are_you(text: str) -> bool:
    """True if the user is asking how we are (for a warmer reply)."""
    t = text.lower().strip()
    return any(p in t for p in ("how are you", "how're you", "how r u", "how are u", "how do you do"))


def _looks_like_booking(text: str) -> bool:
    """True if the message looks like a booking-related request (book, schedule, time, date, etc.)."""
    t = text.lower().strip()
    booking_keywords = (
        "book", "schedule", "appointment", "meeting", "slot", "add", "set up",
        "reserve", "plan", "organize", "calendar", "cancel", "reschedule", "move",
    )
    if any(w in t for w in booking_keywords):
        return True
    # Time pattern: 1-12 + optional :mm + optional am/pm
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", t):
        return True
    # Date words
    date_words = ("today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "next week")
    if any(w in t for w in date_words):
        return True
    return False


def _is_out_of_scope(text: str) -> bool:
    """True if the question is clearly not about appointments (weather, jokes, etc.)."""
    t = text.lower().strip()
    out_of_scope_phrases = (
        "weather", "how is the weather", "what's the weather",
        "tell me a joke", "joke", "what time is it", "what's the time",
        "who are you", "what can you do", "help me with", "random",
        "news", "sports", "recipe", "movie", "music", "game",
    )
    if any(p in t for p in out_of_scope_phrases):
        return True
    # Short general questions that don't look like booking
    if len(t) > 10 and "?" in t and not _looks_like_booking(text):
        return True
    return False


def _detect_intent(text: str) -> str:
    """Returns 'greeting', 'list', 'cancel', 'reschedule', 'confirm_yes', 'confirm_no', 'out_of_scope', or 'create'."""
    t = text.lower().strip()
    if _is_greeting(text):
        return "greeting"
    if t in ("yes", "confirm", "ok", "sure", "yep"):
        return "confirm_yes"
    # "cancel it" and "delete it" are cancel/delete requests, not "no" to a pending confirm
    if t in ("no", "nope", "no thanks"):
        return "confirm_no"
    if _is_out_of_scope(text):
        return "out_of_scope"
    # Cancel: user says cancel/remove/delete (even without "appointment") so "can you cancel please" is cancel
    if any(w in t for w in ("cancel", "remove", "delete")):
        # Don't treat "reschedule/move ... to" as cancel
        if any(w in t for w in ("reschedule", "rebook", "change")) or ("move" in t and (" to " in t or " at " in t)):
            pass  # fall through to reschedule or create
        else:
            return "cancel"
    # Reschedule: user says reschedule/move/rebook/change (even without "appointment" or new time)
    # so "can you reschedule it" or "reschedule please" is reschedule
    if any(w in t for w in ("reschedule", "rebook", "change")) or (
        "move" in t and ("appointment" in t or "meeting" in t or " to " in t or " at " in t or " it " in t)
    ):
        return "reschedule"
    if any(w in t for w in ("list", "show", "what", "view", "see")) and any(
        w in t for w in ("appointment", "schedule", "calendar", "have", "booked")
    ):
        return "list"
    if not _looks_like_booking(text):
        return "out_of_scope"
    return "create"


@dataclass
class Message:
    sender: str
    content: str
    metadata: Dict[str, Any] | None = None


class ConversationContext:
    """
    Shared state between agents for a single user request.
    """

    def __init__(self, calendar: CalendarStore) -> None:
        self.calendar = calendar
        self.state: Dict[str, Any] = {}


class Agent:
    """
    Base class all agents derive from.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        raise NotImplementedError


def _message_looks_like_time_only(text: str) -> bool:
    """True if the message is short and contains a time but no date keyword (today/tomorrow/weekday)."""
    t = text.lower().strip()
    if len(t) > 50:
        return False
    has_time = bool(re.search(r"\d{1,2}\s*(am|pm)\b|\d{1,2}:\d{2}\b|at\s+\d{1,2}\b", t, re.IGNORECASE))
    if not has_time:
        return False
    date_words = ("today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    return not any(w in t for w in date_words)


def _message_looks_like_date_only(text: str) -> bool:
    """True if the message is short and contains a date keyword but no explicit time."""
    t = text.lower().strip()
    if len(t) > 50:
        return False
    date_words = ("today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    has_date = any(w in t for w in date_words)
    has_time = bool(re.search(r"\d{1,2}\s*(am|pm)\b|\d{1,2}:\d{2}\b", t, re.IGNORECASE))
    return has_date and not has_time


def _merge_parsed_with_last_context(
    parsed: Dict[str, Any], user_text: str, last_context: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    If we have last_booking_context and the current message looks like a follow-up
    (e.g. just "2pm" or just "tomorrow"), merge so we remember what we discussed.
    """
    if not last_context:
        return parsed
    t = user_text.lower().strip()
    start = last_context.get("start")
    if isinstance(start, datetime):
        last_date = start.date()
    else:
        last_date = getattr(start, "date", lambda: None)() if start else None
    last_title = last_context.get("title") or "appointment"
    last_duration = last_context.get("duration_minutes", 30)

    # User said only a time (e.g. "2pm", "how about 4pm") – use previous date + title
    if last_date and _message_looks_like_time_only(user_text):
        new_start = parsed["start"]
        merged_start = datetime.combine(last_date, new_start.time())
        merged_end = merged_start + timedelta(minutes=last_duration)
        return {
            **parsed,
            "title": last_title if (parsed.get("title") or "appointment") == "appointment" else parsed["title"],
            "start": merged_start,
            "end": merged_end,
            "date_only": False,
            "duration_minutes": last_duration,
        }

    # User said only a date (e.g. "tomorrow", "next Monday") – use previous title + new date
    if _message_looks_like_date_only(user_text) and last_title != "appointment":
        new_start = parsed["start"]
        merged_end = new_start + timedelta(minutes=last_duration)
        return {
            **parsed,
            "title": last_title,
            "start": new_start,
            "end": merged_end,
            "duration_minutes": last_duration,
        }

    return parsed


class NLUAgent(Agent):
    """
    Light‑weight natural language understanding agent.
    Uses last_booking_context from conversation when the current message is a follow-up
    (e.g. "2pm" after discussing a date, or "tomorrow" after discussing a title).
    """

    def __init__(self) -> None:
        super().__init__("NLUAgent")

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        user_text = message.content
        parsed: Optional[Dict[str, Any]] = None

        # Use LLM only if an API key is configured
        if os.getenv("OPENAI_API_KEY"):
            llm_parsed = parse_appointment_with_llm(user_text)
            if llm_parsed is not None:
                parsed = llm_parsed

        # Fallback: existing rule-based parser
        if parsed is None:
            parsed = self._simple_parse(user_text.lower())

        if parsed is None:
            return [
                Message(
                    sender=self.name,
                    content=(
                        "I couldn't confidently understand the appointment details. "
                        "Please include a date, time, and short description."
                    ),
                    metadata={"type": "nlu_error"},
                )
            ]

        # Merge with previous conversation context when user sends a follow-up (e.g. "2pm" or "tomorrow")
        last_context = context.state.get("last_booking_context")
        parsed = _merge_parsed_with_last_context(parsed, user_text, last_context)
        context.state["parsed_appointment"] = parsed

        if parsed.get("date_only"):
            content = (
                f"I see you want to book \"{parsed['title']}\" on "
                f"{parsed['start'].strftime('%A %d %B')}. Checking available slots."
            )
        else:
            content = (
                "I extracted an appointment request for "
                f"{parsed['title']} on {parsed['start'].strftime('%Y-%m-%d at %H:%M')}."
            )
        return [
            Message(
                sender=self.name,
                content=content,
                metadata={"type": "nlu_parsed", "appointment": parsed},
            )
        ]

    def _simple_parse(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Very small rule-based parser:
        - looks for times like '3pm', '15:30'
        - keywords like 'today', 'tomorrow', or weekday names
        - otherwise assumes 'today at 09:00'
        """

        now = datetime.now()

        # Explicit time in message (e.g. "2pm", "at 3", "14:00") – for date_only detection
        has_explicit_time = bool(
            re.search(r"\d{1,2}\s*(am|pm)\b|at\s+\d{1,2}\b|\d{1,2}:\d{2}", text, re.IGNORECASE)
        )

        # Time – require am/pm or :mm so "4th" in "July 4th" isn't parsed as time
        time_match = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.IGNORECASE
        )
        if not time_match:
            time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        if not time_match:
            time_match = re.search(r"\bat\s+(\d{1,2})\b", text, re.IGNORECASE)
        hour = 9
        minute = 0
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0) if time_match.lastindex >= 2 else 0
            ampm = (time_match.group(3) or "").lower() if time_match.lastindex >= 3 else ""
            if ampm == "pm" and hour < 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
            if not ampm and time_match.lastindex == 1:
                hour = hour + 12 if hour < 8 else hour  # "at 3" -> 3pm, "at 9" -> 9am

        # Date: tomorrow, today, weekdays, month+day (July 4th), or m/d (3/3)
        date = now.date()
        has_date_keyword = False

        if "tomorrow" in text:
            date = now.date() + timedelta(days=1)
            has_date_keyword = True
        elif "today" in text:
            has_date_keyword = True
        else:
            # Weekday names
            weekdays = [
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday",
            ]
            for i, name in enumerate(weekdays):
                if name in text:
                    today_idx = now.weekday()
                    target_idx = i
                    days_ahead = (target_idx - today_idx) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    date = now.date() + timedelta(days=days_ahead)
                    has_date_keyword = True
                    break

            if not has_date_keyword:
                # Month name + day: "July 4th", "july 4", "January 15", "on March 3"
                months = [
                    "january", "february", "march", "april", "may", "june",
                    "july", "august", "september", "october", "november", "december",
                ]
                month_day = re.search(
                    r"\b(january|february|march|april|may|june|july|august|"
                    r"september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\b",
                    text,
                    re.IGNORECASE,
                )
                if month_day:
                    month_name = month_day.group(1).lower()
                    day = int(month_day.group(2))
                    month = months.index(month_name) + 1
                    year = now.year
                    if month < now.month or (month == now.month and day < now.day):
                        year += 1
                    try:
                        date = datetime(year, month, day).date()
                        has_date_keyword = True
                    except ValueError:
                        pass

            if not has_date_keyword:
                # Numeric m/d/yyyy or mm/dd/yyyy: "12/31/2026", "3/3/2025"
                slash_date_full = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
                if slash_date_full:
                    first = int(slash_date_full.group(1))
                    second = int(slash_date_full.group(2))
                    year = int(slash_date_full.group(3))
                    if first <= 12 and second <= 31:
                        month, day = first, second
                    elif second <= 12 and first <= 31:
                        month, day = second, first
                    else:
                        month, day = first, second
                    if month <= 12 and 1 <= day <= 31:
                        try:
                            date = datetime(year, month, day).date()
                            has_date_keyword = True
                        except ValueError:
                            pass

                if not has_date_keyword:
                    # Numeric m/d or mm/dd (no year): "3/3", "12/25", "on 3/15"
                    slash_date = re.search(r"\b(\d{1,2})/(\d{1,2})\b", text)
                    if slash_date:
                        first = int(slash_date.group(1))
                        second = int(slash_date.group(2))
                        year = now.year
                        if first <= 12 and second <= 31:
                            month, day = first, second
                        elif second <= 12 and first <= 31:
                            month, day = second, first
                        else:
                            month, day = first, second
                        if month <= 12 and 1 <= day <= 31:
                            try:
                                date = datetime(year, month, day).date()
                                if date < now.date():
                                    date = datetime(year + 1, month, day).date()
                                has_date_keyword = True
                            except ValueError:
                                pass

        start_dt = datetime.combine(date, datetime.min.time()).replace(
            hour=hour, minute=minute
        )

        # Duration
        duration_minutes = 30
        duration_match = re.search(r"(\d+)\s*(minute|minutes|min|hour|hours)", text)
        if duration_match:
            value = int(duration_match.group(1))
            unit = duration_match.group(2)
            if "hour" in unit:
                duration_minutes = value * 60
            else:
                duration_minutes = value

        # Title heuristic
        title = "appointment"
        m = re.search(r"for ([a-zA-Z ]+)", text)
        if m:
            title = m.group(1).strip()
        elif "doctor" in text:
            title = "doctor visit"
        elif "dentist" in text:
            title = "dentist appointment"

        date_only = bool(has_date_keyword and not has_explicit_time)

        parsed = {
            "title": title,
            "start": start_dt,
            "end": start_dt + timedelta(minutes=duration_minutes),
            "location": None,
            "notes": text,
            "date_only": date_only,
            "duration_minutes": duration_minutes,
        }

        return parsed


class SchedulingAgent(Agent):
    """
    Agent that attempts to add the appointment to the calendar.
    """

    def __init__(self) -> None:
        super().__init__("SchedulingAgent")

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        parsed = context.state.get("parsed_appointment")
        if not parsed:
            return [
                Message(
                    sender=self.name,
                    content="I don't have an appointment to schedule yet.",
                    metadata={"type": "schedule_error"},
                )
            ]

        appointment = Appointment(
            title=parsed["title"],
            start=parsed["start"],
            end=parsed["end"],
            location=parsed["location"],
            notes=parsed["notes"],
        )

        ok, reason = check_business_hours(appointment)
        if not ok:
            return [
                Message(
                    sender=self.name,
                    content=reason + " We're open Monday–Friday, 8am–5pm (last start 4:30pm), and closed for lunch 1–2pm.",
                    metadata={"type": "schedule_business_hours"},
                )
            ]

        conflicts = context.calendar.find_conflicts(appointment)
        if conflicts:
            return [
                Message(
                    sender=self.name,
                    content="The requested time conflicts with an existing event.",
                    metadata={
                        "type": "schedule_conflict",
                        "candidate": appointment,
                        "conflicts": conflicts,
                    },
                )
            ]

        # Don't add yet; ask for confirmation
        return [
            Message(
                sender=self.name,
                content=(
                    f"I'll book \"{appointment.title}\" on {appointment.start.strftime('%A %d %B %Y')} "
                    f"from {appointment.start.strftime('%H:%M')} to {appointment.end.strftime('%H:%M')}. "
                    "Reply **yes** to confirm or **no** to cancel."
                ),
                metadata={"type": "schedule_confirm_pending", "appointment": appointment},
            )
        ]


class ConflictResolutionAgent(Agent):
    """
    Agent that proposes an alternative time when there is a conflict.
    Does not auto-book; the orchestrator will ask the user to confirm.
    """

    def __init__(self) -> None:
        super().__init__("ConflictResolutionAgent")

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        meta = message.metadata or {}
        candidate: Appointment = meta.get("candidate")
        if not candidate:
            return []

        suggestion = context.calendar.suggest_next_free_slot(candidate)
        if not suggestion:
            return [
                Message(
                    sender=self.name,
                    content=(
                        "I couldn't find a free slot later that day. "
                        "You may need to choose a different day."
                    ),
                    metadata={"type": "no_alternative"},
                )
            ]

        # Do NOT set parsed_appointment here; we ask the user first
        return [
            Message(
                sender=self.name,
                content=(
                    "I suggest moving it to "
                    f"{suggestion.start.strftime('%Y-%m-%d at %H:%M')}. "
                    "Does that time work for you? Reply **yes** to confirm or **no** to try another day."
                ),
                metadata={"type": "alternative_proposed", "appointment": suggestion},
            )
        ]


def _parse_requested_date_from_text(text: str) -> Optional[Tuple[date_type, str]]:
    """
    If the user text mentions a specific day/date, return (date, display_name) e.g. (date, "Thursday").
    Otherwise return None. Used to filter appointments by day and to say "no appointment on Thursday".
    """
    t = text.lower()
    now = datetime.now()
    if "today" in t:
        return (now.date(), "today")
    if "tomorrow" in t:
        return ((now + timedelta(days=1)).date(), "tomorrow")
    weekdays = [
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    ]
    for i, name in enumerate(weekdays):
        if name in t:
            today_idx = now.weekday()
            target_idx = i
            days_ahead = (target_idx - today_idx) % 7
            if days_ahead == 0:
                days_ahead = 7
            d = now.date() + timedelta(days=days_ahead)
            display = name.capitalize()
            return (d, display)
    return None


def _find_appointment_by_text(calendar: CalendarStore, text: str) -> Tuple[Optional[Appointment], Optional[str]]:
    """
    Find one appointment that best matches the user text (by day/date first, then title).
    Returns (appointment, no_appointment_on_day_message).
    - If user specified a day/date and there is no appointment on that day: (None, "You don't have any appointment on Thursday.").
    - If user specified a day and there is one or more on that day: (first such appointment, None).
    - If user did not specify a day: match by title (avoid matching only the word "appointment"); (None, None) if ambiguous or no match.
    """
    t = text.lower()
    now = datetime.now()
    requested = _parse_requested_date_from_text(text)

    if requested is not None:
        req_date, display_name = requested
        on_day = [a for a in calendar.appointments if a.start.date() == req_date]
        if not on_day:
            return (None, f"You don't have any appointment on {display_name}.")
        return (on_day[0], None)

    # No specific day: match by title. Don't treat the word "appointment" alone as matching everything.
    candidates = []
    title_words_skip = {"appointment", "meeting", "event"}  # too generic
    for a in calendar.appointments:
        if a.title.lower() in t:
            candidates.append(a)
            continue
        words = [w for w in a.title.lower().split() if w not in title_words_skip]
        if not words:
            continue
        if any(w in t for w in words):
            candidates.append(a)
            continue
        if "today" in t and a.start.date() == now.date():
            candidates.append(a)
        elif "tomorrow" in t and a.start.date() == (now.date() + timedelta(days=1)):
            candidates.append(a)
        else:
            for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
                if day in t and a.start.strftime("%A").lower() == day:
                    candidates.append(a)
                    break
    if not candidates:
        return (None, None)
    return (candidates[0], None)


def _parse_time_only(text: str) -> Optional[Tuple[int, int]]:
    """Parse a time from short reply like '2pm', '10:30 am', '14:00'. Returns (hour_24, minute) or None."""
    t = text.strip().lower()
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = (m.group(3) or "").strip()
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return (hour, minute)
    return None


def _parse_new_time_from_text(text: str, default_date: Optional[datetime] = None) -> Optional[datetime]:
    """Parse a time from phrases like 'to 4pm', 'at 2:30', 'for 10am'. Returns start datetime."""
    now = default_date or datetime.now()
    # Prefer "to X" or "at X" or "for X"
    for pattern in (r"\bto\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", r"\bfor\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"):
        m = re.search(pattern, text.lower())
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            ampm = (m.group(3) or "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
            date = now.date()
            if "tomorrow" in text.lower():
                date = (now.date() + timedelta(days=1))
            return datetime.combine(date, datetime.min.time()).replace(hour=hour, minute=minute)
    return None


class RescheduleAgent(Agent):
    """
    Agent that finds an existing appointment and prepares to reschedule it to a new time.
    Removes the old appointment and sets parsed_appointment for the SchedulingAgent.
    """

    def __init__(self) -> None:
        super().__init__("RescheduleAgent")

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        user_text = message.content
        calendar = context.calendar
        if not calendar.appointments:
            return [
                Message(
                    sender=self.name,
                    content="You don't have any appointments scheduled. Would you like to book one? (e.g. \"Book a meeting tomorrow at 2pm\")",
                    metadata={"type": "reschedule_error"},
                )
            ]
        existing, no_appointment_on_day_msg = _find_appointment_by_text(calendar, user_text)
        if no_appointment_on_day_msg:
            return [
                Message(
                    sender=self.name,
                    content=no_appointment_on_day_msg,
                    metadata={"type": "reschedule_not_found"},
                )
            ]
        if not existing:
            # User said reschedule but didn't specify which appointment (e.g. "can you reschedule it")
            lines = ["Which appointment would you like to reschedule? Your current appointments are:"]
            for a in calendar.appointments:
                lines.append(f"• {a.title} — {a.start.strftime('%A %d %B at %H:%M')}")
            lines.append("Please mention the title or day/date and the new time (e.g. \"reschedule my dentist on Tuesday to 4pm\" or \"move my meeting to 3pm\").")
            return [
                Message(
                    sender=self.name,
                    content="\n".join(lines),
                    metadata={"type": "reschedule_not_found"},
                )
            ]
        new_start = _parse_new_time_from_text(user_text)
        if not new_start:
            return [
                Message(
                    sender=self.name,
                    content="I couldn't understand the new time. Please say something like 'to 4pm' or 'at 2:30pm'.",
                    metadata={"type": "reschedule_bad_time"},
                )
            ]
        duration = existing.end - existing.start
        new_end = new_start + duration
        new_appointment = Appointment(
            title=existing.title,
            start=new_start,
            end=new_end,
            location=existing.location,
            notes=existing.notes or user_text,
        )
        # Don't remove old or add new yet; ask for confirmation
        return [
            Message(
                sender=self.name,
                content=(
                    f"I'll move \"{existing.title}\" from {existing.start.strftime('%A %d %B at %H:%M')} "
                    f"to {new_start.strftime('%A %d %B at %H:%M')}. "
                    "Reply **yes** to confirm or **no** to keep the original time."
                ),
                metadata={
                    "type": "reschedule_confirm_pending",
                    "old_appointment": existing,
                    "new_appointment": new_appointment,
                },
            )
        ]


class CancelAgent(Agent):
    """
    Agent that finds an existing appointment and asks for confirmation before removing it.
    """

    def __init__(self) -> None:
        super().__init__("CancelAgent")

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        user_text = message.content
        calendar = context.calendar
        if not calendar.appointments:
            return [
                Message(
                    sender=self.name,
                    content="You don't have any appointments to cancel or delete. Would you like to book one? (e.g. \"Book a meeting tomorrow at 2pm\")",
                    metadata={"type": "cancel_error"},
                )
            ]
        existing, no_appointment_on_day_msg = _find_appointment_by_text(calendar, user_text)
        if no_appointment_on_day_msg:
            return [
                Message(
                    sender=self.name,
                    content=no_appointment_on_day_msg,
                    metadata={"type": "cancel_not_found"},
                )
            ]
        if not existing:
            # User said cancel/delete but didn't specify which (e.g. "can you delete it", "can you cancel please")
            lines = ["Which appointment would you like to cancel or delete? Your current appointments are:"]
            for a in calendar.appointments:
                lines.append(f"• {a.title} — {a.start.strftime('%A %d %B at %H:%M')}")
            lines.append("Please mention the title or the day/date (e.g. \"cancel my dentist on Thursday\" or \"delete my meeting on Tuesday\").")
            return [
                Message(
                    sender=self.name,
                    content="\n".join(lines),
                    metadata={"type": "cancel_not_found"},
                )
            ]
        # Don't remove yet; ask for confirmation
        return [
            Message(
                sender=self.name,
                content=(
                    f"I'll cancel \"{existing.title}\" on {existing.start.strftime('%A %d %B at %H:%M')}. "
                    "Reply **yes** to confirm or **no** to keep it."
                ),
                metadata={"type": "cancel_confirm_pending", "appointment": existing},
            )
        ]


class NotificationAgent(Agent):
    """
    Agent that turns the scheduling result into a user-friendly summary.
    """

    def __init__(self) -> None:
        super().__init__("NotificationAgent")

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        appointment: Appointment | None = context.state.get("final_appointment")
        if not appointment:
            return [
                Message(
                    sender=self.name,
                    content="No appointment was scheduled.",
                    metadata={"type": "notify_none"},
                )
            ]

        friendly = (
            f"Your appointment \"{appointment.title}\" is booked on "
            f"{appointment.start.strftime('%A %d %B %Y')} "
            f"from {appointment.start.strftime('%H:%M')} "
            f"to {appointment.end.strftime('%H:%M')}."
        )

        return [
            Message(
                sender=self.name,
                content=friendly,
                metadata={"type": "notify_success"},
            )
        ]


# Type for pending confirmation: booking (add), cancel (remove), reschedule (remove old + add new)
PendingConfirm = Optional[Dict[str, Any]]  # {"type": "booking"|"cancel"|"reschedule", "appointment" and/or "old_appointment"/"new_appointment"}


class Orchestrator:
    """
    High-level controller that routes messages through the agents.
    Returns (transcript, pending_alternative, pending_slot_request, pending_confirm).
    When pending_confirm is set, the caller should ask the user yes/no and call again with that response.
    """

    def __init__(self, calendar: CalendarStore) -> None:
        self.calendar = calendar
        self.nlu = NLUAgent()
        self.scheduler = SchedulingAgent()
        self.conflict = ConflictResolutionAgent()
        self.notifier = NotificationAgent()
        self.reschedule = RescheduleAgent()
        self.cancel = CancelAgent()

    def handle_user_request(
        self,
        user_text: str,
        pending_alternative: Optional[Appointment] = None,
        pending_slot_request: Optional[Dict[str, Any]] = None,
        pending_confirm: PendingConfirm = None,
        last_booking_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Message], Optional[Appointment], Optional[Dict[str, Any]], PendingConfirm]:
        context = ConversationContext(self.calendar)
        context.state["last_booking_context"] = last_booking_context
        transcript: List[Message] = []
        user_msg = Message(sender="User", content=user_text)
        transcript.append(user_msg)
        pending_out: Optional[Appointment] = None
        pending_slot_out: Optional[Dict[str, Any]] = None
        pending_confirm_out: PendingConfirm = None

        # Handle confirmation of a pending action (booking, cancel, reschedule)
        if pending_confirm:
            intent = _detect_intent(user_text)
            if intent == "confirm_yes":
                ptype = pending_confirm.get("type")
                if ptype == "booking":
                    appt = pending_confirm.get("appointment")
                    if appt:
                        context.calendar.add(appt)
                        context.state["final_appointment"] = appt
                        transcript.append(
                            Message(
                                sender="SchedulingAgent",
                                content="I've booked that time.",
                                metadata={"type": "schedule_success", "appointment": appt},
                            )
                        )
                        notify_msgs = self.notifier.handle(transcript[-1], context)
                        transcript.extend(notify_msgs)
                elif ptype == "cancel":
                    appt = pending_confirm.get("appointment")
                    if appt:
                        context.calendar.remove(appt)
                        transcript.append(
                            Message(
                                sender="CancelAgent",
                                content=f"I've cancelled \"{appt.title}\" that was on {appt.start.strftime('%A %d %B at %H:%M')}.",
                                metadata={"type": "cancel_done"},
                            )
                        )
                elif ptype == "reschedule":
                    old_a = pending_confirm.get("old_appointment")
                    new_a = pending_confirm.get("new_appointment")
                    if old_a and new_a:
                        context.calendar.remove(old_a)
                        context.calendar.add(new_a)
                        context.state["final_appointment"] = new_a
                        transcript.append(
                            Message(
                                sender="SchedulingAgent",
                                content=f"I've moved it to {new_a.start.strftime('%A %d %B at %H:%M')}.",
                                metadata={"type": "schedule_success", "appointment": new_a},
                            )
                        )
                        notify_msgs = self.notifier.handle(transcript[-1], context)
                        transcript.extend(notify_msgs)
                return transcript, None, None, None
            if intent == "confirm_no":
                if pending_confirm.get("type") == "booking":
                    transcript.append(
                        Message(sender="Assistant", content="No problem, I didn't book that.", metadata={"type": "confirm_declined"})
                    )
                elif pending_confirm.get("type") == "cancel":
                    transcript.append(
                        Message(sender="Assistant", content="No problem, I kept that appointment.", metadata={"type": "confirm_declined"})
                    )
                elif pending_confirm.get("type") == "reschedule":
                    transcript.append(
                        Message(sender="Assistant", content="No problem, I kept the original time.", metadata={"type": "confirm_declined"})
                    )
                return transcript, None, None, None
            # User said something else; clear pending and fall through
            pending_confirm = None

        # Handle time choice after we showed available slots (date-only booking)
        if pending_slot_request:
            time_parsed = _parse_time_only(user_text)
            if time_parsed is not None:
                hour, minute = time_parsed
                d = pending_slot_request["date"]
                if isinstance(d, datetime):
                    d = d.date()
                start_dt = datetime.combine(d, time(hour, minute))
                dur = timedelta(minutes=pending_slot_request["duration_minutes"])
                end_dt = start_dt + dur
                appointment = Appointment(
                    title=pending_slot_request["title"],
                    start=start_dt,
                    end=end_dt,
                    location=None,
                    notes=user_text,
                )
                ok, reason = check_business_hours(appointment)
                if not ok:
                    transcript.append(
                        Message(
                            sender="Assistant",
                            content=reason + " Please pick one of the listed times.",
                            metadata={"type": "slot_invalid"},
                        )
                    )
                    return transcript, None, pending_slot_request, None
                if context.calendar.find_conflicts(appointment):
                    transcript.append(
                        Message(
                            sender="Assistant",
                            content="That time is no longer available. Please choose another from the list.",
                            metadata={"type": "slot_conflict"},
                        )
                    )
                    return transcript, None, pending_slot_request, None
                # Ask for confirmation before booking
                transcript.append(
                    Message(
                        sender="SchedulingAgent",
                        content=(
                            f"I'll book \"{appointment.title}\" on {appointment.start.strftime('%A %d %B %Y')} "
                            f"from {appointment.start.strftime('%H:%M')} to {appointment.end.strftime('%H:%M')}. "
                            "Reply **yes** to confirm or **no** to cancel."
                        ),
                        metadata={"type": "schedule_confirm_pending", "appointment": appointment},
                    )
                )
                pending_confirm_out = {"type": "booking", "appointment": appointment}
                return transcript, None, None, pending_confirm_out
            # Not a time – clear and fall through (user might have said something else)
            pending_slot_request = None

        # Handle confirmation of a previously suggested (conflict) slot
        if pending_alternative:
            intent = _detect_intent(user_text)
            if intent == "confirm_yes":
                context.calendar.add(pending_alternative)
                context.state["final_appointment"] = pending_alternative
                confirm_msg = Message(
                    sender="SchedulingAgent",
                    content="I've booked the suggested time.",
                    metadata={"type": "schedule_success", "appointment": pending_alternative},
                )
                transcript.append(confirm_msg)
                notify_msgs = self.notifier.handle(confirm_msg, context)
                transcript.extend(notify_msgs)
                return transcript, None, None, None
            if intent == "confirm_no":
                transcript.append(
                    Message(
                        sender="ConflictResolutionAgent",
                        content="No problem. Suggest another date or time when you're ready.",
                        metadata={"type": "confirm_declined"},
                    )
                )
                return transcript, None, None, None

        intent = _detect_intent(user_text)

        # Greeting: respond conversationally, do not book
        if intent == "greeting":
            if _is_how_are_you(user_text):
                content = (
                    "I'm doing well, thank you for asking! How are you? "
                    "How can I help you today—would you like to book, reschedule, or cancel an appointment?"
                )
            else:
                content = (
                    "Hello! I'm your appointment assistant. You can ask me to book, reschedule, or cancel appointments. "
                    "Your calendar is in the sidebar—how can I help?"
                )
            transcript.append(
                Message(sender="Assistant", content=content, metadata={"type": "greeting"})
            )
            return transcript, None, None, None

        # List / what do I have: reply with calendar summary, do not book
        if intent == "list":
            appts = self.calendar.appointments
            if not appts:
                content = "You don't have any appointments yet. Say something like \"Book a meeting tomorrow at 2pm\" to add one."
            else:
                lines = [f"You have {len(appts)} appointment(s):"]
                for a in appts:
                    lines.append(f"• {a.title} — {a.start.strftime('%A %d %B at %H:%M')} to {a.end.strftime('%H:%M')}")
                content = "\n".join(lines)
            transcript.append(
                Message(sender="Assistant", content=content, metadata={"type": "list"})
            )
            return transcript, None, None, None

        # Out of scope: nice reply that we only help with appointments
        if intent == "out_of_scope":
            transcript.append(
                Message(
                    sender="Assistant",
                    content=(
                        "I’m here only to help with appointments—booking, rescheduling, or cancelling. "
                        "I can’t answer questions about weather, news, or other topics. "
                        "Try something like: \"Book a meeting tomorrow at 2pm\" or \"What do I have scheduled?\" "
                        "How can I help with your calendar?"
                    ),
                    metadata={"type": "out_of_scope"},
                )
            )
            return transcript, None, None, None

        # Cancel flow
        if intent == "cancel":
            cancel_msgs = self.cancel.handle(user_msg, context)
            transcript.extend(cancel_msgs)
            last_meta = (cancel_msgs[-1].metadata or {}) if cancel_msgs else {}
            if last_meta.get("type") == "cancel_confirm_pending":
                pending_confirm_out = {"type": "cancel", "appointment": last_meta.get("appointment")}
            return transcript, None, None, pending_confirm_out

        # Reschedule flow: RescheduleAgent -> [confirm] or -> SchedulingAgent if we had reschedule_ready
        if intent == "reschedule":
            resched_msgs = self.reschedule.handle(user_msg, context)
            transcript.extend(resched_msgs)
            last_meta = (resched_msgs[-1].metadata or {}) if resched_msgs else {}
            if last_meta.get("type") == "reschedule_confirm_pending":
                pending_confirm_out = {
                    "type": "reschedule",
                    "old_appointment": last_meta.get("old_appointment"),
                    "new_appointment": last_meta.get("new_appointment"),
                }
                return transcript, None, None, pending_confirm_out
            return transcript, None, None, None

        # Create-appointment flow
        nlu_msgs = self.nlu.handle(user_msg, context)
        transcript.extend(nlu_msgs)
        if nlu_msgs and (nlu_msgs[-1].metadata or {}).get("type") == "nlu_error":
            return transcript, None, None, None

        parsed = context.state.get("parsed_appointment")
        if parsed and parsed.get("date_only"):
            # Show available slots and ask for time
            slots = self.calendar.get_available_slots(
                parsed["start"].date(),
                parsed.get("duration_minutes", 30),
            )
            if not slots:
                transcript.append(
                    Message(
                        sender="Assistant",
                        content=(
                            f"Sorry, there are no available slots on {parsed['start'].strftime('%A %d %B')} "
                            "(weekends and holidays are closed). Try another day."
                        ),
                        metadata={"type": "no_slots"},
                    )
                )
                return transcript, None, None, None
            slot_times = [s[0].strftime("%H:%M") for s in slots]
            slot_str = ", ".join(slot_times)
            transcript.append(
                Message(
                    sender="Assistant",
                    content=(
                        f"On {parsed['start'].strftime('%A %d %B')} the available times are: {slot_str}. "
                        "Which time would you like? (e.g. 2pm or 14:00)"
                    ),
                    metadata={"type": "slots_offered"},
                )
            )
            pending_slot_out = {
                "title": parsed["title"],
                "date": parsed["start"].date(),
                "duration_minutes": parsed.get("duration_minutes", 30),
            }
            return transcript, None, pending_slot_out, None

        sched_msgs = self.scheduler.handle(nlu_msgs[-1], context)
        transcript.extend(sched_msgs)
        last_meta = (sched_msgs[-1].metadata or {}) if sched_msgs else {}

        if last_meta.get("type") == "schedule_confirm_pending":
            pending_confirm_out = {"type": "booking", "appointment": last_meta.get("appointment")}
            return transcript, None, None, pending_confirm_out
        if last_meta.get("type") == "schedule_conflict":
            conflict_msgs = self.conflict.handle(sched_msgs[-1], context)
            transcript.extend(conflict_msgs)
            if conflict_msgs and (conflict_msgs[-1].metadata or {}).get("type") == "alternative_proposed":
                pending_out = conflict_msgs[-1].metadata.get("appointment")
        else:
            notify_msgs = self.notifier.handle(transcript[-1], context)
            transcript.extend(notify_msgs)

        return transcript, pending_out, None, None

