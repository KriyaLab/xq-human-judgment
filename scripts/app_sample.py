# /root/xq_poc/app.py  (RECTIFIED)
import os, json, re, time, sqlite3
from pathlib import Path
from textwrap import dedent
from email.utils import parseaddr

import requests
import streamlit as st

# --- TRIAL HELPER (inserted automatically) ---
from datetime import datetime, timezone
try:
    import dateutil.parser as _dp
    _HAS_DATEUTIL = True
except Exception:
    _HAS_DATEUTIL = False

def _parse_dt_safe(s):
    if not s:
        return None
    try:
        if _HAS_DATEUTIL:
            dt = _dp.isoparse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        else:
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except Exception:
        return None

def is_trial_active(user_record):
    """
    Defensive trial check.
    Returns (bool active, dict debug)
    Trial active while BOTH:
      - account age < 7 days
      - idea_count < 2
    """
    debug = {}
    idea_count = int(user_record.get("idea_count") or 0)
    debug['idea_count'] = idea_count

    created_at = user_record.get("created_at")
    created_dt = _parse_dt_safe(created_at)
    if created_dt is None:
        created_dt = datetime.now(timezone.utc)
        debug['created_at_used'] = 'missing_or_invalid_set_now'
    else:
        debug['created_at_used'] = created_at

    now = datetime.now(timezone.utc)
    delta_days = (now - created_dt).total_seconds() / 86400.0
    debug['delta_days'] = delta_days

    active = (delta_days < 7.0) and (idea_count < 2)
    debug['active'] = active
    return active, debug
# --- END TRIAL HELPER ---
# ---------------------------
# Prompt templates for VET / SHAPE / SCOPE / LAUNCH
# Insert this AFTER the trial helper and before any call to groq_chat(...)
# ---------------------------
from textwrap import dedent

# VET
VET_SYSTEM = dedent("""\
You are an expert startup vetting assistant. Your task is to evaluate an idea quickly and produce a compact, factual JSON report suitable for programmatic parsing.

REQUIREMENTS:
- Output exactly one JSON object inside aetc etc ...
""")

def VET_USER(industry: str, one_liner: str, desc: str, founder_ctx: str) -> str:
    prompt = dedent(f"""\
    Evaluate this startup idea.

    Industry: {industry}
    One-liner: {one_liner}
    Description: {desc}
    Founder context: {founder_ctx}

    Produce the JSON object as specified by the system instructions above.
    """)
    return prompt

# SHAPE
SHAPE_SYSTEM = dedent("""\
You are an expert product strategist. Given an idea, produce improved one-liner variants and short rationale.

REQUIREMENTS:
- Return exactly one JSON object etc etc ...
""")

def SHAPE_USER(one_liner: str, vet_json_str: str) -> str:
    prompt = dedent(f"""\
    Original one-liner: {one_liner}
    VET output: {vet_json_str}

    Generate two improved variants and the fields required by SHAPE_SYSTEM.
    """)
    return prompt

# SCOPE
SCOPE_SYSTEM = dedent("""\
You are a pragmatic product manager. Produce a concise MVP (30-day) scope.

REQUIREMENTS:
- Output exactly one JSON object inside a fenced ```json ... ``` block.
- JSON keys:
  - etc etc)
""")

def SCOPE_USER(base_one_liner: str, industry: str, constraints: str) -> str:
    prompt = dedent(f"""\
    One-liner to scope: {base_one_liner}
    Industry: {industry}
    Constraints: {constraints}

    Produce a 30-day MVP scope per SCOPE_SYSTEM.
    """)
    return prompt

# LAUNCH
LAUNCH_SYSTEM = dedent("""\
You are a go-to-market operator. Produce a compact launch plan and deck outline.

REQUIREMENTS:
- Output exactly one JSON object inside a fenced ```json ... ``` block.
- JSON keys:
  - ietc etc
""")

def LAUNCH_USER(one_liner: str, icp_hint: str) -> str:
    prompt = dedent(f"""\
    One-liner: {one_liner}
    ICP hint: {icp_hint}

    Produce the LAUNCH JSON per LAUNCH_SYSTEM.
    """)
    return prompt

# ---------------------------
# end prompt templates
# ---------------------------

from dotenv import load_dotenv
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT

