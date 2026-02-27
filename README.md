---
title: Multi-Agent Appointment Assistant
sdk: streamlit
app_file: appointment_assistant/streamlit_app.py
---

### Multi-Agent AI Appointment Assistant

### 1. Overview

This project is a **Multi-Agent AI Appointment Assistant** built in Python.  
It shows how several specialized agents can work together to understand natural‑language requests, schedule appointments, resolve conflicts, and keep a clear conversational experience.

The assistant runs as:

- A **Streamlit web app** (primary demo).
- A simple **CLI app** for the original baseline.

The core idea is a **multi‑agent orchestration pattern** that you can later connect to real calendars or more advanced LLMs.

---

### 2. Features

- **Natural-language appointment requests**  
  “Book a dentist appointment tomorrow at 3pm for 1 hour” or “Book a meeting on 12/31/2026 at 2pm”.

- **Multi-agent architecture**  
  - **NLU Agent** – turns free text into structured appointment data.
  - **Scheduling Agent** – books into the calendar, enforcing business rules.
  - **Conflict Resolution Agent** – suggests alternative times when there’s a clash.
  - **Reschedule Agent** – moves an existing appointment to a new time.
  - **Cancel Agent** – cancels an existing appointment.
  - **Notification Agent** – summarizes the final result in friendly language.
  - **Orchestrator** – coordinates all agents and tracks the conversation.

- **Business rules**  
  - Working days: **Monday–Friday only** (no weekends).
  - Working hours: **8:00–17:00**, last start **16:30**.
  - **Lunch break 13:00–14:00** (no bookings).
  - Basic **holiday list** (e.g. New Year’s, July 4th, Christmas).

- **Smart conflict handling**  
  - Detects overlaps with existing appointments.
  - Proposes a **next free slot** and asks the user to confirm **yes/no** before booking.

- **Reschedule and cancel flows**  
  - “Reschedule my dentist appointment to 4pm” – finds and moves the existing slot.
  - “Cancel my meeting tomorrow” – finds and removes it, or lists what currently exists if unclear.

- **Conversational behavior & out‑of‑scope handling**  
  - Friendly responses to greetings and “How are you?” without booking anything.
  - Out‑of‑scope questions (e.g. weather, jokes) get a polite message that the assistant only handles appointments.

- **Date‑only booking with slot selection**  
  - If the user specifies only a date (“Book a meeting tomorrow”) the system:
    - Lists all **available slots** on that day, respecting business rules.
    - Asks the user to **pick a time** (e.g. “2pm”), then books it.

- **Richer date parsing**  
  - “today”, “tomorrow”, weekday names.
  - Month + day: “July 4th”, “March 3”.
  - Numeric dates:
    - Short: `3/3`, `12/25`.
    - Full: `12/31/2026`.
  - Time parsing avoids confusing “4th” in “July 4th” with 4:00.

- **Streamlit UI**  
  - Sidebar with **calendar cards** (dark theme) showing scheduled appointments.
  - Main area with:
    - Big title and quick description of what the assistant can do.
    - Transparent conversation area.
    - Text input + buttons (Send / Yes / No / Clear).
    - Input automatically clears after each action.

- **Optional real LLM for NLU (OpenAI)**  
  - If configured, the NLU Agent uses an OpenAI chat model to parse appointments.
  - If the LLM is unavailable or fails, it **falls back** to the built‑in rule‑based parser.

---

### 3. Project Structure

At repo root (recommended):

```text
.
├── appointment_assistant/
│   ├── __init__.py
│   ├── agents.py
│   ├── calendar_store.py
│   ├── llm_client.py
│   ├── main.py
│   ├── streamlit_app.py
│   └── requirements.txt  # local use inside the package (may be duplicated at root)
├── requirements.txt       # root-level for deployment (e.g. Hugging Face)
├── README.md
├── DEPLOY_HUGGINGFACE.md  # step-by-step HF deployment guide
└── .gitignore
```

Key modules:

- `agents.py`  
  - Defines `Message`, `ConversationContext`, `Agent` base class.  
  - Implements `NLUAgent`, `SchedulingAgent`, `ConflictResolutionAgent`, `RescheduleAgent`, `CancelAgent`, `NotificationAgent`, and the `Orchestrator`.

- `calendar_store.py`  
  - `Appointment` dataclass.  
  - `CalendarStore` with:
    - `add`, `remove`, `find_conflicts`.
    - `get_available_slots(date, duration)` – respects business rules.
    - `suggest_next_free_slot(candidate)` – used by conflict resolution.
  - `check_business_hours(appointment)` and constants for working hours, lunch, and holidays.

- `llm_client.py`  
  - Thin wrapper over the `openai` Python client.  
  - `parse_appointment_with_llm(user_text)`:
    - Calls an OpenAI chat model (default `gpt-4o-mini`, configurable).
    - Asks for JSON with title, start, end, duration, etc.
    - Returns a Python dict compatible with the rule-based parser.

- `main.py`  
  - Simple CLI runner for the assistant (original interface).

- `streamlit_app.py`  
  - Web UI (sidebar calendar + main chat area).  
  - Manages session state for:
    - Conversation transcript.
    - Currently pending conflict suggestion (`pending_alternative`).
    - Pending date-only slot selection (`pending_slot_request`).

---

### 4. Installation & Setup (Local)

#### 4.1. Clone the repo

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

