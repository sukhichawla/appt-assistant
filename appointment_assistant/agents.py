from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
import re
from typing import Any, Dict, List, Optional, Tuple

from appointment_assistant.calendar_store import Appointment, CalendarStore, check_business_hours


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
    if t in ("no", "nope", "cancel it", "no thanks"):
        return "confirm_no"
    if _is_out_of_scope(text):
        return "out_of_scope"
    if any(w in t for w in ("cancel", "remove", "delete")) and (
        "appointment" in t or "meeting" in t or "event" in t
    ):
        return "cancel"
    if any(w in t for w in ("reschedule", "move", "rebook", "change")) and (
        "appointment" in t or "meeting" in t or " to " in t or " at " in t
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


class NLUAgent(Agent):
    """
    Light‑weight natural language understanding agent.

    For the capstone you can swap the rule-based parser with an LLM call.
    """

    def __init__(self) -> None:
        super().__init__("NLUAgent")

    def handle(self, message: Message, context: ConversationContext) -> List[Message]:
        user_text = message.content.lower()
        parsed = self._simple_parse(user_text)

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

        context.calendar.add(appointment)
        context.state["final_appointment"] = appointment

        return [
            Message(
                sender=self.name,
                content="I successfully reserved that time on your calendar.",
                metadata={"type": "schedule_success", "appointment": appointment},
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


def _find_appointment_by_text(calendar: CalendarStore, text: str) -> Optional[Appointment]:
    """Find one appointment that best matches the user text (title or date/time)."""
    t = text.lower()
    now = datetime.now()
    candidates = []
    for a in calendar.appointments:
        if a.title.lower() in t or any(w in t for w in a.title.lower().split()):
            candidates.append(a)
        elif "today" in t and a.start.date() == now.date():
            candidates.append(a)
        elif "tomorrow" in t and a.start.date() == (now.date() + timedelta(days=1)):
            candidates.append(a)
        else:
            for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
                if day in t and a.start.strftime("%A").lower() == day:
                    candidates.append(a)
                    break
    if not candidates:
        return None
    return candidates[0]


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
                    content="You don't have any appointments yet, so there's nothing to reschedule. Would you like to book one?",
                    metadata={"type": "reschedule_error"},
                )
            ]
        existing = _find_appointment_by_text(calendar, user_text)
        if not existing:
            lines = ["I couldn't find that appointment. Your current appointments are:"]
            for a in calendar.appointments:
                lines.append(f"• {a.title} — {a.start.strftime('%A %d %B at %H:%M')}")
            lines.append("Please mention the exact title or date of the one you want to move.")
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
        calendar.remove(existing)
        new_appointment = Appointment(
            title=existing.title,
            start=new_start,
            end=new_end,
            location=existing.location,
            notes=existing.notes or user_text,
        )
        context.state["parsed_appointment"] = {
            "title": new_appointment.title,
            "start": new_appointment.start,
            "end": new_appointment.end,
            "location": new_appointment.location,
            "notes": new_appointment.notes,
        }
        return [
            Message(
                sender=self.name,
                content=f"I've removed the old slot. Checking if {new_start.strftime('%Y-%m-%d %H:%M')} is free and booking it.",
                metadata={"type": "reschedule_ready", "appointment": new_appointment},
            )
        ]


class CancelAgent(Agent):
    """
    Agent that finds an existing appointment and removes it from the calendar.
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
                    content="You don't have any appointments to cancel. Would you like to book one?",
                    metadata={"type": "cancel_error"},
                )
            ]
        existing = _find_appointment_by_text(calendar, user_text)
        if not existing:
            lines = ["I couldn't find that appointment. Your current appointments are:"]
            for a in calendar.appointments:
                lines.append(f"• {a.title} — {a.start.strftime('%A %d %B at %H:%M')}")
            lines.append("Please mention the exact title or date of the one you want to cancel.")
            return [
                Message(
                    sender=self.name,
                    content="\n".join(lines),
                    metadata={"type": "cancel_not_found"},
                )
            ]
        calendar.remove(existing)
        return [
            Message(
                sender=self.name,
                content=f"I've cancelled \"{existing.title}\" that was on {existing.start.strftime('%A %d %B at %H:%M')}.",
                metadata={"type": "cancel_done"},
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


class Orchestrator:
    """
    High-level controller that routes messages through the agents.
    Returns (transcript, pending_alternative). When pending_alternative is set,
    the caller should ask the user to confirm (yes/no) and call again with that response.
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
    ) -> Tuple[List[Message], Optional[Appointment], Optional[Dict[str, Any]]]:
        context = ConversationContext(self.calendar)
        transcript: List[Message] = []
        user_msg = Message(sender="User", content=user_text)
        transcript.append(user_msg)
        pending_out: Optional[Appointment] = None
        pending_slot_out: Optional[Dict[str, Any]] = None

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
                    return transcript, None, pending_slot_request
                if context.calendar.find_conflicts(appointment):
                    transcript.append(
                        Message(
                            sender="Assistant",
                            content="That time is no longer available. Please choose another from the list.",
                            metadata={"type": "slot_conflict"},
                        )
                    )
                    return transcript, None, pending_slot_request
                context.calendar.add(appointment)
                context.state["final_appointment"] = appointment
                transcript.append(
                    Message(
                        sender="SchedulingAgent",
                        content="Booked.",
                        metadata={"type": "schedule_success", "appointment": appointment},
                    )
                )
                notify_msgs = self.notifier.handle(transcript[-1], context)
                transcript.extend(notify_msgs)
                return transcript, None, None
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
                return transcript, None, None
            if intent == "confirm_no":
                transcript.append(
                    Message(
                        sender="ConflictResolutionAgent",
                        content="No problem. Suggest another date or time when you're ready.",
                        metadata={"type": "confirm_declined"},
                    )
                )
                return transcript, None, None

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
            return transcript, None, None

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
            return transcript, None, None

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
            return transcript, None, None

        # Cancel flow
        if intent == "cancel":
            cancel_msgs = self.cancel.handle(user_msg, context)
            transcript.extend(cancel_msgs)
            return transcript, None, None

        # Reschedule flow: RescheduleAgent -> SchedulingAgent -> [Conflict?] -> NotificationAgent
        if intent == "reschedule":
            resched_msgs = self.reschedule.handle(user_msg, context)
            transcript.extend(resched_msgs)
            if not resched_msgs or (resched_msgs[-1].metadata or {}).get("type") not in (
                "reschedule_ready",
                "reschedule_done",
            ):
                return transcript, None, None
            sched_msgs = self.scheduler.handle(resched_msgs[-1], context)
            transcript.extend(sched_msgs)
            last_meta = (sched_msgs[-1].metadata or {}) if sched_msgs else {}
            if last_meta.get("type") == "schedule_conflict":
                conflict_msgs = self.conflict.handle(sched_msgs[-1], context)
                transcript.extend(conflict_msgs)
                if conflict_msgs and (conflict_msgs[-1].metadata or {}).get("type") == "alternative_proposed":
                    pending_out = conflict_msgs[-1].metadata.get("appointment")
            else:
                notify_msgs = self.notifier.handle(transcript[-1], context)
                transcript.extend(notify_msgs)
            return transcript, pending_out, None

        # Create-appointment flow
        nlu_msgs = self.nlu.handle(user_msg, context)
        transcript.extend(nlu_msgs)
        if nlu_msgs and (nlu_msgs[-1].metadata or {}).get("type") == "nlu_error":
            return transcript, None, None

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
                return transcript, None, None
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
            return transcript, None, pending_slot_out

        sched_msgs = self.scheduler.handle(nlu_msgs[-1], context)
        transcript.extend(sched_msgs)
        last_meta = (sched_msgs[-1].metadata or {}) if sched_msgs else {}

        if last_meta.get("type") == "schedule_conflict":
            conflict_msgs = self.conflict.handle(sched_msgs[-1], context)
            transcript.extend(conflict_msgs)
            if conflict_msgs and (conflict_msgs[-1].metadata or {}).get("type") == "alternative_proposed":
                pending_out = conflict_msgs[-1].metadata.get("appointment")
            # Do not auto-book; return and ask user to confirm
        else:
            notify_msgs = self.notifier.handle(transcript[-1], context)
            transcript.extend(notify_msgs)

        return transcript, pending_out, None