# --- Project type wording helpers ---
def get_step_labels(project_type: str):
    if project_type == "tech":
        return [
            "VET - Technical Feasibility & Market Check",
            "SHAPE - Refine Product & IP Roadmap",
            "SCOPE - MVP / Prototype Build Plan",
            "LAUNCH - Commercialisation & Scale Strategy",
        ]
    # default: consumer
    return [
        "VET - Business Viability & Market Check",
        "SHAPE - Refine Offer & Target Market",
        "SCOPE - Launch-Ready Business Plan",
        "LAUNCH - Go-to-Market & Growth Plan",
    ]

def get_step_subheaders(project_type: str):
    if project_type == "tech":
        return {
            "vet":    "Assess technical feasibility, market need, and risk profile.",
            "shape":  "Sharpen the product roadmap and defensibility.",
            "scope":  "Define a 30-day prototype plan with must-builds.",
            "launch": "Map commercialisation path and scale levers.",
        }
    return {
        "vet":    "Check if this business can work and where the risks are.",
        "shape":  "Sharpen the offer and who it’s for.",
        "scope":  "Define a 30-day launch-ready plan with priorities.",
        "launch": "Pick one channel and get a practical 30–60 day playbook.",
    }

def generate_vet_pdf(user: dict, vet_data: dict, logo_path: str = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_heading = styles["Heading1"]
    style_heading.alignment = TA_LEFT

    story = []

    # Add logo if available
    if logo_path and Path(logo_path).exists():
        try:
            story.append(Image(str(logo_path), width=2*inch, height=2*inch))
            story.append(Spacer(1, 12))
        except:
            pass

    # Header
    story.append(Paragraph("XQ — Investor-Readiness Report", style_heading))
    story.append(Spacer(1, 12))

    # User info
    story.append(Paragraph(f"<b>Name:</b> {user['name']}", style_normal))
    story.append(Paragraph(f"<b>Email:</b> {user['email']}", style_normal))
    story.append(Paragraph(f"<b>Phone:</b> {user['phone']}", style_normal))
    story.append(Spacer(1, 12))

    # Verdict
    story.append(Paragraph(f"<b>Verdict:</b> {vet_data.get('verdict', '-')}", style_normal))
    story.append(Spacer(1, 12))

    # Summary
    story.append(Paragraph("<b>Summary:</b>", style_normal))
    story.append(Paragraph(vet_data.get("summary", "—"), style_normal))
    story.append(Spacer(1, 12))

    # Scores
    story.append(Paragraph("<b>Scores:</b>", style_normal))
    for k, v in vet_data.get("scores", {}).items():
        story.append(Paragraph(f"{k.replace('_',' ').title()}: {v}", style_normal))
    story.append(Spacer(1, 12))

    # Top Risks
    story.append(Paragraph("<b>Top Risks:</b>", style_normal))
    for item in vet_data.get("top_risks", []):
        story.append(Paragraph(f"• {item}", style_normal))
    story.append(Spacer(1, 12))

    # Must Fix
    story.append(Paragraph("<b>Must Fix:</b>", style_normal))
    for item in vet_data.get("must_fix", []):
        story.append(Paragraph(f"• {item}", style_normal))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ---------------------------
# ENV & CONFIG
# ---------------------------
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "xq_logo.png"  # change if needed
DB_PATH = BASE_DIR / "xq.db"

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ---------------------------
# DB (self-contained)
# ---------------------------
def db_init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT
        )""")
        con.commit()

def db_upsert_user(name: str, email: str, phone: str) -> dict:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                idea_count INTEGER DEFAULT 0
            )
        """)
        con.commit()

        # Check if user exists
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        if row:
            uid = row[0]
            cur.execute("UPDATE users SET name=?, phone=? WHERE id=?", (name, phone, uid))
        else:
            cur.execute("INSERT INTO users(name, email, phone) VALUES (?,?,?)", (name, email, phone))
            uid = cur.lastrowid
        con.commit()

        # Return updated record
        cur.execute("SELECT id, name, email, phone, created_at, idea_count FROM users WHERE id=?", (uid,))
        user_row = cur.fetchone()
        return {
            "id": user_row[0],
            "name": user_row[1],
            "email": user_row[2],
            "phone": user_row[3],
            "created_at": user_row[4],
            "idea_count": user_row[5]
        }

