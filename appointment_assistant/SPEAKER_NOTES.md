## Speaker Notes – Multi-Agent AI Appointment Assistant

These notes are written so you can almost read them verbatim during your capstone presentation.  
Adjust the wording to match your speaking style.

---

### Slide 1 – Title & Introduction

**Slide title:** Multi-Agent AI Appointment Assistant  

**What you say:**

- “Hello everyone, my name is **[Your Name]**, and today I’m presenting my capstone project: a **Multi-Agent AI Appointment Assistant**.”
- “The main idea is to show how **multiple specialized AI agents** can collaborate to understand a user’s natural language request and schedule appointments automatically.”
- “I’ll walk you through the **problem**, the **multi-agent architecture**, and then do a **live demo** of the system in action.”

---

### Slide 2 – Problem Statement

**Slide title:** The Problem: Managing Appointments

**What you say:**

- “We all have to manage appointments: meetings, doctor visits, online calls, and so on.”
- “Most tools are still very **manual**. We switch between chat apps, emails, and calendar tools to decide a time.”
- “The question I asked was: *Can a group of AI agents handle this entire process for a user, starting from a simple natural-language request?*”
- “So the problem I’m addressing is: **How can we automate appointment scheduling in a more intelligent and conversational way?**”

---

### Slide 3 – High-Level Solution

**Slide title:** High-Level Solution

**What you say:**

- “My solution is a **multi-agent AI system** that works like a small team.”
- “When the user types something like ‘Book a dentist appointment for tomorrow at 3pm for 1 hour’, the system doesn’t just run one big function.”
- “Instead, it passes the request through a **pipeline of agents**, where each agent has a **clear responsibility**.”
- “This makes the system **modular**, easier to extend, and more similar to how real-world AI orchestration platforms are designed.”

---

### Slide 4 – Architecture Overview

**Slide title:** Architecture Overview

**What you say:**

- “Here is the overall architecture.”
- “The key components are:
  1. A simple **CLI interface** where the user types natural-language requests.
  2. An **Orchestrator** that coordinates the agents.
  3. A set of specialized **agents**:
     - NLU Agent
     - Scheduling Agent
     - Conflict Resolution Agent
     - Notification Agent
  4. An in-memory **Calendar Store** that holds all appointments.”
- “For each user request, the orchestrator creates a fresh **conversation context** and routes messages between these agents.”

---

### Slide 5 – Agents and Responsibilities

**Slide title:** The Agents

**What you say:**

- “Let me briefly explain what each agent does.”
- “**NLU Agent** – This is the *Natural Language Understanding* agent. It reads the raw text from the user and converts it into structured information: date, time, duration, and a title for the appointment.”
- “**Scheduling Agent** – Takes that structured information and tries to add an appointment to the calendar. It checks for conflicts and either books it or reports a conflict.”
- “**Conflict Resolution Agent** – When there is a conflict, this agent tries to find the **next available free slot** on the same day by scanning the calendar in 30-minute increments.”
- “**Notification Agent** – This agent converts the result into a friendly, human-readable confirmation message that the user can understand easily.”
- “By splitting responsibilities like this, each agent can be improved or replaced without rewriting the whole system.”

---

### Slide 6 – Data Flow & Message Passing

**Slide title:** Data Flow & Message Passing

**What you say:**

- “The agents communicate using a very simple **message-passing** mechanism.”
- “Each message has:
  - a **sender** name,
  - a **content** string, and
  - optional **metadata**.”
- “There’s also a shared **Conversation Context** object. It stores:
  - the parsed appointment details,
  - the final confirmed appointment,
  - and access to the shared `CalendarStore`.”
- “On each step, agents read the latest message and the context, then produce new messages that are appended to a **transcript**. This transcript becomes very useful for debugging and also for demonstration.”

---

### Slide 7 – Technology Stack & Implementation

**Slide title:** Technology Stack

**What you say:**

- “The implementation is deliberately **simple and transparent**.”
- “It uses:
  - **Python 3** as the main language.
  - A few small standard-library modules for dates, times, and regular expressions.
  - A very light dependency list, making it easy to install and run.”
- “The system currently uses a **rule-based NLU** to reduce external dependencies, but the architecture is designed so that this could be swapped out for a **real LLM** like GPT with minimal changes.”
- “The calendar is implemented as an **in-memory store**, which is perfect for demos and unit testing, but can later be replaced with a database or an external calendar API.”

---

### Slide 8 – Live Demo (Script)

**Slide title:** Live Demo

**What you do/say:**

- “Now I’ll quickly show the system in action.”
- “I start the assistant from the command line using:
  `python -m appointment_assistant.main`.”
- “The menu appears with three options: create appointment, list appointments, and exit.”

**Demo part 1 – Happy path**

- “First, I’ll create a simple appointment.”
- Type:  
  `Book a dentist appointment for tomorrow at 3pm for 1 hour`
