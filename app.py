import streamlit as st
import json
import requests
import base64
import uuid
from datetime import datetime, date, time

# =========================================================
#  CONFIGURACIÓN GENERAL
# =========================================================

st.set_page_config(
    page_title="LifeGame Theory",
    layout="wide"
)

API_BASE = "https://api.github.com"

# =========================================================
#  CSS MINIMALISTA
# =========================================================

def inject_css():
    """CSS minimalista blanco/negro"""
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True,
    )

inject_css()

# =========================================================
#  GITHUB HELPERS (UN SOLO REPO)
# =========================================================

def github_headers():
    return {
        "Authorization": f"Bearer {st.secrets['github']['token']}",
        "Accept": "application/vnd.github+json",
    }

def github_repo():
    return st.secrets["github"]["repo"]

def github_exists(path: str) -> bool:
    """
    Verifica si un archivo o carpeta existe en el repo.
    path es relativo al root del repo, ej: 'data', 'data/leo/profile.json'
    """
    url = f"{API_BASE}/repos/{github_repo()}/contents/{path}"
    r = requests.get(url, headers=github_headers())
    return r.status_code == 200

def github_create_file(path: str, message: str, content: str = "") -> bool:
    """
    Crea un archivo en el repo (crea carpetas implícitamente).
    """
    url = f"{API_BASE}/repos/{github_repo()}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": "main",
    }
    r = requests.put(url, headers=github_headers(), json=payload)
    return r.status_code in (200, 201)

def github_get(user: str, filename: str):
    """
    Lee archivo desde GitHub, dentro de data/<user>/<filename>.
    Devuelve (content_str, sha) o (None, None) si no existe.
    """
    path = f"data/{user}/{filename}"
    url = f"{API_BASE}/repos/{github_repo()}/contents/{path}"
    r = requests.get(url, headers=github_headers())
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        sha = data.get("sha")
        return content, sha
    return None, None

def github_put(user: str, filename: str, content_str: str, sha: str | None):
    """
    Escribe archivo en GitHub (update o create).
    Devuelve nueva SHA o None si falla.
    """
    path = f"data/{user}/{filename}"
    url = f"{API_BASE}/repos/{github_repo()}/contents/{path}"

    payload = {
        "message": f"Update {filename}",
        "content": base64.b64encode(content_str.encode()).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=github_headers(), json=payload)
    if r.status_code in (200, 201):
        body = r.json()
        new_sha = body["content"]["sha"]
        return new_sha
    else:
        st.error(f"Error al subir {filename}: {r.status_code} - {r.text}")
        return None

# =========================================================
#  DATOS POR DEFECTO
# =========================================================

DEFAULT_PROFILE = {
    "current_level": 1,
    "current_xp": 0,
    "xp_base_per_level": 100,
    "total_tokens": 0,
    "streak_days": 0,
    "last_active_date": None,
}

DEFAULT_CONFIG = {
    "xp_formula": "linear",
    "xp_base_per_level": 100,
    "calendar_start_week_on": "monday",
    "default_view": "month",
}

DEFAULT_ATTRIBUTES = {
    "attributes": [
        {"id": "strength", "name": "Fuerza", "current_xp": 0},
        {"id": "intelligence", "name": "Inteligencia", "current_xp": 0},
        {"id": "vitality", "name": "Vitalidad", "current_xp": 0},
    ]
}

DEFAULT_MISSIONS = {"missions": []}
DEFAULT_CALENDAR = {"events": []}
DEFAULT_REWARDS = {"rewards": [], "redemptions": []}

# =========================================================
#  CREACIÓN AUTOMÁTICA DE /data Y DATA DEL USUARIO
# =========================================================