def db_get_user_by_email(email: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                idea_count INTEGER DEFAULT 0
            )
        """)
        con.commit()

        cur.execute("SELECT id, name, email, phone, created_at, idea_count FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "created_at": row[4],
                "idea_count": row[5]
            }
        return None

# ---------------------------
# LLM (Groq) minimal wrapper
# ---------------------------
class GroqError(Exception): ...

def groq_chat(messages, model: str = GROQ_MODEL, temperature: float = 0.2, max_tokens: int = 900, retries: int = 3, timeout: int = 30) -> str:
    if not GROQ_API_KEY:
        raise GroqError("GROQ_API_KEY missing. Add it to .env or environment.")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(GROQ_API_URL, headers=headers, data=json.dumps(payload), timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            last_err = GroqError(f"HTTP {r.status_code}: {r.text[:400]}")
        except requests.RequestException as e:
            last_err = e
        time.sleep(1.5 * attempt)
    raise GroqError(f"Groq chat failed after {retries} tries: {last_err}")

# ---------------------------
# Helpers
# ---------------------------
def extract_json_block(text: str):
    if not text:
        return None
    fence = re.search(r"""```json\s*(\{.*?\})\s*```""", text, flags=re.S|re.M)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    brace = re.search(r"(\{.*\})", text, flags=re.S)
    if brace:
        try:
            return json.loads(brace.group(1))
        except json.JSONDecodeError:
            return None
    return None

def clean_input(text: str) -> str:
    return (text or '').strip().replace('\u200b', '').replace('\xa0', '').replace('\u200c', '')

def valid_email(e: str) -> bool:
    e = (e or "").strip().replace("\u200b", "")
    _, addr = parseaddr(e)
    if not addr or "@" not in addr:
        return False
    local, _, domain = addr.rpartition("@")
    return bool(local and domain and "." in domain)

def clean_phone(p: str) -> str:
    return re.sub(r"\D+", "", p or "")

def valid_phone(p: str) -> bool:
    digits = clean_phone(p)
    return len(digits) >= 10

# ---------------------------
# Trial Limit Helpers (updated)
# ---------------------------
def increment_idea_count(user_id: int):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("UPDATE users SET idea_count = COALESCE(idea_count,0) + 1 WHERE id=?", (user_id,))
        con.commit()

# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="XQ – Don't build. Think.", page_icon="XQ", layout="wide")
db_init()

# Header / Top bar with logo + tagline
col_logo, col_tag = st.columns([1, 3], vertical_alignment="center")
with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), caption=None, use_container_width=True)
    else:
        st.markdown("###  XQ")
with col_tag:
    st.markdown("<h2 style='margin-bottom:0;'>Don't build — think.</h2>", unsafe_allow_html=True)
    st.caption("Investment-readiness for founders. Brutal, practical, fast.")

st.divider()

# Sidebar: user capture
if "state" not in st.session_state:
    st.session_state.state = {
        "industry": "F&B / Cloud Kitchen",
        "one_liner": "",
        "desc": "",
        "founder_ctx": "",
        "vet_json": None,
        "shape_json": None,
        "chosen_variant": "",
        "scope_json": None,
        "launch_json": None,
        "project_type": None,  # "tech" or "consumer"
        "user": {"id": None, "name": "", "email": "", "phone": ""},
    }
S = st.session_state.state

# ---------------------------
# Sidebar (login + project type)
# ---------------------------
# --- Sidebar heartbeat (always render this first) ---
st.sidebar.markdown("🫀 Sidebar loaded")

# --- Sidebar controls wrapped in a function so heartbeat still shows even if an error occurs ---
def render_sidebar():
    try:
        if S["user"]["id"]:
            st.sidebar.success(f" Hi, {S['user']['name']} ({S['user']['email']})")

            # Project type selection
            ptype_label = "What type of project are you working on?"
            ptype_options = (
                "Tech / Deep-Tech (AI, SaaS, Defence, IP)",
                "Consumer Business (Restaurant, Apparel, D2C, Services)",
            )
            ptype_map = {ptype_options[0]: "tech", ptype_options[1]: "consumer"}

            if not S.get("project_type"):
                choice = st.sidebar.radio(ptype_label, ptype_options, key="ptype_first")
                if st.sidebar.button("Save Project Type"):
                    S["project_type"] = ptype_map[choice]
                    st.rerun()
            else:
                st.sidebar.caption(
                    f"Project type: **{'Tech / Deep-Tech' if S['project_type']=='tech' else 'Consumer Business'}**"
                )
                with st.sidebar.expander("Change project type"):
                    choice = st.sidebar.radio(
                        ptype_label,
                        ptype_options,
                        index=0 if S["project_type"] == "tech" else 1,
                        key="ptype_change",
                    )
                    if st.sidebar.button("Update Project Type"):
                        S["project_type"] = ptype_map[choice]
                        st.rerun()

            if st.sidebar.button("Sign Out"):
                S["user"] = {"id": None, "name": "", "email": "", "phone": ""}
                S["vet_json"] = None
                S["shape_json"] = None
                S["scope_json"] = None
                S["launch_json"] = None
                st.rerun()

        else:
            st.sidebar.markdown("### Free Trial Access")
            mode = st.sidebar.radio("Choose Action", ["Login", "Register"], key="auth_mode")

            email = st.sidebar.text_input("Email", value=S["user"]["email"], key="auth_email")
            phone = st.sidebar.text_input("Phone", value=S["user"]["phone"], key="auth_phone")

            if mode == "Login":
                if st.sidebar.button("Login", key="auth_login_btn"):
                    user = db_get_user_by_email(email.lower().strip())
                    if user and clean_phone(user["phone"]) == clean_phone(phone):
                        S["user"] = user
                        st.sidebar.success(f"Welcome back, {user['name']}!")
                        st.rerun()
                    else:
                        st.sidebar.error("No matching account found. Please register first.")
            else:
                name = st.sidebar.text_input("Your Name", value=S["user"]["name"], key="auth_name")
                if st.sidebar.button("Register", key="auth_register_btn"):
                    if not name.strip():
                        st.sidebar.error("Name is required.")
                    elif not valid_email(email):
                        st.sidebar.error("Valid email address is required.")
                    elif not valid_phone(phone):
                        st.sidebar.error("Valid 10-digit phone number is required.")
                    elif db_get_user_by_email(email.lower().strip()):
                        st.sidebar.error("Email already registered. Please log in instead.")
                    else:
                        user = db_upsert_user(name.strip(), email.lower().strip(), clean_phone(phone))
                        S["user"] = user
                        st.sidebar.success("Registration successful!")
                        st.rerun()

            st.sidebar.info("Enter your email/phone to log in, or register if new.")
    except Exception as e:
        # keep sidebar visible and show any error *inside* the sidebar
        st.sidebar.error(f"Sidebar error: {e!s}")

render_sidebar()

# Tabs
disabled_tabs = not bool(S["user"]["id"])
labels = get_step_labels(S.get("project_type") or "consumer")
_sub = get_step_subheaders(S.get("project_type") or "consumer")
tab1, tab2, tab3, tab4 = st.tabs([
    labels[0] + (" (locked)" if disabled_tabs else ""),
    labels[1] + (" (locked)" if disabled_tabs else ""),
    labels[2] + (" (locked)" if disabled_tabs else ""),
    labels[3] + (" (locked)" if disabled_tabs else "")
])


# --- VET ---
with tab1:    
    if disabled_tabs:
        st.info("Unlock by saving your details in the left panel.")
    else:
        st.subheader("VET — Brutal Investor Check")
        st.markdown(f"#### {_sub['vet']}")
        # Defensive industry list (Tech users will see Cloud Kitchen / Retail)
        S["industry"] = st.selectbox("Industry", ["F&B / Cloud Kitchen", "Retail / SME", "SaaS / IT", "Services", "Other"], index=0)
        S["one_liner"] = st.text_input("Your one-liner (pitch in one sentence)", value=S["one_liner"])
        S["desc"] = st.text_area("Brief description (what do you do?)", height=100, value=S["desc"])
        S["founder_ctx"] = st.text_area("Founder context (capital, city/tier, team)", height=80, value=S["founder_ctx"])

        # Use robust trial check (is_trial_active)
        try:
            trial_ok, trial_debug = is_trial_active(S["user"])
        except Exception as _e:
            # fail safe: treat as active to avoid accidental lockouts while we debug
            trial_ok, trial_debug = True, {"error": str(_e)}

        if not trial_ok:
            st.error("Your free trial is over (7 days or 2 ideas).")
            # optional debug during QA (remove/comment out in production)
            # st.caption(f"TRIAL DEBUG: {trial_debug}")
        else:
            # Visible hint + explicit CTA
            st.info("Tip: Press Ctrl+Enter to submit, or click the blue **Run VET** button below.")
            if st.button("Run VET", type="primary"):
                try:
                    messages = [
                        {"role": "system", "content": VET_SYSTEM},
                        {"role": "user", "content": VET_USER(S["industry"], S["one_liner"], S["desc"], S["founder_ctx"])},
                    ]
                    out = groq_chat(messages, temperature=0.15, max_tokens=900)
                    data = extract_json_block(out)
                    if not data:
                        st.warning("Could not parse JSON. Showing raw output:")
                        st.code(out)
                    else:
                       # success: increment idea_count AFTER successful response
                       try:
                           increment_idea_count(S["user"]["id"])
                       except Exception as e:
                           print("WARNING: failed to increment idea_count:", e)

                       S["vet_json"] = data
                       pdf_bytes = generate_vet_pdf(S["user"], S["vet_json"], logo_path=str(LOGO_PATH))
                       st.download_button(
                         "📄 Download VET Report (PDF)",
                         data=pdf_bytes,
                         file_name="xq_vet_report.pdf",
                         mime="application/pdf"
                       )
                       st.success(f"Verdict: {data.get('verdict','?')}. Now go to the SHAPE tab to refine your idea.")
                       if st.button("👉 Go to SHAPE"):
                           st.experimental_set_query_params(tab="SHAPE")
                       st.write("**Summary**")
                       st.write(data.get("summary", ""))
                       st.write("**Scores**")
                       st.json(data.get("scores", {}))
                       st.write("**Top Risks**")
                       st.write(data.get("top_risks", []))
                       st.write("**Must Fix**")
                       st.write(data.get("must_fix", []))

                except GroqError as e:
                    st.error(f"Groq error: {e}")

# --- SHAPE ---
with tab2:
    if disabled_tabs:
        st.info("Unlock by saving your details in the left panel.")
    else:
        st.subheader("SHAPE — Improve or Pivot")
        st.markdown(f"#### {_sub['shape']}")
        st.write("Original one-liner:")
        st.code(S["one_liner"] or "—")
        if not S["vet_json"]:
            st.info("Run VET first to enable SHAPE.")
        else:
            if st.button("Generate 2 improved variants"):
              try:
                messages = [
                    {"role": "system", "content": SHAPE_SYSTEM},
                    {"role": "user", "content": SHAPE_USER(S["one_liner"], json.dumps(S["vet_json"]))},
                ]
                out = groq_chat(messages, temperature=0.25, max_tokens=1000)
                data = extract_json_block(out)
                if not data:
                    st.warning("Could not parse JSON. Showing raw output:")
                    st.code(out)
                else:
                    S["shape_json"] = data
                    pdf_bytes = generate_vet_pdf(S["user"], S["shape_json"], logo_path=str(LOGO_PATH))
                    st.download_button("📄 Download SHAPE Report (PDF)", data=pdf_bytes, file_name="xq_shape_report.pdf", mime="application/pdf")
              except GroqError as e:
                st.error(f"Groq error: {e}")
        if not S["vet_json"]:
            st.info("Run VET first to enable SHAPE.")

        if S["shape_json"]:
            st.write("**Variants**")
            for i, v in enumerate(S["shape_json"].get("variants", []), start=1):
                st.markdown(f"**Variant {i}:** {v.get('one_liner','')}")
                st.caption(f"ICP: {v.get('who','')}")
                st.caption(f"Why now: {v.get('why_now','')}")
                st.caption(f"Pricing hint: {v.get('pricing_hint','')}")
                st.caption(f"GTM: {v.get('go_to_market','')}")
                st.write("Key changes:", v.get("key_changes", []))
                if st.button(f"Use Variant {i}"):
                    S["chosen_variant"] = v.get("one_liner","")
                    st.success(f"Chosen: {S['chosen_variant']}")

# --- SCOPE ---
with tab3:
    if disabled_tabs:
        st.info("Unlock by saving your details in the left panel.")
    else:
        st.subheader("SCOPE — MVP Plan (30 days)")
        st.markdown(f"#### {_sub['scope']}")
        base_one_liner = S["chosen_variant"] or S["one_liner"]
        constraints = st.text_input("Constraints (team size, capital, city/tier)", value=S["founder_ctx"])
        if st.button("Generate MVP scope"):
            try:
                messages = [
                    {"role": "system", "content": SCOPE_SYSTEM},
                    {"role": "user", "content": SCOPE_USER(base_one_liner, S["industry"], constraints)},
                ]
                out = groq_chat(messages, temperature=0.2, max_tokens=900)
                data = extract_json_block(out)
                if not data:
                    st.warning("Could not parse JSON. Showing raw output:")
                    st.code(out)
                else:
                    S["scope_json"] = data
                    pdf_bytes = generate_vet_pdf(S["user"], S["scope_json"], logo_path=str(LOGO_PATH))
                    st.download_button("📄 Download SCOPE Report (PDF)", data=pdf_bytes, file_name="xq_scope_report.pdf", mime="application/pdf")
            except GroqError as e:
                st.error(f"Groq error: {e}")

        if S.get("scope_json"):
            st.write("**Must build**")
            st.write(S["scope_json"].get("must_build", []))
            st.write("**Must NOT build**")
            st.write(S["scope_json"].get("must_not_build", []))
            st.write("**Launch channel**")
            st.write(S["scope_json"].get("one_launch_channel", ""))
            st.write("**Effort bucket**")
            st.write(S["scope_json"].get("effort_bucket", ""))
            st.write("**Quick validation (7 days)**")
            st.write(S["scope_json"].get("quick_validation", []))

# --- LAUNCH ---
with tab4:
    if disabled_tabs:
        st.info("Unlock by saving your details in the left panel.")
    else:
        st.subheader("LAUNCH — 30–60 Day Compass")
        st.markdown(f"#### {_sub['launch']}")
        icp_hint = st.text_input("ICP hint (optional, e.g., Tier-2 SME owners, delivery partners, etc.)", "")
        if st.button("Generate plan"):
            try:
                one = S["chosen_variant"] or S["one_liner"]
                messages = [
                    {"role": "system", "content": LAUNCH_SYSTEM},
                    {"role": "user", "content": LAUNCH_USER(one, icp_hint)},
                ]
                out = groq_chat(messages, temperature=0.25, max_tokens=1100)
                data = extract_json_block(out)
                if not data:
                    st.warning("Could not parse JSON. Showing raw output:")
                    st.code(out)
                else:
                    S["launch_json"] = data
                    pdf_bytes = generate_vet_pdf(S["user"], S["launch_json"], logo_path=str(LOGO_PATH))
                    st.download_button("📄 Download LAUNCH Plan (PDF)", data=pdf_bytes, file_name="xq_launch_plan.pdf", mime="application/pdf")
            except GroqError as e:
                st.error(f"Groq error: {e}")

        if S.get("launch_json"):
            st.write("**ICP summary**")
            st.write(S["launch_json"].get("icp_summary", []))
            st.write("**30-day plan**")
            st.write(S["launch_json"].get("30_day_plan", []))
            st.write("**60-day plan**")
            st.write(S["launch_json"].get("60_day_plan", []))
            st.write("**Deck outline**")
            st.write(S["launch_json"].get("deck_outline", []))
            st.write("**Funding path**")
            st.write(S["launch_json"].get("funding_path", ""))

st.divider()
st.caption(" XQ — Don’t build. Think. | Free 7-day trial. If it helps, please tell others")

# ---------------------------
# Admin Page (Hidden Access)
# ---------------------------
if "admin" in st.query_params and st.query_params["admin"] == "xq106":
    st.title("🛡️ Admin Panel – XQ Users")
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT name, email, phone, created_at, idea_count FROM users ORDER BY created_at DESC")
        rows = cur.fetchall()

    if rows:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["Name", "Email", "Phone", "Signup Time", "Ideas Submitted"])
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download User List (CSV)", data=csv, file_name="xq_users.csv", mime="text/csv")
    else:
        st.info("No users found.")
