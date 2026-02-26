from __future__ import annotations

from datetime import datetime

from appointment_assistant.agents import Orchestrator
from appointment_assistant.calendar_store import CalendarStore


def print_transcript(messages) -> None:
    for msg in messages:
        if msg.sender.lower() == "user":
            print(f"\nYou: {msg.content}")
        else:
            print(f"{msg.sender}: {msg.content}")


def print_appointments(calendar: CalendarStore) -> None:
    if not calendar.appointments:
        print("\nNo appointments in the calendar yet.")
        return

    print("\nYour current appointments:")
    for appt in calendar.appointments:
        print(
            f"- {appt.title} | "
            f"{appt.start.strftime('%Y-%m-%d %H:%M')} "
            f"to {appt.end.strftime('%H:%M')}"
        )


def main() -> None:
    print("=== Multi-Agent AI Appointment Assistant ===")
    print("You can: create, reschedule, or cancel appointments in natural language.")
    print('  Create:   "Book a dentist appointment for tomorrow at 3pm for 1 hour"')
    print('  Reschedule: "Reschedule my dentist appointment to 4pm"')
    print('  Cancel:   "Cancel my dentist appointment tomorrow"\n')

    calendar = CalendarStore()
    orchestrator = Orchestrator(calendar)
    pending_alternative = None
    pending_slot_request = None

    while True:
        print("\nMenu:")
        print("1) Create / reschedule / cancel (natural language)")
        print("2) List appointments")
        print("3) Exit")
        choice = input("Enter choice (1-3): ").strip()

        if choice == "1":
            if pending_alternative:
                print(f"\nSuggested slot: {pending_alternative.start.strftime('%Y-%m-%d %H:%M')}. Reply 'yes' to confirm or 'no' to decline.")
            if pending_slot_request:
                print("\nPick a time from the list above (e.g. 2pm or 14:00):")
            user_text = input("\nYour message: ").strip()
            if not user_text:
                print("Please enter something.")
                continue

            transcript, pending_alternative, pending_slot_request = orchestrator.handle_user_request(
                user_text, pending_alternative, pending_slot_request
            )
            print_transcript(transcript)

        elif choice == "2":
            print_appointments(calendar)

        elif choice == "3":
            print("\nGoodbye!")
            break
        else:
            print("Invalid choice, please enter 1, 2, or 3.")


if __name__ == "__main__":
    main()