- Say:
  - “This request is passed to the NLU Agent, which extracts the date, time, duration, and title.”
  - “The Scheduling Agent finds that the time is free and books it.”
  - “Finally, the Notification Agent confirms the appointment in a natural sentence.”
- “We can then list all appointments to verify it was saved.”

**Demo part 2 – Conflict + resolution**

- “Next, I’ll demonstrate a conflict.”
- First book an appointment:
  - `Schedule a meeting today at 10am for 1 hour`
- Then try another:
  - `Schedule a catch up for today at 10:30am for 30 minutes`
- Say:
  - “The Scheduling Agent detects a time overlap with the 10am meeting.”
  - “The Conflict Resolution Agent searches forward in the day for the next free 30-minute slot.”
  - “It proposes a new time, which is then passed back to the Scheduling Agent and booked.”
  - “Finally, the Notification Agent explains the final, conflict-free time to the user.”

---

### Slide 9 – Evaluation & Limitations

**Slide title:** Evaluation & Limitations

**What you say:**

- “In terms of what the system does well:”
  - “It clearly demonstrates **multi-agent collaboration** for a real-world task.”
  - “The architecture is **modular**, easy to understand, and easy to extend.”
- “However, there are also some limitations:”
  - “The NLU is currently **rule-based**, so it may not understand very complex or ambiguous sentences.”
  - “The calendar is **in-memory only**, so appointments are lost when the program stops.”
  - “Conflict resolution uses a simple heuristic and doesn’t negotiate with the user.”
- “These limitations are intentional to keep the core idea clear and to leave room for future work.”

---

### Slide 10 – Future Work

**Slide title:** Future Work

**What you say:**

- “There are several clear directions for future improvements.”
- “First, integrating a **real LLM** such as GPT for the NLU Agent. That would allow the system to handle more varied and complex language.”
- “Second, connecting to **real calendar services** like Google Calendar or Outlook so the assistant could be used in daily life.”
- “Third, adding more agents, such as:
  - A **Reminder Agent** to schedule notifications before an appointment.
  - A **User Preference Agent** that learns preferred times or days.
  - An **Explanation Agent** that explains why certain time slots were chosen.”
- “These extensions would keep the multi-agent architecture but add more intelligence and practical value.”

---

### Slide 11 – Takeaways & Conclusion

**Slide title:** Key Takeaways

**What you say:**

- “To summarize, this project shows how a **multi-agent AI architecture** can automate appointment scheduling from natural language.”
- “Instead of a single monolithic model, I used several **specialized agents** that collaborate via message passing and a shared context.”
- “This design is **modular, testable, and extensible**, and it mirrors how many real-world AI orchestration systems are built.”
- “Thank you for listening. I’m happy to answer any questions about the implementation, the design decisions, or potential extensions.”

---

### Optional Slide – Q&A

**Slide title:** Questions?

**What you say:**

- “Thank you. I’m now open to questions.”
- If asked technical questions, you can:
  - Refer to the `agents.py` file for how each agent is implemented.
  - Refer to the `calendar_store.py` file for conflict checking and slot suggestions.
  - Explain how you would plug in an LLM or external API into the existing agent interfaces.

---

## Demo Speaker Notes – Major Changes Since Initial Code

Use this section when **demoing the current app** and when **explaining what was added or changed** after the first version. It highlights the main enhancements for evaluators and Q&A.

---

### What the initial code had

- **CLI only** – terminal menu: create appointment, list, exit.
- **Four agents** – NLU, Scheduling, Conflict Resolution, Notification.
- **Conflict** – when a slot was busy, the system **auto-booked** the next suggested slot (no user confirmation).
- **Simple date parsing** – “today”, “tomorrow”, weekday names only.
- **No business rules** – any time could be booked.
- **No reschedule or cancel** – only “create appointment”.

---

### Major change 1 – Streamlit web UI

**What you say:**  
“The first big change was adding a **Streamlit web interface** so we’re not limited to the command line. The app runs in the browser with a **sidebar** and a **main chat area**.”

**Highlights:**
- **Sidebar** – calendar is always visible; appointment cards with date and time.
- **Main area** – title, short description of what the assistant can do, **conversation thread**, and **text input** (cleared after each send).
- **No scroll to start** – input is near the top so the user can type and send without scrolling.

---

### Major change 2 – Conflict: ask user before booking

**What you say:**  
“Originally, when there was a **conflict**, the system automatically booked the next suggested slot. We changed it so the assistant **asks the user**: ‘Does that time work? Reply yes or no.’ Only after the user says **yes** do we book it.”

**Highlights:**
- Orchestrator returns a **pending suggested slot**; the UI shows it and Yes/No.
- User can **decline** and suggest another day or time later.

---

### Major change 3 – Reschedule and Cancel agents

**What you say:**  
“We added two more agents so the system is **conversational** and not only for creating appointments.”

