import streamlit as st
import math
from datetime import date, datetime
import requests
import base64
import json

# =========================
#   CONFIG INICIAL APP
# =========================

st.set_page_config(
    page_title="LifeRPG",
    page_icon="🎮",
    layout="wide"
)

# =========================
#   AUTH & GITHUB HELPERS
# =========================

def get_valid_users():
    # Usuarios definidos en secrets.toml, sección [auth]
    try:
        return dict(st.secrets["auth"])
    except Exception:
        # Fallback por si no tienes secrets bien puestos
        return {"demo": "demo"}

def github_config():
    try:
        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
        return token, repo
    except Exception:
        st.error("No se pudo leer configuración de GitHub desde secrets.toml")
        return None, None

def github_file_url(username: str):
    token, repo = github_config()
    if not token or not repo:
        return None, None, None
    api_url = f"https://api.github.com/repos/{repo}/contents/data/{username}.json"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    return api_url, headers, token

def export_state():
    """Convierte st.session_state de juego en un dict serializable."""
    return {
        "player_name": st.session_state.player_name,
        "level": st.session_state.level,
        "xp": st.session_state.xp,
        "base_xp_per_level": st.session_state.base_xp_per_level,
        "attributes": st.session_state.attributes,
        "quests": st.session_state.quests,
        "logs": [
            {
                "timestamp": log["timestamp"].isoformat(),
                "description": log["description"],
                "attribute": log["attribute"],
                "xp": log["xp"],
                "source": log["source"],
            }
            for log in st.session_state.logs
        ],
        "completed_today": {
            k: list(v) for k, v in st.session_state.completed_today.items()
        },
    }

def import_state(data: dict):
    """Carga los datos guardados en st.session_state."""
    st.session_state.player_name = data.get("player_name", "Héroe sin nombre")
    st.session_state.level = data.get("level", 1)
    st.session_state.xp = data.get("xp", 0)
    st.session_state.base_xp_per_level = data.get("base_xp_per_level", 100)
    st.session_state.attributes = data.get("attributes", {
        "Fuerza 💪": 0,
        "Inteligencia 📚": 0,
        "Carisma 😎": 0,
        "Vitalidad ❤️": 0,
    })
    st.session_state.quests = data.get("quests", [])
    # logs: reconstruir timestamps
    raw_logs = data.get("logs", [])
    logs = []
    for log in raw_logs:
        try:
            ts = datetime.fromisoformat(log["timestamp"])
        except Exception:
            ts = datetime.now()
        logs.append(
            {
                "timestamp": ts,
                "description": log.get("description", ""),
                "attribute": log.get("attribute", ""),
                "xp": log.get("xp", 0),
                "source": log.get("source", ""),
            }
        )
    st.session_state.logs = logs

    # completed_today
    st.session_state.completed_today = {
        k: set(v_list) for k, v_list in data.get("completed_today", {}).items()
    }

def load_state_from_github(username: str):
    api_url, headers, _ = github_file_url(username)
    if not api_url:
        return

    resp = requests.get(api_url, headers=headers)
    if resp.status_code == 200:
        body = resp.json()
        content_b64 = body["content"]
        decoded = base64.b64decode(content_b64).decode("utf-8")
        data = json.loads(decoded)
        import_state(data)
        st.session_state.github_sha = body["sha"]
        st.success("Datos cargados desde GitHub ✅")
    elif resp.status_code == 404:
        st.info("No se encontraron datos en GitHub para este usuario. Empezarás desde cero.")
        st.session_state.github_sha = None
    else:
        st.error(f"No se pudo cargar desde GitHub (status {resp.status_code})")

def save_state_to_github(username: str):
    api_url, headers, _ = github_file_url(username)
    if not api_url:
        return

    data = export_state()
    content_str = json.dumps(data, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"Update LifeRPG data for {username}",
        "content": content_b64,
    }
    if st.session_state.get("github_sha"):
        payload["sha"] = st.session_state.github_sha

    resp = requests.put(api_url, headers=headers, data=json.dumps(payload))
    if resp.status_code in (200, 201):
        body = resp.json()
        st.session_state.github_sha = body["content"]["sha"]
        st.success("Datos guardados en GitHub ✅")
    else:
        st.error(f"No se pudo guardar en GitHub (status {resp.status_code})")


# =========================
#   ESTADO INICIAL DE JUEGO
# =========================

def init_game_state():
    if "player_name" not in st.session_state:
        st.session_state.player_name = "Héroe sin nombre"
    if "level" not in st.session_state:
        st.session_state.level = 1
    if "xp" not in st.session_state:
        st.session_state.xp = 0
    if "base_xp_per_level" not in st.session_state:
        st.session_state.base_xp_per_level = 100
    if "attributes" not in st.session_state:
        st.session_state.attributes = {
            "Fuerza 💪": 0,
            "Inteligencia 📚": 0,
            "Carisma 😎": 0,
            "Vitalidad ❤️": 0,
        }
    if "quests" not in st.session_state:
        st.session_state.quests = []
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "completed_today" not in st.session_state:
        st.session_state.completed_today = {}
    if "github_sha" not in st.session_state:
        st.session_state.github_sha = None

