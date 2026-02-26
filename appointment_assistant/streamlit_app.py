from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st

from appointment_assistant.agents import Orchestrator
from appointment_assistant.calendar_store import CalendarStore


def inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Remove top space and Streamlit chrome */
        #MainMenu, footer, header { visibility: hidden; }
        .stDeployButton { display: none; }
        .block-container { padding-top: 0.75rem !important; padding-bottom: 0.5rem !important; max-width: 100%; }
        .stApp > div:first-child { padding-top: 0.5rem !important; }

        /* Main area – warm neutral */
        .stApp { background: #faf8f5; }

        /* Sidebar – calendar */
        [data-testid="stSidebar"] { background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); }
        [data-testid="stSidebar"] .stMarkdown { color: #e2e8f0; }
        .sidebar-title { font-size: 0.95rem; font-weight: 700; color: #f8fafc; letter-spacing: 0.02em; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid rgba(248,250,252,0.2); }
        .cal-card {
            background: rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 0.85rem 0.9rem;
            margin-bottom: 0.6rem;
            border-left: 4px solid #38bdf8;
            color: #e2e8f0;
        }
        .cal-card.alt { border-left-color: #34d399; }
        .cal-card .cal-title { font-weight: 600; font-size: 0.9rem; color: #fff; margin-bottom: 0.25rem; }
        .cal-card .cal-time { font-size: 0.8rem; color: #94a3b8; font-variant-numeric: tabular-nums; }
        .cal-card .cal-date { font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; }
        .cal-empty { text-align: center; padding: 1.25rem 0.75rem; color: #94a3b8; font-size: 0.8rem; background: rgba(0,0,0,0.2); border-radius: 8px; border: 1px dashed rgba(255,255,255,0.15); }

        /* Main title – larger, no extra space below */
        .main-title { font-size: 1.6rem; font-weight: 700; color: #1e293b; margin: 0 0 0.15rem 0; letter-spacing: -0.02em; }
        .main-info { font-size: 0.8rem; color: #64748b; line-height: 1.45; margin: 0 0 0.6rem 0; }

        /* Conversation – fits viewport, scroll inside, no white box */
        .conv-wrap { 
            background: transparent; 
            padding: 0.5rem 0 0.75rem 0;
            min-height: 220px;
            max-height: 55vh;
            overflow-y: auto;
            margin-bottom: 0.5rem;
        }
        .msg-row { margin-bottom: 0.75rem; }
        .msg-row.user .msg-wrap { margin-left: 15%; }
        .msg-label { font-size: 0.65rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.15rem; }
        .msg-user {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: #fff;
            border-radius: 10px 10px 4px 10px;
            padding: 0.55rem 0.9rem;
            font-size: 0.85rem;
            line-height: 1.4;
            box-shadow: 0 2px 8px rgba(59,130,246,0.3);
        }
        .msg-assistant {
            background: #f1f5f9;
            color: #334155;
            border-radius: 10px 10px 10px 4px;
            padding: 0.55rem 0.9rem;
            font-size: 0.85rem;
            line-height: 1.4;
            border: 1px solid #e2e8f0;
        }
        .chat-placeholder { text-align: center; padding: 1.5rem; color: #94a3b8; font-size: 0.85rem; }

        /* Pending banner */
        .pending-banner {
            background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
            border: 1px solid #6ee7b7;
            border-radius: 8px;
            padding: 0.5rem 0.75rem;
            margin-bottom: 0.5rem;
            font-size: 0.8rem;
            color: #065f46;
        }

        /* Input row – compact */
        .input-row { margin-top: 0.25rem; }
        div[data-testid="stVerticalBlock"] > div:has(textarea) .stTextArea textarea { border-radius: 10px; border: 1px solid #e2e8f0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_or_create_state() -> tuple[CalendarStore, Orchestrator]:
    if "calendar" not in st.session_state:
        st.session_state.calendar = CalendarStore()
        st.session_state.orchestrator = Orchestrator(st.session_state.calendar)
        st.session_state.last_transcript = None
        st.session_state.pending_alternative = None
        st.session_state.pending_slot_request = None
        st.session_state.input_key_counter = 0
    return st.session_state.calendar, st.session_state.orchestrator


def render_sidebar_calendar(calendar: CalendarStore) -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-title">📅 Calendar</div>', unsafe_allow_html=True)
        if not calendar.appointments:
            st.markdown(
                '<div class="cal-empty">No appointments yet.<br>Book one in the chat.</div>',
                unsafe_allow_html=True,
            )
        else:
            for i, appt in enumerate(calendar.appointments):
                cls = "cal-card alt" if i % 2 == 1 else "cal-card"
                title_safe = appt.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                date_str = appt.start.strftime("%a %d %b")
                time_str = f"{appt.start.strftime('%H:%M')} – {appt.end.strftime('%H:%M')}"
                st.markdown(
                    f'<div class="{cls}">'
                    f'<div class="cal-title">{title_safe}</div>'
                    f'<div class="cal-time">{time_str}</div>'
                    f'<div class="cal-date">{date_str}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )


def render_main(orchestrator: Orchestrator) -> None:
    pending_alt = st.session_state.get("pending_alternative")
    pending_slot = st.session_state.get("pending_slot_request")

    st.markdown('<p class="main-title">Appointment Assistant</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="main-info">'
        'I can <strong>book</strong> appointments (e.g. &ldquo;Book a meeting tomorrow at 2pm&rdquo;), '
        '<strong>reschedule</strong> them (e.g. &ldquo;Move my dentist to 4pm&rdquo;), '
        'and <strong>cancel</strong> them (e.g. &ldquo;Cancel my meeting tomorrow&rdquo;). '
        'Your calendar is in the sidebar. Just type what you need below.'
        '</p>',
        unsafe_allow_html=True,
    )

    if pending_alt:
        st.markdown(
            f'<div class="pending-banner">'
            f'Suggested: {pending_alt.start.strftime("%A %d %B at %H:%M")}. Reply <strong>yes</strong> or <strong>no</strong>.</div>',
            unsafe_allow_html=True,
        )
    if pending_slot:
        st.caption("Pick a time (e.g. **2pm** or **14:00**)")

    transcript = st.session_state.get("last_transcript")
    st.markdown('<div class="conv-wrap">', unsafe_allow_html=True)
    if not transcript:
        st.markdown(
            '<div class="chat-placeholder">Say hello or ask to book, reschedule, or cancel an appointment.</div>',
            unsafe_allow_html=True,
        )
    else:
        for msg in transcript:
            if msg.sender.lower() == "user":
                st.markdown(
                    '<div class="msg-row user"><div class="msg-wrap">'
                    '<div class="msg-label">You</div>'
                    f'<div class="msg-user">{msg.content.replace("<", "&lt;").replace(chr(10), "<br>")}</div>'
                    "</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="msg-row assistant"><div class="msg-wrap">'
                    '<div class="msg-label">Assistant</div>'
                    f'<div class="msg-assistant">{msg.content.replace("<", "&lt;").replace(chr(10), "<br>")}</div>'
                    "</div></div>",
                    unsafe_allow_html=True,
                )
    st.markdown("</div>", unsafe_allow_html=True)

    placeholder = "Book tomorrow at 2pm · Reschedule to 4pm · Cancel my meeting"
    if pending_slot:
        placeholder = "e.g. 2pm or 14:00"

    input_key = f"input_msg_{st.session_state.get('input_key_counter', 0)}"
    user_text = st.text_area(
        "Message",
        value="",
        height=56,
        placeholder=placeholder,
        label_visibility="collapsed",
        key=input_key,
    )

    c1, c2, c3, _ = st.columns([1, 1, 1, 5])
    with c1:
        submit = st.button("Send", type="primary", use_container_width=True)
    with c2:
        if pending_alt:
            yes_click = st.button("Yes", key="yes_btn", use_container_width=True)
            no_click = st.button("No", key="no_btn", use_container_width=True)
        else:
            yes_click = no_click = False
    with c3:
        clear = st.button("Clear", use_container_width=True)

    if clear:
        st.session_state.last_transcript = None
        st.session_state.pending_alternative = None
        st.session_state.pending_slot_request = None
        st.session_state.input_key_counter = st.session_state.get("input_key_counter", 0) + 1
        st.rerun()

    if pending_alt and yes_click:
        transcript, p_alt, p_slot = orchestrator.handle_user_request("yes", pending_alt, pending_slot)
        st.session_state.last_transcript = transcript
        st.session_state.pending_alternative = p_alt
        st.session_state.pending_slot_request = p_slot
        st.session_state.input_key_counter = st.session_state.get("input_key_counter", 0) + 1
        st.rerun()

    if pending_alt and no_click:
        transcript, p_alt, p_slot = orchestrator.handle_user_request("no", pending_alt, pending_slot)
        st.session_state.last_transcript = transcript
        st.session_state.pending_alternative = p_alt
        st.session_state.pending_slot_request = p_slot
        st.session_state.input_key_counter = st.session_state.get("input_key_counter", 0) + 1
        st.rerun()

    if submit:
        cleaned = user_text.strip()
        if not cleaned:
            st.warning("Please enter a message.")
        else:
            transcript, p_alt, p_slot = orchestrator.handle_user_request(
                cleaned, pending_alt, pending_slot
            )
            st.session_state.last_transcript = transcript
            st.session_state.pending_alternative = p_alt
            st.session_state.pending_slot_request = p_slot
            st.session_state.input_key_counter = st.session_state.get("input_key_counter", 0) + 1
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Appointment Assistant",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    calendar, orchestrator = get_or_create_state()

    render_sidebar_calendar(calendar)
    render_main(orchestrator)


if __name__ == "__main__":
    main()
