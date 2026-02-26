from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import List, Tuple

# Business rules: work 8am–5pm, last appointment starts 4:30pm, lunch 1pm–2pm, weekdays only, no holidays
WORK_START = time(8, 0)   # 8am
WORK_END = time(17, 0)     # 5pm
LAST_START = time(16, 30)  # 4:30pm
LUNCH_START = time(13, 0)  # 1pm
LUNCH_END = time(14, 0)    # 2pm

# Holidays: (month, day) — we check date only (annual)
HOLIDAYS: List[Tuple[int, int]] = [
    (1, 1),   # New Year's Day
    (7, 4),   # Independence Day
    (12, 25), # Christmas
    (11, 28), # Thanksgiving (4th Thu — approximate; exact varies)
    (11, 27), # day after / around Thanksgiving
    (9, 2),   # Labor Day (1st Mon — approximate)
    (5, 27),  # Memorial Day (last Mon — approximate)
]


def _is_weekday(d: datetime) -> bool:
    return d.weekday() < 5  # Monday=0 .. Friday=4


def _is_holiday(d: datetime) -> bool:
    for (mo, day) in HOLIDAYS:
        if d.month == mo and d.day == day:
            return True
    return False


def check_business_hours(appointment: "Appointment") -> Tuple[bool, str]:
    """
    Returns (True, "") if the appointment is within business hours and allowed;
    (False, "reason") otherwise.
    Rules: weekdays only, no holidays, 8am–5pm, no lunch 1–2pm, last start 4:30pm.
    """
    start = appointment.start
    end = appointment.end

    if not _is_weekday(start):
        return False, "We only schedule on weekdays (Monday–Friday), not on weekends."

    if _is_holiday(start):
        return False, "We're closed on holidays. Please choose a different day."

    start_t = start.time()
    end_t = end.time()

    if start_t < WORK_START:
        return False, "We open at 8:00 AM. Please choose a time from 8am onward."

    if end_t > WORK_END:
        return False, "We close at 5:00 PM. Your appointment must end by 5pm."

    if start_t > LAST_START:
        return False, "The latest appointment start is 4:30 PM. Please choose an earlier time."

    # No overlap with lunch 1pm–2pm
    if start_t < LUNCH_END and end_t > LUNCH_START:
        return False, "We're closed for lunch between 1:00 PM and 2:00 PM. Please pick a time outside that hour."

    return True, ""


@dataclass
class Appointment:
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    notes: str | None = None

    def overlaps(self, other: "Appointment") -> bool:
        return max(self.start, other.start) < min(self.end, other.end)


class CalendarStore:
    """
    In-memory calendar store used by the agents.

    For a real product you could replace this with a database
    or integrate with Google Calendar / Outlook.
    """

    def __init__(self) -> None:
        self._appointments: List[Appointment] = []

    @property
    def appointments(self) -> List[Appointment]:
        return list(self._appointments)

    def add(self, appointment: Appointment) -> None:
        self._appointments.append(appointment)
        self._appointments.sort(key=lambda a: a.start)

    def remove(self, appointment: Appointment) -> bool:
        """
        Remove an appointment that matches by title and start time.
        Returns True if one was removed, False otherwise.
        """
        for i, a in enumerate(self._appointments):
            if a.title == appointment.title and a.start == appointment.start:
                self._appointments.pop(i)
                return True
        return False

    def find_conflicts(self, candidate: Appointment) -> List[Appointment]:
        return [a for a in self._appointments if a.overlaps(candidate)]

    def get_available_slots(
        self, for_date: "datetime", duration_minutes: int = 30
    ) -> List[Tuple[datetime, datetime]]:
        """
        Return list of (start, end) slots on for_date within business hours,
        excluding lunch and existing appointments. for_date can be date or datetime.
        """
        d = for_date.date() if isinstance(for_date, datetime) else for_date
        dt = datetime.combine(d, time(0, 0))
        if not _is_weekday(dt) or _is_holiday(dt):
            return []
        duration = timedelta(minutes=duration_minutes)
        slot_starts = []
        for hour in (8, 9, 10, 11, 12, 14, 15, 16):
            for minute in (0, 30):
                t = time(hour, minute)
                if t > LAST_START:
                    continue
                if LUNCH_START <= t < LUNCH_END:
                    continue
                slot_starts.append(datetime.combine(d, t))
        out = []
        for start in slot_starts:
            end = start + duration
            if end.time() > WORK_END:
                continue
            trial = Appointment(title="", start=start, end=end)
            if check_business_hours(trial)[0] and not self.find_conflicts(trial):
                out.append((start, end))
        return out

    def suggest_next_free_slot(
        self, candidate: Appointment, search_horizon_days: int = 5
    ) -> Appointment | None:
        """
        Find the next free slot within business hours (weekdays 8am–5pm,
        no lunch 1–2pm, last start 4:30pm, no holidays).
        """
        duration = candidate.end - candidate.start
        # Valid 30-min slot start times: 8:00–12:30 and 14:00–16:30
        slot_starts = []
        for hour in (8, 9, 10, 11, 12, 14, 15, 16):
            for minute in (0, 30):
                t = time(hour, minute)
                if t > LAST_START:
                    continue
                if LUNCH_START <= t < LUNCH_END:
                    continue
                slot_starts.append(t)

        start_date = candidate.start.date()
        for day in range(search_horizon_days + 1):
            d = start_date + timedelta(days=day)
            if not _is_weekday(datetime.combine(d, time(0, 0))) or _is_holiday(datetime.combine(d, time(0, 0))):
                continue
            for start_t in slot_starts:
                trial_start = datetime.combine(d, start_t)
                trial_end = trial_start + duration
                if trial_end.time() > WORK_END:
                    continue
                if d == start_date and trial_start <= candidate.start:
                    continue
                trial = Appointment(
                    title=candidate.title,
                    start=trial_start,
                    end=trial_end,
                    location=candidate.location,
                    notes=candidate.notes,
                )
                ok, _ = check_business_hours(trial)
                if ok and not self.find_conflicts(trial):
                    return trial
        return None