def init_auth_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = None

init_auth_state()

# =========================
#   LOGIN
# =========================

def login_view():
    st.title("🔐 LifeRPG - Login")
    st.write("Inicia sesión para cargar tus datos desde GitHub.")

    users = get_valid_users()

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")

    if submit:
        if username in users and users[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.success(f"Bienvenido, {username} 👋")
            # Inicializar juego y cargar datos del usuario
            init_game_state()
            load_state_from_github(username)
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    st.info("Si estás en modo demo, prueba usuario: `demo`, contraseña: `demo`")

# =========================
#   FUNCIONES DEL JUEGO
# =========================

def xp_needed_for_next_level(level: int) -> int:
    return st.session_state.base_xp_per_level * level

def add_xp(amount: int):
    st.session_state.xp += amount
    while st.session_state.xp >= xp_needed_for_next_level(st.session_state.level):
        st.session_state.xp -= xp_needed_for_next_level(st.session_state.level)
        st.session_state.level += 1
        st.success(f"🎉 ¡Subiste a nivel {st.session_state.level}!")

def add_attribute_xp(attribute_name: str, amount: int):
    if attribute_name in st.session_state.attributes:
        st.session_state.attributes[attribute_name] += amount

def log_action(description: str, attribute: str, xp_amount: int, source: str):
    st.session_state.logs.append(
        {
            "timestamp": datetime.now(),
            "description": description,
            "attribute": attribute,
            "xp": xp_amount,
            "source": source,
        }
    )

def mark_quest_completed(quest_id: int):
    today_str = date.today().isoformat()
    if today_str not in st.session_state.completed_today:
        st.session_state.completed_today[today_str] = set()
    st.session_state.completed_today[today_str].add(quest_id)

def is_quest_completed_today(quest_id: int) -> bool:
    today_str = date.today().isoformat()
    return (
        today_str in st.session_state.completed_today and
        quest_id in st.session_state.completed_today[today_str]
    )

# =========================
#   SI NO LOGIN → PANTALLA LOGIN
# =========================

if not st.session_state.authenticated:
    login_view()
    st.stop()

# Usuario autenticado → inicializar juego si hace falta
init_game_state()

# =========================
#   SIDEBAR NAVEGACIÓN
# =========================

st.sidebar.title("🎮 LifeRPG")
st.sidebar.caption(f"Usuario: **{st.session_state.username}**")

page = st.sidebar.radio(
    "Navegación",
    ["Dashboard", "Misiones & Hábitos", "Registro del día", "Configuración"]
)

st.sidebar.markdown("---")
st.sidebar.write(f"👤 **{st.session_state.player_name}**")
st.sidebar.write(f"⭐ Nivel: **{st.session_state.level}**")

if st.sidebar.button("💾 Guardar en GitHub"):
    save_state_to_github(st.session_state.username)

if st.sidebar.button("🔄 Cargar desde GitHub"):
    load_state_from_github(st.session_state.username)
    st.experimental_rerun()

if st.sidebar.button("🚪 Cerrar sesión"):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.experimental_rerun()

# =========================
#   PANTALLA: DASHBOARD
# =========================

if page == "Dashboard":
    st.title("🏠 Dashboard / HUD")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"👤 {st.session_state.player_name}")
        current_level = st.session_state.level
        xp_current = st.session_state.xp
        xp_needed = xp_needed_for_next_level(current_level)
        st.write(f"Nivel actual: **{current_level}**")
        st.write(f"XP: **{xp_current}/{xp_needed}**")
        progress = xp_current / xp_needed if xp_needed > 0 else 0
        st.progress(progress)

    with col2:
        st.subheader("📅 Hoy")
        today = date.today().strftime("%d/%m/%Y")
        st.write(f"Fecha: **{today}**")
        today_key = date.today().isoformat()
        completed_today = len(st.session_state.completed_today.get(today_key, []))
        st.metric("Misiones completadas hoy", completed_today)

    st.markdown("---")
    st.subheader("📊 Atributos del personaje")

    cols = st.columns(2)
    items = list(st.session_state.attributes.items())
    for i, (attr_name, value) in enumerate(items):
        with cols[i % 2]:
            st.metric(attr_name, value)

    st.markdown("---")
    st.subheader("📝 Actividad reciente")

    recent_logs = sorted(st.session_state.logs, key=lambda x: x["timestamp"], reverse=True)[:10]
    if not recent_logs:
        st.info("Aún no hay actividades registradas. ¡Completa misiones o registra acciones!")
    else:
        for log in recent_logs:
            ts = log["timestamp"].strftime("%d/%m %H:%M")
            st.write(
                f"- `{ts}` → **{log['description']}** (+{log['xp']} XP en {log['attribute']}) "
                f"_({log['source']})_"
            )

# =========================
#   PANTALLA: MISIONES
# =========================