#### 4.2. Create a virtual environment (recommended)

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# macOS/Linux
source .venv/bin/activate
```

#### 4.3. Install dependencies

From the **repo root** (the folder containing `requirements.txt`):

```bash
pip install -r requirements.txt
```

This installs:

- `streamlit`
- `python-dateutil`
- `openai` (for optional LLM NLU)

---

### 5. Running the Assistant

#### 5.1. Run the Streamlit web app (recommended)

From the repo root:

```bash
streamlit run appointment_assistant/streamlit_app.py
```

Then open the URL printed in the terminal (usually `http://localhost:8501`).

You should see:

- **Sidebar** with the in-memory calendar (cards for each appointment).
- **Main area** with:
  - Title.
  - Short description of capabilities.
  - Chat transcript.
  - Input area and buttons.

Try phrases like:

- “Book a dentist appointment tomorrow at 3pm for 1 hour.”
- “Reschedule my dentist appointment to 4pm.”
- “Cancel my meeting tomorrow.”
- “What appointments do I have?”
- “Book a meeting on July 4th at 3pm.”
- “Book a meeting on 12/31/2026 at 2pm.”
- “Book a meeting tomorrow” → then choose a time from the offered slots.

#### 5.2. Run the CLI version (baseline)

From the repo root:

```bash
python -m appointment_assistant.main
```

Follow the on-screen menu to create and list appointments.

---

### 6. Real LLM Integration (OpenAI)

The system can optionally use a **real LLM** for NLU via the OpenAI API.

#### 6.1. How it works

- `NLUAgent.handle`:
  - If `OPENAI_API_KEY` is set:
    - Calls `parse_appointment_with_llm(user_text)` (in `llm_client.py`).
    - If that returns structured data, it uses it.
  - If not set, or if any error occurs (API, JSON parsing, etc.):
    - Falls back to `_simple_parse(...)`, the existing rule‑based parser.

This keeps the rest of the pipeline unchanged while allowing a more powerful understanding when an LLM is available.

#### 6.2. Enabling the LLM locally

1. Ensure dependencies are installed (see above).
2. Set the API key in your shell (PowerShell example):

   ```powershell
   $env:OPENAI_API_KEY = "sk-...your-real-key..."
   ```

3. (Optional) Choose a model:

   ```powershell
   $env:OPENAI_MODEL = "gpt-4o-mini"
   ```

4. Run Streamlit:

   ```bash
   streamlit run appointment_assistant/streamlit_app.py
   ```

If you unset `OPENAI_API_KEY`, the app automatically returns to the pure rule‑based NLU.

---

### 7. Business Rules & Calendar Logic

The calendar lives in memory via `CalendarStore`:

- **Business hours**  
  - Valid appointment windows are enforced by `check_business_hours`.
- **Available slots**  
  - `get_available_slots(date, duration_minutes)` walks the workday in fixed steps and returns open slots that:
    - Do not overlap existing appointments.
    - Respect lunch and holidays.
- **Conflict resolution**  
  - When a requested time conflicts, `suggest_next_free_slot(candidate)` searches forward on that day for the next free window of the same duration.

These utilities are reused across scheduling, conflict handling, rescheduling, and date‑only booking flows.

---

### 8. Deployment & GitHub

#### 8.1. Basic GitHub steps

From your repo root:

```bash
git init
git add .
git commit -m "Initial multi-agent appointment assistant"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git push -u origin main
```

Replace `<your-username>` and `<your-repo-name>` with your actual GitHub info.

#### 8.2. Deploying on Streamlit Community Cloud

1. Push code to GitHub.
2. Go to Streamlit Community Cloud and create a **New app**.
3. Select your repo and branch `main`.
4. Set the entry point to:

   ```text
   appointment_assistant/streamlit_app.py
   ```

5. Deploy – it will install dependencies from `requirements.txt` and give you a public URL.

#### 8.3. Deploying on Hugging Face Spaces

See `DEPLOY_HUGGINGFACE.md` for a detailed guide. In summary:

- Ensure the **repo root** contains:
  - `appointment_assistant/` folder.
  - Root-level `requirements.txt` (with `streamlit`, `python-dateutil`, `openai`).
- Create a **Space** with SDK = **Streamlit**.
- Set the app file to:

  ```text
  appointment_assistant/streamlit_app.py
  ```

- (Optional) Configure secrets:
  - `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`) to enable the LLM NLU.
- After build completes, you get a **public link** to your assistant.

#### 8.4. Docker / container (optional)

You can also containerize the app:

- Write a `Dockerfile` that:
  - Copies the code.
  - Installs requirements.
  - Runs `streamlit run appointment_assistant/streamlit_app.py`.
- Deploy the image to any container platform (AWS, Azure, Render, etc.).

---

### 9. Extensibility Ideas

This project is intentionally structured for extension:

- Swap the in-memory calendar with:
  - Google Calendar, Outlook, or a database.
- Add agents:
  - **Reminder Agent** – sends reminders before events.
  - **User Preferences Agent** – learns preferred times/days and suggests better slots.
  - **Explanation Agent** – explains why certain slots were suggested or rejected.
- Experiment with:
  - Different LLM prompts or models.
  - Separate NLU, Conflict, and Explanation models orchestrated together.

Overall, the project demonstrates how a **multi-agent architecture plus optional LLMs** can provide a clear, explainable solution for appointment scheduling from natural language.