def ensure_data_structure(username: str):
    """
    Crea en GitHub:
      - /data/
      - /data/<username>/
      - archivos JSON y JSONL base
    si no existen.
    """

    # 1) carpeta /data/
    if not github_exists("data"):
        github_create_file("data/.keep", "Init data folder", "")

    # 2) carpeta /data/<username>/
    user_folder = f"data/{username}"
    if not github_exists(user_folder):
        github_create_file(f"{user_folder}/.keep", f"Init folder for {username}", "")

    # 3) archivos base
    base_files = {
        "profile.json": json.dumps(DEFAULT_PROFILE, indent=2),
        "config.json": json.dumps(DEFAULT_CONFIG, indent=2),
        "attributes.json": json.dumps(DEFAULT_ATTRIBUTES, indent=2),
        "missions.json": json.dumps(DEFAULT_MISSIONS, indent=2),
        "calendar.json": json.dumps(DEFAULT_CALENDAR, indent=2),
        "rewards.json": json.dumps(DEFAULT_REWARDS, indent=2),
        "mission_log.jsonl": "",
        "journal.jsonl": "",
        "decisions.jsonl": "",
    }

    for fname, content in base_files.items():
        path = f"data/{username}/{fname}"
        if not github_exists(path):
            github_create_file(path, f"Init {fname} for {username}", content)

# =========================================================
#  SESSION STATE
# =========================================================

def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = None

# =========================================================
#  LOAD & SAVE DATA
# =========================================================

def load_all_user_data(username: str):
    """Carga todos los archivos JSON y JSONL del usuario."""

    files = {
        "profile.json": "profile",
        "config.json": "config",
        "attributes.json": "attributes",
        "missions.json": "missions",
        "calendar.json": "calendar",
        "rewards.json": "rewards",
        "mission_log.jsonl": "mission_log",
        "journal.jsonl": "journal",
        "decisions.jsonl": "decisions",
    }

    for fname, key in files.items():
        content, sha = github_get(username, fname)

        if fname.endswith(".jsonl"):
            if content:
                data_list = [
                    json.loads(line) for line in content.splitlines() if line.strip()
                ]
            else:
                data_list = []
            st.session_state[key] = {"data": data_list, "sha": sha}
        else:
            if content:
                data = json.loads(content)
            else:
                # fallback (no debería pasar, porque ensure_data_structure ya los crea)
                if fname == "profile.json":
                    data = DEFAULT_PROFILE
                elif fname == "config.json":
                    data = DEFAULT_CONFIG
                elif fname == "attributes.json":
                    data = DEFAULT_ATTRIBUTES
                elif fname == "missions.json":
                    data = DEFAULT_MISSIONS
                elif fname == "calendar.json":
                    data = DEFAULT_CALENDAR
                elif fname == "rewards.json":
                    data = DEFAULT_REWARDS
            st.session_state[key] = {"data": data, "sha": sha}

def save_json(user: str, key: str, filename: str):
    content = json.dumps(st.session_state[key]["data"], indent=2)
    old_sha = st.session_state[key]["sha"]
    new_sha = github_put(user, filename, content, old_sha)
    if new_sha:
        st.session_state[key]["sha"] = new_sha

def save_jsonl(user: str, key: str, filename: str):
    lines = [json.dumps(item) for item in st.session_state[key]["data"]]
    content = "\n".join(lines)
    old_sha = st.session_state[key]["sha"]
    new_sha = github_put(user, filename, content, old_sha)
    if new_sha:
        st.session_state[key]["sha"] = new_sha

def save_all_user_data(username: str):
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
#  AUTENTICACIÓN
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

            # crear /data y archivos base si no existen
            ensure_data_structure(username)
            # cargar todo a memoria
            load_all_user_data(username)

            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

# =========================================================
#  PÁGINAS
# =========================================================

# ---------- DASHBOARD ----------

def page_dashboard():
    st.header("Dashboard")

    profile = st.session_state["profile"]["data"]
    level = profile["current_level"]
    xp = profile["current_xp"]
    base = profile["xp_base_per_level"]

    st.subheader(f"Nivel {level}")
    progress = min(xp / base, 1.0) if base > 0 else 0
    st.progress(progress)

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"XP: {xp} / {base}")
    with col2:
        st.write(f"Tokens: {profile['total_tokens']}")

    st.markdown("---")
    st.subheader("Misiones de hoy")

    today = date.today().isoformat()
    missions = st.session_state["missions"]["data"]["missions"]

    today_missions = []
    for m in missions:
        if m["type"] == "daily":
            today_missions.append(m)
        elif m["type"] == "weekly":
            # aquí podrías implementar lógica de días concretos
            pass

    if not today_missions:
        st.info("No tienes misiones diarias configuradas.")
    else:
        for m in today_missions:
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{m['name']} (XP {m['base_xp']}, Tokens {m['tokens_reward']})")
            with cols[1]:
                if st.button("Completar", key=f"complete_today_{m['id']}"):
                    log = {
                        "mission_id": m["id"],
                        "date": today,
                        "status": "completed",
                        "xp_awarded": m["base_xp"],
                        "tokens_awarded": m["tokens_reward"],
                        "timestamp": datetime.now().isoformat(),
                        "notes": "",
                    }
                    st.session_state["mission_log"]["data"].append(log)
                    profile["current_xp"] += m["base_xp"]
                    profile["total_tokens"] += m["tokens_reward"]
                    st.success("Misión completada.")
                    st.rerun()

