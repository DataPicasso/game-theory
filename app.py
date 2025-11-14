import streamlit as st
from datetime import date, datetime
import requests
import base64
import json

# ======================================
#   CONFIGURACIÓN BÁSICA DE LA APP
# ======================================

st.set_page_config(
    page_title="LifeRPG",
    layout="wide"
)

# ======================================
#   CSS PARA ESTILO MINIMALISTA
# ======================================

def inject_css():
    st.markdown(
        """
        <style>
        /* Fondo y texto generales */
        body, .stApp {
            background-color: #FFFFFF;
            color: #000000;
        }

        /* Sidebar con borde sutil */
        section[data-testid="stSidebar"] {
            border-right: 1px solid #000000;
        }

        /* Botones minimalistas */
        div.stButton > button {
            border: 1px solid #000000;
            color: #000000;
            background-color: #FFFFFF;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            transition: all 0.15s ease-in-out;
            font-weight: 500;
        }
        div.stButton > button:hover {
            background-color: #000000;
            color: #FFFFFF;
        }

        /* Formularios e inputs */
        input, textarea, select {
            border: 1px solid #000000 !important;
            border-radius: 4px !important;
        }

        /* Títulos y secciones */
        h1, h2, h3, h4 {
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ======================================
#   AUTH Y GITHUB HELPERS
# ======================================

def get_valid_users():
    # Usuarios definidos en secrets.toml, sección [auth]
    try:
        return dict(st.secrets["auth"])
    except Exception:
        # Fallback por si no tienes secrets bien configurados
        return {"demo": "demo"}


def github_config():
    try:
        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
        return token, repo
    except Exception:
        st.error("No se pudo leer la configuración de GitHub desde secrets.")
        return None, None


def github_file_url(username: str):
    token, repo = github_config()
    if not token or not repo:
        return None, None, None
    api_url = f"https://api.github.com/repos/{repo}/contents/data/{username}.json"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    return api_url, headers, token


def export_state():
    """Convierte st.session_state en un dict serializable."""
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
    st.session_state.player_name = data.get("player_name", "Heroe sin nombre")
    st.session_state.level = data.get("level", 1)
    st.session_state.xp = data.get("xp", 0)
    st.session_state.base_xp_per_level = data.get("base_xp_per_level", 100)
    st.session_state.attributes = data.get(
        "attributes",
        {
            "Fuerza": 0,
            "Inteligencia": 0,
            "Carisma": 0,
            "Vitalidad": 0,
        },
    )
    st.session_state.quests = data.get("quests", [])

    # Reconstruir logs con timestamps
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
        st.success("Datos cargados desde GitHub.")
    elif resp.status_code == 404:
        st.info("No se encontraron datos en GitHub para este usuario. Empezarás desde cero.")
        st.session_state.github_sha = None
    else:
        st.error(f"No se pudo cargar desde GitHub (status {resp.status_code}).")


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
        st.success("Datos guardados en GitHub.")
    else:
        st.error(f"No se pudo guardar en GitHub (status {resp.status_code}).")


# ======================================
#   ESTADO INICIAL
# ======================================

def init_game_state():
    if "player_name" not in st.session_state:
        st.session_state.player_name = "Heroe sin nombre"
    if "level" not in st.session_state:
        st.session_state.level = 1
    if "xp" not in st.session_state:
        st.session_state.xp = 0
    if "base_xp_per_level" not in st.session_state:
        st.session_state.base_xp_per_level = 100
    if "attributes" not in st.session_state:
        st.session_state.attributes = {
            "Fuerza": 0,
            "Inteligencia": 0,
            "Carisma": 0,
            "Vitalidad": 0,
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

# ======================================
#   LOGIN
# ======================================

def login_view():
    inject_css()
    st.title("LifeRPG")
    st.subheader("Acceso")

    users = get_valid_users()

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")

    if submit:
        if username in users and users[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.success(f"Bienvenido, {username}.")
            init_game_state()
            load_state_from_github(username)
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    st.info("Modo demo: usuario 'demo', contraseña 'demo'.")


# ======================================
#   FUNCIONES DEL JUEGO
# ======================================

def xp_needed_for_next_level(level: int) -> int:
    return st.session_state.base_xp_per_level * level


def add_xp(amount: int):
    st.session_state.xp += amount
    while st.session_state.xp >= xp_needed_for_next_level(st.session_state.level):
        st.session_state.xp -= xp_needed_for_next_level(st.session_state.level)
        st.session_state.level += 1
        st.success(f"Nuevo nivel alcanzado: {st.session_state.level}.")


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
        today_str in st.session_state.completed_today
        and quest_id in st.session_state.completed_today[today_str]
    )


# ======================================
#   SI NO HAY LOGIN -> PEDIR LOGIN
# ======================================

if not st.session_state.authenticated:
    login_view()
    st.stop()

# Usuario autenticado
inject_css()
init_game_state()

# ======================================
#   SIDEBAR
# ======================================

st.sidebar.title("LifeRPG")
st.sidebar.caption(f"Usuario: {st.session_state.username}")

page = st.sidebar.radio(
    "Navegación",
    ["Dashboard", "Misiones y habitos", "Registro del dia", "Configuracion"],
)

st.sidebar.markdown("---")
st.sidebar.write(f"Personaje: {st.session_state.player_name}")
st.sidebar.write(f"Nivel: {st.session_state.level}")

if st.sidebar.button("Guardar en GitHub"):
    save_state_to_github(st.session_state.username)

if st.sidebar.button("Cargar desde GitHub"):
    load_state_from_github(st.session_state.username)
    st.experimental_rerun()

if st.sidebar.button("Cerrar sesion"):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.experimental_rerun()


# ======================================
#   PANTALLA: DASHBOARD
# ======================================

if page == "Dashboard":
    st.title("Dashboard")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Estado del personaje")
        current_level = st.session_state.level
        xp_current = st.session_state.xp
        xp_needed = xp_needed_for_next_level(current_level)
        st.write(f"Nivel actual: {current_level}")
        st.write(f"Experiencia: {xp_current} / {xp_needed}")
        progress = xp_current / xp_needed if xp_needed > 0 else 0
        st.progress(progress)

    with col2:
        st.subheader("Resumen de hoy")
        today = date.today().strftime("%d/%m/%Y")
        st.write(f"Fecha: {today}")
        today_key = date.today().isoformat()
        completed_today = len(st.session_state.completed_today.get(today_key, []))
        st.metric("Misiones completadas hoy", completed_today)

    st.markdown("---")
    st.subheader("Atributos")

    cols = st.columns(2)
    items = list(st.session_state.attributes.items())
    for i, (attr_name, value) in enumerate(items):
        with cols[i % 2]:
            st.metric(attr_name, value)

    st.markdown("---")
    st.subheader("Actividad reciente")

    recent_logs = sorted(
        st.session_state.logs, key=lambda x: x["timestamp"], reverse=True
    )[:10]
    if not recent_logs:
        st.info("Todavia no hay actividades registradas.")
    else:
        for log in recent_logs:
            ts = log["timestamp"].strftime("%d/%m %H:%M")
            st.write(
                f"- {ts} | {log['description']} (+{log['xp']} XP en {log['attribute']}) [{log['source']}]"
            )


# ======================================
#   PANTALLA: MISIONES
# ======================================

elif page == "Misiones y habitos":
    st.title("Misiones y habitos")

    st.subheader("Crear nueva mision")

    with st.form("new_quest_form"):
        q_name = st.text_input("Nombre de la mision", placeholder="Ejemplo: Leer 20 minutos")
        q_type = st.selectbox("Tipo de mision", ["Diaria", "Semanal", "Epica"])
        q_attribute = st.selectbox("Atributo principal", list(st.session_state.attributes.keys()))
        q_xp = st.number_input(
            "Experiencia otorgada al completarla",
            min_value=1,
            max_value=1000,
            value=10,
        )
        submitted = st.form_submit_button("Añadir mision")

        if submitted:
            if not q_name.strip():
                st.error("La mision debe tener un nombre.")
            else:
                st.session_state.quests.append(
                    {
                        "name": q_name.strip(),
                        "type": q_type,
                        "attribute": q_attribute,
                        "xp": int(q_xp),
                    }
                )
                st.success("Mision creada.")

    st.markdown("---")
    st.subheader("Lista de misiones")

    if not st.session_state.quests:
        st.info("No tienes misiones aun. Crea alguna en el formulario de arriba.")
    else:
        for idx, quest in enumerate(st.session_state.quests):
            completed = is_quest_completed_today(idx)
            cols = st.columns([4, 2, 2, 2])
            with cols[0]:
                st.write(quest["name"])
                st.caption(f"Tipo: {quest['type']}")
            with cols[1]:
                st.write(f"Atributo: {quest['attribute']}")
            with cols[2]:
                st.write(f"Recompensa: {quest['xp']} XP")
            with cols[3]:
                if completed:
                    st.success("Completada hoy")
                else:
                    if st.button("Completar", key=f"complete_{idx}"):
                        add_xp(quest["xp"])
                        add_attribute_xp(quest["attribute"], quest["xp"])
                        mark_quest_completed(idx)
                        log_action(
                            description=f"Completó mision: {quest['name']}",
                            attribute=quest["attribute"],
                            xp_amount=quest["xp"],
                            source="Mision",
                        )
                        st.experimental_rerun()


# ======================================
#   PANTALLA: REGISTRO DEL DIA
# ======================================

elif page == "Registro del dia":
    st.title("Registro del dia")

    st.subheader("Registrar una accion")

    with st.form("log_action_form"):
        desc = st.text_input("Descripcion", placeholder="Ejemplo: Correr 3 kilometros")
        attr = st.selectbox("Atributo afectado", list(st.session_state.attributes.keys()))
        xp_amount = st.number_input(
            "Experiencia a otorgar", min_value=1, max_value=500, value=10
        )
        submitted = st.form_submit_button("Registrar")

        if submitted:
            if not desc.strip():
                st.error("La descripcion no puede estar vacia.")
            else:
                add_xp(int(xp_amount))
                add_attribute_xp(attr, int(xp_amount))
                log_action(
                    description=desc.strip(),
                    attribute=attr,
                    xp_amount=int(xp_amount),
                    source="Registro manual",
                )
                st.success("Accion registrada.")

    st.markdown("---")
    st.subheader("Historial reciente")

    if not st.session_state.logs:
        st.info("Todavia no tienes registros.")
    else:
        recent_logs = sorted(
            st.session_state.logs, key=lambda x: x["timestamp"], reverse=True
        )[:20]
        for log in recent_logs:
            ts = log["timestamp"].strftime("%d/%m %H:%M")
            st.write(
                f"- {ts} | {log['description']} (+{log['xp']} XP en {log['attribute']}) [{log['source']}]"
            )


# ======================================
#   PANTALLA: CONFIGURACION
# ======================================

elif page == "Configuracion":
    st.title("Configuracion")

    st.subheader("Datos del personaje")

    new_name = st.text_input("Nombre del personaje", value=st.session_state.player_name)
    base_xp = st.number_input(
        "Experiencia base por nivel (dificultad)",
        min_value=10,
        max_value=1000,
        value=st.session_state.base_xp_per_level,
    )

    if st.button("Guardar configuracion de personaje"):
        st.session_state.player_name = new_name.strip() or "Heroe sin nombre"
        st.session_state.base_xp_per_level = int(base_xp)
        st.success("Configuracion actualizada.")

    st.markdown("---")
    st.subheader("Atributos")

    st.write("Atributos actuales:")
    for attr_name, value in st.session_state.attributes.items():
        st.write(f"- {attr_name}: {value} XP")

    st.markdown("Añadir nuevo atributo")
    new_attr = st.text_input(
        "Nombre del nuevo atributo",
        placeholder="Ejemplo: Creatividad",
    )
    if st.button("Añadir atributo"):
        if not new_attr.strip():
            st.error("El atributo debe tener nombre.")
        elif new_attr in st.session_state.attributes:
            st.error("Ese atributo ya existe.")
        else:
            st.session_state.attributes[new_attr] = 0
            st.success("Atributo añadido.")

    st.markdown("---")
    st.subheader("Zona peligrosa")

    if st.button("Resetear todo"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()