**Highlights:**
- **Reschedule Agent** – understands “Reschedule my dentist to 4pm” or “Move my meeting to Tuesday”; finds the existing appointment, removes the old slot, and books the new time (with conflict check and business-hours rules).
- **Cancel Agent** – understands “Cancel my dentist tomorrow”; finds the appointment and removes it. If the user has no appointments or the phrase doesn’t match, we reply clearly and list current appointments when helpful.

---

### Major change 4 – Conversational and out-of-scope handling

**What you say:**  
“We made the assistant **conversational** and **safe**: it doesn’t try to book when the user is just chatting or asking something off-topic.”

**Highlights:**
- **Greetings** – “Hi”, “Hello” get a short intro and “How can I help?”
- **“How are you?”** – we reply in a friendly way (“I’m doing well, thank you for asking! How are you? How can I help you today?”) and **don’t book**.
- **Out-of-scope** – e.g. “How is the weather?” gets a polite message that we only help with appointments and **no booking**.
- **Intent detection** – we distinguish greeting, list, cancel, reschedule, confirm yes/no, out-of-scope, and create, so we only run the booking pipeline when appropriate.

---

### Major change 5 – Business hours and rules

**What you say:**  
“We added **business rules** so the system only allows bookings during working hours and never on weekends or lunch.”

**Highlights:**
- **Hours** – 8am–5pm; **last appointment start** 4:30pm.
- **Lunch** – no appointments 1pm–2pm.
- **Weekdays only** – no weekends.
- **Holidays** – a small list (e.g. New Year’s, July 4th, Christmas); no booking on those days.
- **CalendarStore** – `check_business_hours()` and `get_available_slots()` respect these rules; the Scheduling Agent rejects invalid slots with a clear message.

---

### Major change 6 – Date-only booking and slot choice

**What you say:**  
“If the user says only a **date** and no time—for example ‘Book a meeting tomorrow’—we **don’t guess**. We look up **available slots** for that day and ask the user to **pick a time**.”

**Highlights:**
- NLU detects **date_only** (date keyword but no explicit time).
- Orchestrator calls **get_available_slots(date)** and replies with a list like “On Monday the available times are: 08:00, 08:30, … Which time would you like?”
- We store a **pending_slot_request**; when the user replies with a time (e.g. “2pm”), we complete the booking. All within business hours.

---

### Major change 7 – Richer date parsing

**What you say:**  
“We extended the **NLU date parsing** so the assistant understands more natural date formats.”

**Highlights:**
- **Month + day** – e.g. “July 4th”, “March 3”, “January 15”.
- **Numeric m/d** – e.g. “3/3”, “12/25”.
- **Full date m/d/yyyy** – e.g. “12/31/2026”.
- **Time parsing** – we require **am/pm** or a colon (e.g. “3pm”, “14:30”) so that “July **4th**” is never parsed as 4:00; “at 3pm” is correctly used as the time.

---

### Major change 8 – UI polish and input behavior

**What you say:**  
“We refined the **UI** for a cleaner demo and better UX.”

**Highlights:**
- **Sidebar** – dark theme; calendar cards with clear date/time.
- **Main** – larger title, **short info text** explaining the assistant can book, reschedule, and cancel.
- **No white box** – conversation area uses a transparent background so it doesn’t look like a separate box under the info text.
- **Input clears after send** – after the user sends a message (or Yes/No), the text box is cleared so they can type the next request immediately.

---

### Demo script (current app)

**Opening:**  
“I’ll show the **Streamlit app**. The **sidebar** shows the calendar; the **main area** is where we chat.”

**Suggested flows:**

1. **Greeting / How are you**  
   Type: “How are you?”  
   Point out: friendly reply, no booking, and the assistant offers to help with appointments.

2. **Book with full date**  
   Type: “Book an appointment on July 4th at 3pm” or “Book an appointment on 12/31/2026 at 2pm.”  
   Point out: date and time are parsed correctly and the appointment appears in the **sidebar** calendar.

3. **Date-only then time**  
   Type: “Book a meeting tomorrow.”  
   Point out: assistant lists **available slots** and asks for a time.  
   Type: “2pm.”  
   Point out: booking is completed and the calendar updates.

4. **Conflict and confirm**  
   Book something at 10am, then try “Book a meeting today at 10:30.”  
   Point out: assistant suggests another slot and asks “Does that work? Yes or no.”  
   Click **Yes** or type “yes” and show the new appointment in the sidebar.

5. **Reschedule**  
   Type: “Reschedule my meeting to 4pm.”  
   Point out: Reschedule Agent finds the meeting and moves it; calendar updates.

6. **Cancel**  
   Type: “Cancel my meeting tomorrow.”  
   Point out: Cancel Agent removes it; sidebar calendar updates.

7. **Out-of-scope**  
   Type: “How is the weather?”  
   Point out: polite “I only help with appointments” message and no booking.

**Closing:**  
“These changes make the system **conversational**, **rule-aware**, and **safer**—while keeping the same multi-agent design underneath.”

