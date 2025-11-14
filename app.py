import streamlit as st
import json
import requests
import base64
import uuid
from datetime import datetime, date, time, timedelta
import calendar
from typing import List, Dict, Any

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
        .mission-daily { border-left: 4px solid #4CAF50; padding-left: 10px; margin: 5px 0; }
        .mission-weekly { border-left: 4px solid #2196F3; padding-left: 10px; margin: 5px 0; }
        .mission-monthly { border-left: 4px solid #FF9800; padding-left: 10px; margin: 5px 0; }
        .mission-epic { border-left: 4px solid #9C27B0; padding-left: 10px; margin: 5px 0; }
        .calendar-day { border: 1px solid #e0e0e0; padding: 8px; min-height: 120px; }
        .calendar-today { background-color: #f0f8ff; border: 2px solid #000; }
        .mission-completed { text-decoration: line-through; color: #888; }
        .attribute-card { border: 1px solid #ddd; padding: 10px; margin: 5px 0; border-radius: 5px; }
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
    "created_date": date.today().isoformat(),
    "player_name": "",
    "player_bio": "",
    "player_goals": "",
    "player_motivation": "",
}

DEFAULT_CONFIG = {
    "xp_formula": "linear",
    "xp_base_per_level": 100,
    "calendar_start_week_on": "monday",
    "default_view": "month",
    "theme": "minimal",
    "language": "es",
    "notifications_enabled": True,
    "auto_save": True,
    "daily_reset_time": "06:00",
}

DEFAULT_ATTRIBUTES = {
    "attributes": [
        {"id": "strength", "name": "Fuerza", "current_xp": 0, "description": "Fuerza física y resistencia", "color": "#FF6B6B", "icon": "💪"},
        {"id": "intelligence", "name": "Inteligencia", "current_xp": 0, "description": "Capacidad mental y aprendizaje", "color": "#4ECDC4", "icon": "🧠"},
        {"id": "vitality", "name": "Vitalidad", "current_xp": 0, "description": "Energía y salud general", "color": "#45B7D1", "icon": "❤️"},
        {"id": "discipline", "name": "Disciplina", "current_xp": 0, "description": "Autocontrol y consistencia", "color": "#96CEB4", "icon": "⚡"},
        {"id": "creativity", "name": "Creatividad", "current_xp": 0, "description": "Pensamiento innovador y artístico", "color": "#FFEAA7", "icon": "🎨"},
        {"id": "social", "name": "Social", "current_xp": 0, "description": "Habilidades sociales y relaciones", "color": "#DDA0DD", "icon": "👥"},
        {"id": "wisdom", "name": "Sabiduría", "current_xp": 0, "description": "Experiencia y juicio", "color": "#98D8C8", "icon": "🦉"},
    ]
}

DEFAULT_MISSIONS = {
    "missions": [
        {
            "id": "m_daily_routine",
            "name": "Rutina Matutina",
            "description": "Meditación, ejercicio y planificación del día",
            "type": "daily",
            "base_xp": 15,
            "tokens_reward": 2,
            "attribute_id": "discipline",
            "start_date": date.today().isoformat(),
            "end_date": None,
            "recurrence": "everyday",
            "priority": "high"
        }
    ]
}

DEFAULT_CALENDAR = {"events": []}
DEFAULT_REWARDS = {
    "rewards": [
        {
            "id": "r_break",
            "name": "Descanso Premium - 30 min sin culpa",
            "description": "Tiempo de ocio totalmente justificado",
            "cost_tokens": 10,
            "category": "leisure"
        },
        {
            "id": "r_treat",
            "name": "Premio Especial",
            "description": "Algo que realmente disfrutes",
            "cost_tokens": 25,
            "category": "reward"
        }
    ],
    "redemptions": []
}

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
    if "current_date" not in st.session_state:
        st.session_state.current_date = date.today()
    if "calendar_view" not in st.session_state:
        st.session_state.calendar_view = "month"

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
#  LÓGICA DEL JUEGO
# =========================================================

def get_today_missions() -> List[Dict]:
    """Obtiene las misiones para el día actual"""
    today = st.session_state.current_date.isoformat()
    missions = st.session_state["missions"]["data"]["missions"]
    mission_log = st.session_state["mission_log"]["data"]
    
    today_missions = []
    
    for mission in missions:
        # Verificar si la misión está activa para hoy
        if is_mission_active_today(mission, st.session_state.current_date):
            # Verificar si ya fue completada hoy
            completed_today = any(
                log["mission_id"] == mission["id"] and 
                log["date"] == today and 
                log["status"] == "completed"
                for log in mission_log
            )
            
            mission_copy = mission.copy()
            mission_copy["completed"] = completed_today
            mission_copy["completion_data"] = next(
                (log for log in mission_log 
                 if log["mission_id"] == mission["id"] and log["date"] == today),
                None
            )
            today_missions.append(mission_copy)
    
    return today_missions

def is_mission_active_today(mission: Dict, target_date: date) -> bool:
    """Determina si una misión está activa para una fecha específica"""
    start_date = datetime.fromisoformat(mission.get("start_date", "2000-01-01")).date()
    end_date = datetime.fromisoformat(mission["end_date"]).date() if mission.get("end_date") else None
    
    if target_date < start_date:
        return False
    
    if end_date and target_date > end_date:
        return False
    
    mission_type = mission.get("type", "daily")
    recurrence = mission.get("recurrence", "everyday")
    
    if mission_type == "daily":
        if recurrence == "everyday":
            return True
        elif recurrence == "weekdays" and target_date.weekday() < 5:
            return True
        elif recurrence == "weekends" and target_date.weekday() >= 5:
            return True
    
    elif mission_type == "weekly":
        # Misiones semanales específicas
        if recurrence == "monday" and target_date.weekday() == 0:
            return True
        elif recurrence == "tuesday" and target_date.weekday() == 1:
            return True
        # ... otros días de la semana
    
    elif mission_type == "monthly":
        # Misiones mensuales (ej: día 1 de cada mes)
        if recurrence == "first_day" and target_date.day == 1:
            return True
    
    elif mission_type in ["epic", "one_off"]:
        # Misiones épicas o únicas - siempre activas dentro de su rango de fechas
        return True
    
    return False

def complete_mission(mission_id: str, notes: str = ""):
    """Completa una misión y otorga recompensas"""
    today = st.session_state.current_date.isoformat()
    mission = next(m for m in st.session_state["missions"]["data"]["missions"] if m["id"] == mission_id)
    
    log_entry = {
        "mission_id": mission_id,
        "date": today,
        "status": "completed",
        "xp_awarded": mission["base_xp"],
        "tokens_awarded": mission["tokens_reward"],
        "timestamp": datetime.now().isoformat(),
        "notes": notes,
    }
    
    # Agregar al log
    st.session_state["mission_log"]["data"].append(log_entry)
    
    # Actualizar perfil
    profile = st.session_state["profile"]["data"]
    profile["current_xp"] += mission["base_xp"]
    profile["total_tokens"] += mission["tokens_reward"]
    
    # Actualizar atributo si existe
    if mission.get("attribute_id"):
        attributes = st.session_state["attributes"]["data"]["attributes"]
        for attr in attributes:
            if attr["id"] == mission["attribute_id"]:
                attr["current_xp"] += mission["base_xp"]
                break
    
    # Verificar si subió de nivel
    check_level_up()

def check_level_up():
    """Verifica si el usuario subió de nivel"""
    profile = st.session_state["profile"]["data"]
    xp_needed = profile["xp_base_per_level"]
    
    while profile["current_xp"] >= xp_needed:
        profile["current_level"] += 1
        profile["current_xp"] -= xp_needed
        # Opcional: incrementar xp necesario para siguiente nivel
        # xp_needed = int(xp_needed * 1.2)

def get_mission_class(mission_type: str) -> str:
    """Devuelve la clase CSS para el tipo de misión"""
    type_classes = {
        "daily": "mission-daily",
        "weekly": "mission-weekly",
        "monthly": "mission-monthly",
        "epic": "mission-epic"
    }
    return type_classes.get(mission_type, "mission-daily")

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
    st.header("🏠 Dashboard")
    
    profile = st.session_state["profile"]["data"]
    level = profile["current_level"]
    xp = profile["current_xp"]
    base = profile["xp_base_per_level"]
    
    # Stats principales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Nivel", level)
    with col2:
        st.metric("XP", f"{xp}/{base}")
    with col3:
        st.metric("Tokens", profile["total_tokens"])
    with col4:
        st.metric("Racha", f"{profile['streak_days']} días")
    
    # Barra de progreso
    progress = min(xp / base, 1.0) if base > 0 else 0
    st.progress(progress)
    
    st.markdown("---")
    
    # Misiones de hoy
    st.subheader("🎯 Misiones de Hoy")
    today_missions = get_today_missions()
    
    if not today_missions:
        st.info("No tienes misiones para hoy. ¡Crea algunas en la pestaña de Misiones!")
    else:
        completed_count = sum(1 for m in today_missions if m.get("completed"))
        st.write(f"**Progreso: {completed_count}/{len(today_missions)} completadas**")
        
        for mission in today_missions:
            mission_class = get_mission_class(mission["type"])
            completed = mission.get("completed", False)
            
            col1, col2 = st.columns([3, 1])
            with col1:
                if completed:
                    st.markdown(f'<div class="{mission_class} mission-completed">✓ {mission["name"]}</div>', unsafe_allow_html=True)
                    st.caption(f"{mission['description']} - ✅ Completada")
                else:
                    st.markdown(f'<div class="{mission_class}">🎯 {mission["name"]}</div>', unsafe_allow_html=True)
                    st.caption(f"{mission['description']} - XP: {mission['base_xp']} | Tokens: {mission['tokens_reward']}")
            
            with col2:
                if not completed:
                    if st.button("Completar", key=f"complete_{mission['id']}"):
                        complete_mission(mission["id"])
                        st.rerun()
                else:
                    st.success("✅")
    
    # Atributos
    st.markdown("---")
    st.subheader("📊 Atributos")
    attributes = st.session_state["attributes"]["data"]["attributes"]
    
    cols = st.columns(len(attributes))
    for idx, attr in enumerate(attributes):
        with cols[idx]:
            st.write(f"**{attr['name']}**")
            st.write(f"XP: {attr['current_xp']}")
            st.caption(attr.get('description', ''))

# ---------- CALENDARIO AVANZADO ----------

def page_calendar():
    st.header("📅 Calendario Estratégico")
    
    # Controles de navegación
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀ Mes Anterior"):
            if st.session_state.calendar_view == "month":
                st.session_state.current_date = st.session_state.current_date.replace(day=1) - timedelta(days=1)
            else:
                st.session_state.current_date -= timedelta(days=7)
    with col2:
        view_option = st.radio("Vista", ["Mes", "Semana", "Día"], horizontal=True, key="view_selector")
        st.session_state.calendar_view = view_option.lower()
    with col3:
        if st.button("Mes Siguiente ▶"):
            if st.session_state.calendar_view == "month":
                next_month = st.session_state.current_date.replace(day=28) + timedelta(days=4)
                st.session_state.current_date = next_month.replace(day=1)
            else:
                st.session_state.current_date += timedelta(days=7)
    
    # Reset a hoy
    if st.button("Hoy"):
        st.session_state.current_date = date.today()
    
    st.write(f"**Vista: {st.session_state.current_date.strftime('%B %Y')}**")
    
    if st.session_state.calendar_view == "mes":
        render_month_view()
    elif st.session_state.calendar_view == "semana":
        render_week_view()
    else:
        render_day_view()

def render_month_view():
    """Renderiza vista mensual del calendario"""
    current_date = st.session_state.current_date
    year = current_date.year
    month = current_date.month
    
    # Obtener primer día del mes y número de días
    first_day = date(year, month, 1)
    last_day = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
    
    # Crear encabezados de días
    days = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    cols = st.columns(7)
    for i, day in enumerate(days):
        cols[i].write(f"**{day}**")
    
    # Crear calendario
    cal_rows = []
    current_row = [None] * 7
    
    # Rellenar días del mes anterior
    start_weekday = first_day.weekday()
    prev_month_last_day = first_day - timedelta(days=1)
    
    for i in range(start_weekday):
        prev_day = prev_month_last_day - timedelta(days=start_weekday - i - 1)
        current_row[i] = prev_day
    
    # Rellenar días del mes actual
    current_day = first_day
    while current_day <= last_day:
        current_row[start_weekday] = current_day
        start_weekday += 1
        
        if start_weekday == 7 or current_day == last_day:
            cal_rows.append(current_row.copy())
            current_row = [None] * 7
            start_weekday = 0
        
        current_day += timedelta(days=1)
    
    # Renderizar calendario
    for row in cal_rows:
        cols = st.columns(7)
        for i, day_date in enumerate(row):
            with cols[i]:
                if day_date:
                    is_today = day_date == date.today()
                    day_class = "calendar-day calendar-today" if is_today else "calendar-day"
                    
                    st.markdown(f'<div class="{day_class}">', unsafe_allow_html=True)
                    st.write(f"**{day_date.day}**")
                    
                    # Mostrar misiones y eventos para este día
                    render_day_content(day_date)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.write("")

def render_week_view():
    """Renderiza vista semanal"""
    current_date = st.session_state.current_date
    start_of_week = current_date - timedelta(days=current_date.weekday())
    
    st.write(f"**Semana del {start_of_week.strftime('%d %b')} al {(start_of_week + timedelta(days=6)).strftime('%d %b %Y')}**")
    
    cols = st.columns(7)
    for i in range(7):
        day_date = start_of_week + timedelta(days=i)
        with cols[i]:
            is_today = day_date == date.today()
            day_name = day_date.strftime('%a')
            
            if is_today:
                st.markdown(f"**🎯 {day_date.day} {day_name}**")
            else:
                st.markdown(f"**{day_date.day} {day_name}**")
            
            render_day_content(day_date, detailed=True)

def render_day_view():
    """Renderiza vista diaria detallada"""
    current_date = st.session_state.current_date
    is_today = current_date == date.today()
    
    st.subheader(f"📅 {current_date.strftime('%A, %d de %B de %Y')} {'(HOY)' if is_today else ''}")
    
    # Misiones del día
    st.write("### 🎯 Misiones del Día")
    today_missions = get_today_missions()
    
    if today_missions:
        for mission in today_missions:
            completed = mission.get("completed", False)
            status = "✅" if completed else "⏳"
            st.write(f"{status} **{mission['name']}**")
            st.caption(f"{mission['description']} | XP: {mission['base_xp']} | Tokens: {mission['tokens_reward']}")
            
            if not completed and st.button("Completar", key=f"day_view_{mission['id']}"):
                complete_mission(mission["id"])
                st.rerun()
    else:
        st.info("No hay misiones programadas para este día.")
    
    # Eventos del calendario
    st.write("### 🗓️ Eventos Programados")
    events = st.session_state["calendar"]["data"]["events"]
    day_events = [e for e in events if e["date"] == current_date.isoformat()]
    
    if day_events:
        for event in sorted(day_events, key=lambda x: x["start_time"]):
            st.write(f"🕒 **{event['start_time']} - {event['end_time']}**: {event['title']}")
            if event.get('notes'):
                st.caption(event['notes'])
    else:
        st.info("No hay eventos programados para este día.")
    
    # Agregar nuevo evento
    st.write("### ➕ Agregar Evento")
    with st.form("add_event_form"):
        title = st.text_input("Título del evento")
        event_date = st.date_input("Fecha", value=current_date)
        start_time = st.time_input("Hora inicio", value=time(8, 0))
        end_time = st.time_input("Hora fin", value=time(9, 0))
        notes = st.text_area("Notas")
        
        if st.form_submit_button("Agregar Evento"):
            new_event = {
                "id": f"ev_{uuid.uuid4().hex}",
                "title": title,
                "date": event_date.isoformat(),
                "start_time": start_time.strftime("%H:%M"),
                "end_time": end_time.strftime("%H:%M"),
                "notes": notes,
                "type": "event"
            }
            st.session_state["calendar"]["data"]["events"].append(new_event)
            st.success("Evento agregado!")
            st.rerun()

def render_day_content(day_date: date, detailed: bool = False):
    """Renderiza el contenido de un día en el calendario"""
    # Misiones para este día
    temp_date = st.session_state.current_date
    st.session_state.current_date = day_date
    day_missions = get_today_missions()
    st.session_state.current_date = temp_date
    
    # Eventos para este día
    events = st.session_state["calendar"]["data"]["events"]
    day_events = [e for e in events if e["date"] == day_date.isoformat()]
    
    # Mostrar resumen
    if day_missions:
        completed = sum(1 for m in day_missions if m.get("completed"))
        st.caption(f"🎯 {completed}/{len(day_missions)}")
    
    if day_events:
        st.caption(f"🗓️ {len(day_events)}")
    
    if detailed:
        for mission in day_missions[:3]:  # Mostrar máximo 3 misiones
            status = "✅" if mission.get("completed") else "⏳"
            st.write(f"{status} {mission['name'][:15]}...")
        
        for event in day_events[:2]:  # Mostrar máximo 2 eventos
            st.write(f"🗓️ {event['title'][:12]}...")

# ---------- MISIONES ----------

def page_missions():
    st.header("🎯 Sistema de Misiones")
    
    tab1, tab2, tab3 = st.tabs(["Todas las Misiones", "Crear Nueva Misión", "Misiones Épicas"])
    
    with tab1:
        missions = st.session_state["missions"]["data"]["missions"]
        
        if not missions:
            st.info("Aún no hay misiones. Crea tu primera misión!")
        else:
            for mission in missions:
                with st.expander(f"{mission['name']} ({mission['type']})"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Descripción:** {mission['description']}")
                        st.write(f"**XP:** {mission['base_xp']} | **Tokens:** {mission['tokens_reward']}")
                        st.write(f"**Fecha inicio:** {mission.get('start_date', 'N/A')}")
                        if mission.get('end_date'):
                            st.write(f"**Fecha fin:** {mission['end_date']}")
                        if mission.get('attribute_id'):
                            st.write(f"**Atributo:** {mission['attribute_id']}")
                    
                    with col2:
                        if st.button("Eliminar", key=f"del_{mission['id']}"):
                            st.session_state["missions"]["data"]["missions"] = [
                                m for m in missions if m["id"] != mission["id"]
                            ]
                            st.rerun()
    
    with tab2:
        st.subheader("Crear Nueva Misión")
        
        with st.form("create_mission"):
            name = st.text_input("Nombre de la misión *")
            description = st.text_area("Descripción")
            mission_type = st.selectbox("Tipo", ["daily", "weekly", "monthly", "epic", "one_off"])
            base_xp = st.number_input("XP base", 1, 1000, 10)
            tokens_reward = st.number_input("Tokens de recompensa", 0, 100, 2)
            
            # Atributos
            attributes = st.session_state["attributes"]["data"]["attributes"]
            attribute_id = st.selectbox(
                "Atributo relacionado", 
                [""] + [attr["id"] for attr in attributes]
            )
            
            # Fechas
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Fecha inicio", value=date.today())
            with col2:
                end_date = st.date_input("Fecha fin (opcional)", value=None)
            
            # Recurrencia según tipo
            if mission_type == "daily":
                recurrence = st.selectbox("Recurrencia", ["everyday", "weekdays", "weekends"])
            elif mission_type == "weekly":
                recurrence = st.selectbox("Día de la semana", [
                    "monday", "tuesday", "wednesday", "thursday", 
                    "friday", "saturday", "sunday"
                ])
            elif mission_type == "monthly":
                recurrence = st.selectbox("Tipo mensual", ["first_day", "last_day"])
            else:
                recurrence = "once"
            
            priority = st.selectbox("Prioridad", ["low", "medium", "high"])
            
            if st.form_submit_button("Crear Misión"):
                if not name.strip():
                    st.error("El nombre es obligatorio")
                else:
                    new_mission = {
                        "id": f"m_{uuid.uuid4().hex}",
                        "name": name.strip(),
                        "description": description,
                        "type": mission_type,
                        "base_xp": base_xp,
                        "tokens_reward": tokens_reward,
                        "attribute_id": attribute_id if attribute_id else None,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat() if end_date else None,
                        "recurrence": recurrence,
                        "priority": priority
                    }
                    st.session
