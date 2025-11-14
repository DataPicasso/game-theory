import streamlit as st
import json
import requests
import base64
import uuid
from datetime import datetime, date, time

# =========================================================
#  CONFIG GENERAL
# =========================================================

st.set_page_config(page_title="LifeGame Theory", layout="wide")

API_BASE = "https://api.github.com"

# =========================================================
#  CSS
# =========================================================

def inject_css():
    st.markdown("""
    <style>
    body { background-color: #FFF; }
    .stButton>button {
        border:1px solid #000;
        background:#FFF;
        color:#000;
        border-radius:4px;
        padding:0.4rem 1rem;
        transition:0.2s;
    }
    .stButton>button:hover {
        background:#000;
        color:#FFF;
    }
    input, textarea, select {
        border:1px solid #000 !important;
        border-radius:4px !important;
    }
    </style>
    """, unsafe_allow_html=True)

inject_css()

# =========================================================
#  GITHUB API UTILS
# =========================================================

def github_headers():
    return {
        "Authorization": f"Bearer {st.secrets['github']['token']}",
        "Accept": "application/vnd.github+json"
    }

def github_exists(path):
    """True si existe un archivo o carpeta en GitHub."""
    repo = st.secrets["github"]["repo"]
    url = f"{API_BASE}/repos/{repo}/contents/{path}"
    r = requests.get(url, headers=github_headers())
    return r.status_code == 200

def github_create_file(path, message="Init", content=""):
    """Crear archivo en GitHub (crea carpeta implícitamente)."""
    repo = st.secrets["github"]["repo"]
    url = f"{API_BASE}/repos/{repo}/contents/{path}"

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode()
    }

    r = requests.put(url, headers=github_headers(), json=payload)
    return r.status_code in [200, 201]

def ensure_data_structure(username):
    """Crea /data/ y /data/<username>/ y todos los archivos base si no existen."""

    # 1) /data/
    if not github_exists("data"):
        github_create_file("data/.keep", "Init data folder")

    # 2) /data/<user>/
    user_folder = f"data/{username}"
    if not github_exists(user_folder):
        github_create_file(f"{user_folder}/.keep", f"Init user folder {username}")

    # 3) Crear archivos base
    base_files = {
        "profile.json": DEFAULT_PROFILE,
        "config.json": DEFAULT_CONFIG,
        "attributes.json": DEFAULT_ATTRIBUTES,
        "missions.json": DEFAULT_MISSIONS,
        "calendar.json": DEFAULT_CALENDAR,
        "rewards.json": DEFAULT_REWARDS,
        "mission_log.jsonl": "",
        "journal.jsonl": "",
        "decisions.jsonl": ""
    }

    for fname, default in base_files.items():
        full = f"{user_folder}/{fname}"
        if not github_exists(full):
            if fname.endswith(".jsonl"):
                github_create_file(full, f"Init {fname}", "")
            else:
                github_create_file(full, f"Init {fname}", json.dumps(default, indent=2))

def github_get(user, filename):
    """Lee archivo del repo."""
    repo = st.secrets["github"]["repo"]
    url = f"{API_BASE}/repos/{repo}/contents/data/{user}/{filename}"

    r = requests.get(url, headers=github_headers())
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    return None, None

def github_put(user, filename, content_str, sha=None):
    """Sube archivo al repo."""
    repo = st.secrets["github"]["repo"]
    url = f"{API_BASE}/repos/{repo}/contents/data/{user}/{filename}"

    payload = {
        "message": f"Update {filename}",
        "content": base64.b64encode(content_str.encode()).decode(),
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=github_headers(), json=payload)
    return r.status_code in [200, 201]


# =========================================================
#  DEFAULT FILE DATA
# =========================================================

DEFAULT_PROFILE = {
    "current_level": 1,
    "current_xp": 0,
    "xp_base_per_level": 100,
    "total_tokens": 0,
    "streak_days": 0,
    "last_active_date": None
}

DEFAULT_CONFIG = {
    "xp_formula": "linear",
    "xp_base_per_level": 100,
    "calendar_start_week_on": "monday",
    "default_view": "month"
}