elif page == "Misiones & Hábitos":
    st.title("🗺️ Misiones & Hábitos")

    st.subheader("Crear nueva misión")
    with st.form("new_quest_form"):
        q_name = st.text_input("Nombre de la misión", placeholder="Ej: Leer 20 minutos")
        q_type = st.selectbox("Tipo de misión", ["Diaria", "Semanal", "Épica"])
        q_attribute = st.selectbox("Atributo principal", list(st.session_state.attributes.keys()))
        q_xp = st.number_input("XP otorgada al completarla", min_value=1, max_value=1000, value=10)
        submitted = st.form_submit_button("➕ Añadir misión")

        if submitted:
            if not q_name.strip():
                st.error("La misión debe tener un nombre.")
            else:
                st.session_state.quests.append(
                    {
                        "name": q_name.strip(),
                        "type": q_type,
                        "attribute": q_attribute,
                        "xp": int(q_xp),
                    }
                )
                st.success("✅ Misión creada.")

    st.markdown("---")
    st.subheader("Lista de misiones")

    if not st.session_state.quests:
        st.info("No tienes misiones aún. Crea alguna en el formulario de arriba.")
    else:
        for idx, quest in enumerate(st.session_state.quests):
            completed = is_quest_completed_today(idx)
            cols = st.columns([4, 2, 2, 2])
            with cols[0]:
                st.write(f"**{quest['name']}**")
                st.caption(f"Tipo: {quest['type']}")
            with cols[1]:
                st.write(f"Atributo: {quest['attribute']}")
            with cols[2]:
                st.write(f"Recompensa: 🌟 {quest['xp']} XP")
            with cols[3]:
                if completed:
                    st.success("Completada hoy")
                else:
                    if st.button("✔️ Completar", key=f"complete_{idx}"):
                        add_xp(quest["xp"])
                        add_attribute_xp(quest["attribute"], quest["xp"])
                        mark_quest_completed(idx)
                        log_action(
                            description=f"Completó misión: {quest['name']}",
                            attribute=quest["attribute"],
                            xp_amount=quest["xp"],
                            source="Misión"
                        )
                        st.experimental_rerun()

# =========================
#   PANTALLA: REGISTRO DEL DÍA
# =========================

elif page == "Registro del día":
    st.title("📓 Registro del día / Journal")

    st.subheader("Registrar una acción")

    with st.form("log_action_form"):
        desc = st.text_input("¿Qué hiciste?", placeholder="Ej: Corrí 3 km")
        attr = st.selectbox("Atributo afectado", list(st.session_state.attributes.keys()))
        xp_amount = st.number_input("XP a otorgar", min_value=1, max_value=500, value=10)
        submitted = st.form_submit_button("💾 Registrar acción")

        if submitted:
            if not desc.strip():
                st.error("La descripción no puede estar vacía.")
            else:
                add_xp(int(xp_amount))
                add_attribute_xp(attr, int(xp_amount))
                log_action(
                    description=desc.strip(),
                    attribute=attr,
                    xp_amount=int(xp_amount),
                    source="Registro manual"
                )
                st.success("✅ Acción registrada.")

    st.markdown("---")
    st.subheader("Historial reciente")

    if not st.session_state.logs:
        st.info("Todavía no tienes registros.")
    else:
        recent_logs = sorted(st.session_state.logs, key=lambda x: x["timestamp"], reverse=True)[:20]
        for log in recent_logs:
            ts = log["timestamp"].strftime("%d/%m %H:%M")
            st.write(
                f"- `{ts}` → **{log['description']}** (+{log['xp']} XP en {log['attribute']}) "
                f"_({log['source']})_"
            )

# =========================
#   PANTALLA: CONFIGURACIÓN
# =========================

elif page == "Configuración":
    st.title("⚙️ Configuración")

    st.subheader("Datos del personaje")
    new_name = st.text_input("Nombre del personaje", value=st.session_state.player_name)
    base_xp = st.number_input(
        "XP base por nivel (afecta la dificultad)",
        min_value=10,
        max_value=1000,
        value=st.session_state.base_xp_per_level
    )

    if st.button("💾 Guardar configuración de personaje"):
        st.session_state.player_name = new_name.strip() or "Héroe sin nombre"
        st.session_state.base_xp_per_level = int(base_xp)
        st.success("Configuración actualizada.")

    st.markdown("---")
    st.subheader("Atributos")

    st.write("Atributos actuales:")
    for attr_name, value in st.session_state.attributes.items():
        st.write(f"- {attr_name}: {value} XP")

    st.markdown("### Añadir nuevo atributo")
    new_attr = st.text_input("Nombre del nuevo atributo (puedes usar emojis)", placeholder="Ej: Creatividad 🎨")
    if st.button("➕ Añadir atributo"):
        if not new_attr.strip():
            st.error("El atributo debe tener nombre.")
        elif new_attr in st.session_state.attributes:
            st.error("Ese atributo ya existe.")
        else:
            st.session_state.attributes[new_attr] = 0
            st.success("Atributo añadido.")

    st.markdown("---")
    st.subheader("⚠️ Zona peligrosa")

    if st.button("🗑️ Resetear todo (empezar de cero)"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()