# ---------- CALENDARIO ----------

def page_calendar():
    st.header("Calendario")

    events = st.session_state["calendar"]["data"]["events"]

    st.subheader("Eventos existentes")
    if not events:
        st.info("Todavía no hay eventos en el calendario.")
    else:
        for ev in sorted(events, key=lambda e: (e["date"], e["start_time"])):
            st.write(f"{ev['date']} {ev['start_time']}-{ev['end_time']} — {ev['title']}")

    st.markdown("---")
    st.subheader("Añadir evento")

    title = st.text_input("Título")
    d = st.date_input("Fecha", value=date.today())
    start_t = st.time_input("Hora inicio", value=time(8, 0))
    end_t = st.time_input("Hora fin", value=time(9, 0))
    notes = st.text_area("Notas")

    if st.button("Crear evento"):
        new = {
            "id": f"ev_{uuid.uuid4().hex}",
            "type": "generic",
            "date": d.isoformat(),
            "start_time": start_t.strftime("%H:%M"),
            "end_time": end_t.strftime("%H:%M"),
            "title": title,
            "notes": notes,
        }
        events.append(new)
        st.success("Evento creado.")
        st.rerun()

# ---------- MISIONES ----------

def page_missions():
    st.header("Misiones")

    missions = st.session_state["missions"]["data"]["missions"]

    st.subheader("Lista de misiones")
    if not missions:
        st.info("Aún no hay misiones. Crea alguna abajo.")
    else:
        for m in missions:
            st.write(
                f"- {m['name']} ({m['type']}) — XP {m['base_xp']} / Tokens {m['tokens_reward']}"
            )

    st.markdown("---")
    st.subheader("Crear nueva misión")

    name = st.text_input("Nombre de la misión")
    desc = st.text_area("Descripción")
    mtype = st.selectbox("Tipo", ["daily", "weekly", "one_off"])
    xp = st.number_input("XP otorgados", 1, 1000, 10)
    tokens = st.number_input("Tokens otorgados", 0, 1000, 0)

    if st.button("Crear misión"):
        if not name.strip():
            st.error("La misión debe tener un nombre.")
        else:
            mid = f"m_{uuid.uuid4().hex}"
            missions.append(
                {
                    "id": mid,
                    "name": name.strip(),
                    "description": desc,
                    "type": mtype,
                    "base_xp": xp,
                    "tokens_reward": tokens,
                }
            )
            st.success("Misión creada.")
            st.rerun()

# ---------- JOURNAL ----------

def page_journal():
    st.header("Registro diario")

    attrs = st.session_state["attributes"]["data"]["attributes"]

    entry = st.text_area("Escribe tu registro del día:")
    attr_ids = st.multiselect(
        "Atributos relacionados", [a["id"] for a in attrs]
    )
    xp = st.number_input("XP a otorgar (manual)", 0, 200, 10)

    if st.button("Guardar registro"):
        log = {
            "id": f"j_{uuid.uuid4().hex}",
            "date": date.today().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "text": entry,
            "attribute_ids": attr_ids,
            "xp_awarded": xp,
        }
        st.session_state["journal"]["data"].append(log)
        st.success("Registro guardado.")

    st.markdown("---")
    st.subheader("Historial")

    logs = sorted(
        st.session_state["journal"]["data"],
        key=lambda x: x["timestamp"],
        reverse=True,
    )
    if not logs:
        st.info("Todavía no tienes registros.")
    else:
        for l in logs[:50]:
            st.write(f"{l['date']} — {l['text']}")

# ---------- GAME THEORY LAB ----------