DEFAULT_ATTRIBUTES = {
    "attributes": [
        {"id": "strength", "name": "Fuerza", "current_xp": 0},
        {"id": "intelligence", "name": "Inteligencia", "current_xp": 0},
        {"id": "vitality", "name": "Vitalidad", "current_xp": 0}
    ]
}

DEFAULT_MISSIONS = {"missions": []}
DEFAULT_CALENDAR = {"events": []}
DEFAULT_REWARDS = {"rewards": [], "redemptions": []}

# =========================================================
#  SESSION STATE
# =========================================================

def init_session():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("username", None)

# =========================================================
#  LOAD & SAVE
# =========================================================

def load_all_user_data(username):
    files = {
        "profile.json": "profile",
        "config.json": "config",
        "attributes.json": "attributes",
        "missions.json": "missions",
        "calendar.json": "calendar",
        "rewards.json": "rewards",
        "mission_log.jsonl": "mission_log",
        "journal.jsonl": "journal",
        "decisions.jsonl": "decisions"
    }

    for fname, key in files.items():
        content, sha = github_get(username, fname)

        if fname.endswith(".jsonl"):
            if content:
                lines = [json.loads(line) for line in content.splitlines() if line.strip()]
            else:
                lines = []
            st.session_state[key] = {"data": lines, "sha": sha}
        else:
            if not content:
                # fallback si no existe
                if fname == "profile.json": data = DEFAULT_PROFILE
                elif fname == "config.json": data = DEFAULT_CONFIG
                elif fname == "attributes.json": data = DEFAULT_ATTRIBUTES
                elif fname == "missions.json": data = DEFAULT_MISSIONS
                elif fname == "calendar.json": data = DEFAULT_CALENDAR
                elif fname == "rewards.json": data = DEFAULT_REWARDS
            else:
                data = json.loads(content)

            st.session_state[key] = {"data": data, "sha": sha}

def save_json(user, key, filename):
    content = json.dumps(st.session_state[key]["data"], indent=2)
    sha = st.session_state[key]["sha"]
    github_put(user, filename, content, sha)

def save_jsonl(user, key, filename):
    lines = [json.dumps(item) for item in st.session_state[key]["data"]]
    content = "\n".join(lines)
    sha = st.session_state[key]["sha"]
    github_put(user, filename, content, sha)

def save_all_user_data(username):
    save_json(username, "profile", "profile.json")
    save_json(username, "config", "config.json")
    save_json(username, "attributes", "attributes.json")
    save_json(username, "missions", "missions.json")
    save_json(username, "calendar", "calendar.json")
    save_json(username, "rewards", "rewards.json")
    save_jsonl(username, "mission_log", "mission_log.jsonl")
    save_jsonl(username, "journal", "journal.jsonl")
    save_jsonl(username, "decisions", "decisions.jsonl")

# =========================================================
#  AUTH
# =========================================================

def get_valid_users():
    if "auth" not in st.secrets:
        return {"demo": "demo"}
    return {k: str(st.secrets["auth"][k]) for k in st.secrets["auth"]}

def login_screen():
    st.title("LifeGame Theory")
    st.subheader("Acceso")

    users = get_valid_users()
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):
        if username in users and users[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username

            ensure_data_structure(username)
            load_all_user_data(username)

            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

# =========================================================
# PAGES (Dashboard, Calendar, Missions, etc.)
# =========================================================
# --- YOUR EXISTING PAGES: unchanged ---
# --- (I will keep them exactly as you provided) ---

# =========================================================
#  ROUTING
# =========================================================

init_session()

if not st.session_state.authenticated:
    login_screen()
    st.stop()

username = st.session_state.username

menu = st.sidebar.radio("Menú", [
    "Dashboard",
    "Calendario",
    "Misiones",
    "Registro diario",
    "Decisiones",
    "Recompensas",
    "Configuración"
])

if menu == "Dashboard":
    page_dashboard()
elif menu == "Calendario":
    page_calendar()
elif menu == "Misiones":
    page_missions()
elif menu == "Registro diario":
    page_journal()
elif menu == "Decisiones":
    page_decisions()
elif menu == "Recompensas":
    page_rewards()
elif menu == "Configuración":
    page_config()
