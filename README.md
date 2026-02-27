## Multi-Agent AI Appointment Assistant

### 1. Overview

This project is a **multi-agent AI Appointment Assistant** designed as a capstone project.  
It simulates how several specialized AI agents can collaborate to understand a natural-language request, schedule an appointment, resolve conflicts, and confirm the final booking to the user.

The project is implemented in **Python** and runs as a **command-line application**.  
You type a natural language request (for example:  
“Book a dentist appointment for tomorrow at 3pm for 1 hour”), and the system routes it through a pipeline of agents:

- **NLU Agent** – interprets your text and extracts structured appointment details.
- **Scheduling Agent** – checks the in-memory calendar and tries to add the appointment.
- **Conflict Resolution Agent** – proposes an alternative time if there is a conflict.
- **Notification Agent** – generates a clear, user-friendly confirmation message.

This architecture demonstrates **multi-agent collaboration**, **task specialization**, and a **simple orchestration layer** you can extend with real LLMs or external calendar APIs.

---

### 2. Features

- **Natural-language appointment requests**  
  Describe what you want in plain English (date, time, duration, and purpose).

- **Multi-agent pipeline**  
  Separate agents for understanding, scheduling, conflict resolution, and notifications.

- **Conflict detection & simple rescheduling**  
  Detects overlapping appointments and attempts to find the next available 30-minute slot.

- **In-memory calendar**  
  Stores appointments during program execution, with a simple listing view.

- **LLM-ready design**  
  The current NLU agent is intentionally lightweight and rule-based, but its design makes it easy to swap in calls to an LLM API (e.g. OpenAI) for more powerful understanding.

---

### 3. Project Structure

```text
appointment_assistant/
├── agents.py            # All agent classes + orchestrator
├── calendar_store.py    # Appointment model and in-memory calendar
├── main.py              # CLI entrypoint (terminal)
├── streamlit_app.py     # Streamlit web UI
├── __init__.py          # Makes this a Python package
├── requirements.txt     # Python dependencies
├── README.md            # Project documentation (this file)
└── SPEAKER_NOTES.md     # Slide-by-slide speaker notes
```

- **`calendar_store.py`**  
  Defines an `Appointment` dataclass and a `CalendarStore` class that:
  - Stores appointments in memory
  - Detects overlapping appointments
  - Suggests the next free time slot when there is a conflict

- **`agents.py`**  
  Contains:
  - `Message` dataclass – simple message-passing structure between agents.
  - `ConversationContext` – shared state (e.g. parsed appointment, final booking).
  - `Agent` base class – interface for all agents.
  - `NLUAgent` – parses the user’s natural language request into a structured appointment.
  - `SchedulingAgent` – checks conflicts and reserves time on the `CalendarStore`.
  - `ConflictResolutionAgent` – proposes an alternative appointment time.
  - `NotificationAgent` – produces the final user-facing confirmation message.
  - `Orchestrator` – coordinates the flow across all agents for each user request.

- **`main.py`**  
  Implements the **command-line interface**, including:
  - A simple text menu (create appointment, list appointments, exit).
  - Routes each natural-language request through the `Orchestrator`.
  - Prints a conversation-style transcript showing how each agent responded.

- **`streamlit_app.py`**  
  Implements a **Streamlit web UI**:
  - Text area where the user types a natural-language request.
  - Button to trigger the multi-agent pipeline.
  - Left panel: full agent conversation transcript (user + agents).
  - Right panel: live view of the in-memory calendar as a table.

---

### 4. Installation & Setup

#### 4.1. Prerequisites

- **Python 3.10+** installed and available on your PATH.
- A terminal or command prompt (PowerShell, CMD, etc.).

#### 4.2. Create and activate a virtual environment (recommended)

```bash
cd appointment_assistant

# Create virtual environment (Windows)
python -m venv .venv

# Activate (PowerShell)
.\.venv\Scripts\Activate.ps1

# or (CMD)
.\.venv\Scripts\activate.bat
```

#### 4.3. Install dependencies

```bash
pip install -r requirements.txt
```

> Note: The current version uses only the standard library and a light dependency;  
> you can easily add more (e.g. `openai`, `fastapi`) as you extend the project.

---

### 5. Running the Assistant

From the **parent directory** of `appointment_assistant`, you can run either:

#### 5.1. CLI (terminal) mode

```bash
python -m appointment_assistant.main
```

You will see a menu like:

```text
=== Multi-Agent AI Appointment Assistant ===
Type natural language like:
  "Book a dentist appointment for tomorrow at 3pm for 1 hour"
or choose to list existing appointments.

Menu:
1) Create a new appointment (natural language)
2) List appointments
3) Exit
```

##### Example scenario (happy path)

1. Choose `1` to create a new appointment.  
2. Enter:  
   `Book a dentist appointment for tomorrow at 3pm for 1 hour`
3. The assistant will:
   - NLU Agent: Extract the time, date, duration, and title.
   - Scheduling Agent: Check the calendar, find it free, and add the appointment.
   - Notification Agent: Confirm your booking in friendly language.
4. Choose `2` to list appointments and verify that the appointment is stored.

##### Example scenario (conflict + resolution)

1. First, book an appointment:  
   `Schedule a meeting today at 10am for 1 hour`
2. Then, try to book another:  
   `Schedule a catch up for today at 10:30am for 30 minutes`
3. The flow will be:
   - NLU Agent parses the new request.
   - Scheduling Agent detects a conflict with the existing appointment.
   - Conflict Resolution Agent proposes the next available 30-minute slot.
   - Scheduling Agent re-checks and books the proposed alternative.
   - Notification Agent confirms the new, conflict-free booking.