def page_decisions():
    st.header("Game Theory Lab")

    st.subheader("Evaluar una decisión")

    situation = st.text_input("Describe la situación")
    opt1 = st.text_input("Opción A")
    opt2 = st.text_input("Opción B")

    shortA = st.slider("Payoff corto plazo A", 1, 10, 5)
    longA = st.slider("Payoff largo plazo A", 1, 10, 5)

    shortB = st.slider("Payoff corto plazo B", 1, 10, 5)
    longB = st.slider("Payoff largo plazo B", 1, 10, 5)

    if st.button("Registrar decisión"):
        entry = {
            "id": f"d_{uuid.uuid4().hex}",
            "timestamp": datetime.now().isoformat(),
            "situation": situation,
            "options": [
                {
                    "name": opt1,
                    "short_term_payoff": shortA,
                    "long_term_payoff": longA,
                },
                {
                    "name": opt2,
                    "short_term_payoff": shortB,
                    "long_term_payoff": longB,
                },
            ],
            "chosen_option": None,
            "reason": None,
            "regret_check": None,
        }
        st.session_state["decisions"]["data"].append(entry)
        st.success("Decisión registrada.")

    st.markdown("---")
    st.subheader("Historial de decisiones")

    decs = sorted(
        st.session_state["decisions"]["data"],
        key=lambda x: x["timestamp"],
        reverse=True,
    )
    if not decs:
        st.info("Sin decisiones registradas aún.")
    else:
        for d in decs[:50]:
            st.write(f"{d['timestamp']} — {d['situation']}")

# ---------- RECOMPENSAS ----------

def page_rewards():
    st.header("Recompensas")

    rewards = st.session_state["rewards"]["data"]["rewards"]
    redemptions = st.session_state["rewards"]["data"]["redemptions"]
    profile = st.session_state["profile"]["data"]

    st.subheader("Tienda")

    if not rewards:
        st.info("Todavía no hay recompensas definidas.")
    else:
        for r in rewards:
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"{r['name']} — Costo: {r['cost_tokens']} tokens")
            with cols[1]:
                if profile["total_tokens"] >= r["cost_tokens"]:
                    if st.button("Canjear", key=f"redeem_{r['id']}"):
                        profile["total_tokens"] -= r["cost_tokens"]
                        redemptions.append(
                            {
                                "id": f"red_{uuid.uuid4().hex}",
                                "reward_id": r["id"],
                                "date": date.today().isoformat(),
                                "tokens_spent": r["cost_tokens"],
                            }
                        )
                        st.success("Recompensa canjeada.")
                        st.rerun()
                else:
                    st.write("Sin tokens suficientes.")

    st.markdown("---")
    st.subheader("Crear recompensa")

    rname = st.text_input("Nombre de la recompensa")
    cost = st.number_input("Costo en tokens", 0, 1000, 0)

    if st.button("Crear recompensa"):
        if not rname.strip():
            st.error("La recompensa debe tener nombre.")
        else:
            rid = f"r_{uuid.uuid4().hex}"
            rewards.append({"id": rid, "name": rname.strip(), "cost_tokens": cost})
            st.success("Recompensa creada.")
            st.rerun()

# ---------- CONFIGURACIÓN ----------

def page_config():
    st.header("Configuración")

    cfg = st.session_state["config"]["data"]

    st.subheader("Parámetros de XP")
    new_base = st.number_input(
        "XP base para subir de nivel",
        10,
        10000,
        cfg.get("xp_base_per_level", 100),
    )
    if st.button("Guardar configuración"):
        cfg["xp_base_per_level"] = new_base
        st.success("Configuración actualizada.")

    st.markdown("---")
    st.subheader("Persistencia en GitHub")

    if st.button("Guardar TODOS los datos en GitHub"):
        save_all_user_data(st.session_state.username)
        st.success("Datos guardados.")

    if st.button("Recargar datos desde GitHub"):
        load_all_user_data(st.session_state.username)
        st.success("Datos recargados.")

# =========================================================
#  ROUTING
# =========================================================

init_session()

if not st.session_state.authenticated:
    login_screen()
    st.stop()

username = st.session_state.username

st.sidebar.title("LifeGame Theory")
st.sidebar.write(f"Usuario: {username}")

menu = st.sidebar.radio(
    "Menú",
    [
        "Dashboard",
        "Calendario",
        "Misiones",
        "Registro diario",
        "Decisiones",
        "Recompensas",
        "Configuración",
    ],
)

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