---

#### 5.2. Streamlit web app (browser) mode

To launch the Streamlit UI, from the **parent directory** of `appointment_assistant` run:

```bash
streamlit run appointment_assistant/streamlit_app.py
```

Then open the URL shown in the terminal (usually `http://localhost:8501`).

In the web app you can:

- Type the appointment description into a text area.
- Click **Create appointment** to run the multi-agent pipeline.
- See the **agent transcript** on the left (User, NLU, Scheduling, Conflict Resolution, Notification).
- See a live table of all **current appointments** on the right.

---

### 6. How the Multi-Agent System Works

#### 6.1. Message passing and context

- Each agent receives a `Message` and a shared `ConversationContext`.
- The `ConversationContext` holds:
  - The shared `CalendarStore`
  - Parsed appointment details
  - The final confirmed appointment
- Agents return a list of new messages, which are appended to a transcript.

#### 6.2. Agent responsibilities

- **NLUAgent**
  - Parses free text.
  - Extracts:
    - Date (today, tomorrow, or weekday names)
    - Time (e.g. `3pm`, `15:30`)
    - Duration (e.g. `30 minutes`, `1 hour`)
    - A heuristic title (e.g. “dentist appointment”).

- **SchedulingAgent**
  - Converts the parsed data into an `Appointment`.
  - Uses `CalendarStore` to detect conflicts.
  - On success: saves the appointment and updates the context.
  - On conflict: emits a message with conflict metadata.

- **ConflictResolutionAgent**
  - Reads the conflicting `Appointment`.
  - Uses `CalendarStore.suggest_next_free_slot(...)` to find the next available slot.
  - Updates the context with the suggested alternative.

- **NotificationAgent**
  - Reads the `final_appointment` from the context.
  - Produces a human-friendly confirmation message.

- **Orchestrator**
  - Controls the order:
    1. `NLUAgent`
    2. `SchedulingAgent`
    3. `ConflictResolutionAgent` (if needed)
    4. `SchedulingAgent` again (after alternative)
    5. `NotificationAgent`
  - Returns the full transcript to the CLI to display.

---

### 7. Extending the Project (Ideas for Capstone Enhancements)

- **Integrate a real LLM**  
  Replace the rule-based `NLUAgent` with an LLM-backed one using an API like OpenAI:
  - Send the user’s text and receive structured JSON for date, time, and title.
  - Improves robustness and language coverage.

- **Web or mobile UI**  
  - Build a simple **web front-end** using `FastAPI` + `React` or use `Streamlit` for a quick UI.
  - Add authentication and multiple users.

- **External calendar integration**
  - Connect to Google Calendar or Outlook APIs.
  - Persist appointments across runs and sync with real user calendars.

- **Additional specialized agents**
  - Reminder Agent – schedules reminders before appointments.
  - Preference Agent – learns preferred times/locations for different appointment types.
  - Explanation Agent – explains why certain time slots were chosen or rejected.

---

### 8. How to Present This as a Capstone

When presenting:

- Emphasize **why a multi-agent approach** is useful:
  - Each agent has a clear, focused responsibility.
  - Easier to test and extend compared to a single monolithic model.
- Show the **step-by-step transcript** of how agents collaborate on a request.
- Highlight how you could **plug in more powerful AI models** (LLMs) without changing the overall architecture.
- Discuss trade-offs:
  - Simplicity vs. intelligence (rule-based vs. LLM-based NLU).
  - In-memory vs. persistent / cloud-based calendars.

This README can serve both as documentation for evaluators and as a guide during your live demo.

---

### 9. Deployment & GitHub

#### 9.1. Uploading the project to GitHub

From `C:\Users\sukh1\appointment_assistant`:

```bash
git init
git add .
git commit -m "Initial multi-agent appointment assistant"

# create an empty repo on GitHub, then:
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo-name>.git
git push -u origin main
```

Make sure to replace `<your-username>` and `<your-repo-name>` with your actual GitHub details.

#### 9.2. Deploying the Streamlit app

**Option A – Streamlit Community Cloud (very simple):**

1. Push your code to GitHub as described above.  
2. Go to the Streamlit Community Cloud website and choose **New app**.  
3. Select your GitHub repo, branch `main`, and set the entry point to `appointment_assistant/streamlit_app.py`.  
4. The platform installs `requirements.txt` and hosts your app at a public URL you can share in your report or slides.

**Option B – Run on your own server / VM:**

1. Copy the project to a server (or use `git clone`).  
2. Create a virtual environment and run `pip install -r requirements.txt`.  
3. Start the app with:
   ```bash
   streamlit run appointment_assistant/streamlit_app.py --server.port 80 --server.address 0.0.0.0
   ```
4. Put a reverse proxy (e.g. Nginx) in front if you want a custom domain and HTTPS.

**Option C – Hugging Face Spaces (public working link):**

- See **[DEPLOY_HUGGINGFACE.md](DEPLOY_HUGGINGFACE.md)** for step-by-step instructions to prepare the repo (root `requirements.txt`, correct folder layout), push to GitHub, create a Streamlit Space, and get a shareable URL.

**Option D – Docker / container (optional):**

- Create a small `Dockerfile` that:
  - Copies the code
  - Installs dependencies
  - Uses `streamlit run appointment_assistant/streamlit_app.py` as the container command  
- Deploy that image to any container-friendly platform (Azure, AWS, Render, etc.).

