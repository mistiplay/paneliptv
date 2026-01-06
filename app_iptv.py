import streamlit as st
import requests
import hashlib
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from streamlit_javascript import st_javascript

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Buscador PRO", layout="wide", page_icon="📺")

# 🔴 TU ID DE GOOGLE SHEETS
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# --- INICIALIZACIÓN DE VARIABLES (CRUCIAL PARA EVITAR ERRORES) ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user' not in st.session_state: st.session_state.user = "" 
if 'iptv_data' not in st.session_state: st.session_state.iptv_data = None
if 'mode' not in st.session_state: st.session_state.mode = 'live'
if 'user_ip_cached' not in st.session_state: st.session_state.user_ip_cached = None
# Cache de datos
if 'data_live' not in st.session_state: st.session_state.data_live = None
if 'data_vod' not in st.session_state: st.session_state.data_vod = None
if 'data_series' not in st.session_state: st.session_state.data_series = None

# 2. ESTILOS VISUALES (GRID RESPONSIVO ARREGLADO)
st.markdown("""
    <style>
    /* Ocultar elementos nativos */
    #MainMenu, header, footer {visibility: hidden;}
    
    /* FONDO */
    .stApp {
        background-color: #0e0e0e;
        background-image: radial-gradient(circle at center, #1a1a1a 0%, #000 100%);
        color: white;
    }

    /* FORMULARIOS */
    div[data-testid="stForm"] {
        background-color: rgba(20, 20, 20, 0.95);
        padding: 30px;
        border-radius: 10px;
        border: 1px solid #333;
        box-shadow: 0 0 20px rgba(0, 198, 255, 0.1);
    }
    .stTextInput > div > div > input { background-color: #222; color: white; border: 1px solid #444; }
    .stButton > button { width: 100%; background-color: #0069d9; color: white; border: none; font-weight: 600; height: 45px; }
    .stButton > button:hover { background-color: #0056b3; }

    /* --- REJILLA RESPONSIVA (GRID) --- */
    /* Esto controla que en movil se vean 3 y en PC se ajusten */
    .vod-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); /* PC: Mínimo 150px */
        gap: 15px;
        padding-bottom: 20px;
    }
    
    /* REGLA MÓVIL: Forzar 3 columnas */
    @media (max-width: 768px) {
        .vod-grid {
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }
    }

    /* --- TARJETA VOD (SIN BORDES NEGROS) --- */
    .vod-card {
        background-color: #151515;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #333;
        transition: transform 0.2s;
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 8px rgba(0,0,0,0.4);
    }
    .vod-card:hover {
        transform: scale(1.05);
        border-color: #00C6FF;
        z-index: 10;
    }

    /* Contenedor Imagen (Full Width - Aspecto Poster 2:3) */
    .vod-img-box {
        width: 100%;
        padding-top: 150%; /* Esto crea el rectángulo vertical perfecto */
        position: relative;
    }
    .vod-img {
        position: absolute;
        top: 0; left: 0; bottom: 0; right: 0;
        width: 100%; height: 100%;
        object-fit: cover; /* La imagen llena todo el hueco */
    }

    /* Info Texto */
    .vod-info {
        padding: 8px 5px;
        text-align: center;
        background: #111;
        border-top: 1px solid #222;
        min-height: 50px; /* Altura mínima para que no quede cortado */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .vod-title {
        font-size: 13px !important; /* TEXTO MÁS GRANDE */
        font-weight: bold; 
        color: white;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        margin-bottom: 3px;
    }
    .vod-cat {
        font-size: 11px !important; /* TEXTO MÁS GRANDE */
        color: #00C6FF;
        font-weight: 500;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }

    /* --- LISTA CANALES --- */
    .channel-row {
        background-color: rgba(40, 40, 40, 0.6);
        padding: 12px 15px;
        margin-bottom: 6px;
        border-radius: 5px;
        border-left: 4px solid #0069d9;
        display: flex; align-items: center;
    }
    </style>
""", unsafe_allow_html=True)

# 3. FUNCIONES

@st.cache_data(ttl=60) 
def get_users_from_cloud():
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
    try:
        url = 'https://api.ipify.org'
        ip_js = st_javascript(f"await fetch('{url}').then(r => r.text())")
        if ip_js and isinstance(ip_js, str) and len(ip_js) > 6: return ip_js
        return None
    except: return None

def proxy_img(url):
    if not url or not url.startswith('http'): return "https://via.placeholder.com/200x300?text=No+Img"
    # Ajuste de proxy
    return f"https://wsrv.nl/?url={url}&w=200&h=300&fit=cover&output=webp"

# ==============================================================================
#  PANTALLA 1: LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if not st.session_state.user_ip_cached:
            ip = get_my_ip()
            if ip: 
                st.session_state.user_ip_cached = ip
                st.rerun()
        
        with st.form("login_form"):
            st.markdown("<h2 style='text-align:center; color:white;'>🔐 CLIENT ACCESS</h2>", unsafe_allow_html=True)
            if st.session_state.user_ip_cached:
                st.caption(f"IP Verificada: {st.session_state.user_ip_cached}")
            else:
                st.warning("⏳ Detectando IP... (Espera unos segundos)")

            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INICIAR SESIÓN"):
                if not st.session_state.user_ip_cached:
                    st.error("⚠️ Aún no se detecta tu IP. Espera unos segundos.")
                    st.stop()
                
                hashed_input = hashlib.sha256(str.encode(p)).hexdigest()
                users_db = get_users_from_cloud()
                
                found = False
                for user in users_db:
                    if str(user['username']) == u and str(user['password']) == hashed_input:
                        if str(user['allowed_ip']) == st.session_state.user_ip_cached:
                            st.session_state.logged_in = True
                            st.session_state.user = u
                            st.rerun()
                        else:
                            st.error(f"⛔ IP no autorizada ({st.session_state.user_ip_cached})")
                            found = True; break
                        found = True
                if not found: st.error("❌ Credenciales incorrectas.")
    st.stop()

# ==============================================================================
#  PANTALLA 2: CONECTAR (SOLUCIÓN BASE)
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
                            # Limpieza BASE
                            final_api = url_input.strip().replace("/get.php", "/player_api.php").replace("/xmltv.php", "/player_api.php")
                            headers = {"User-Agent": "Mozilla/5.0"} # Anti-bloqueo
                            res = requests.get(final_api, headers=headers, timeout=25)
                            
                            if res.status_code == 200:
                                try:
                                    data = res.json()
                                    if isinstance(data, dict) and 'user_info' in data:
                                        st.session_state.iptv_data = {"api": final_api, "info": data['user_info']}
                                        # Limpiar caches
                                        st.session_state.data_live = None
                                        st.session_state.data_vod = None
                                        st.session_state.data_series = None
                                        st.rerun()
                                    else: st.error("❌ Login fallido: Datos de usuario no encontrados.")
                                except: st.error("❌ Error: El servidor no devolvió JSON válido.")
                            else: st.error(f"❌ Error HTTP {res.status_code}")
                        except Exception as e: st.error(f"❌ Error técnico: {e}")
                else: st.warning("⚠️ URL inválida.")
    st.stop()

# ==============================================================================
#  PANTALLA 3: DASHBOARD (GRID HTML LIMPIO)
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# HEADER
exp = "Indefinido"
if info.get('exp_date') and str(info.get('exp_date')) != 'null':
    try: exp = datetime.fromtimestamp(int(info['exp_date'])).strftime('%d/%m/%Y')
    except: pass

st.markdown(f"""
<div style="background: rgba(20,20,20,0.95); padding:15px 25px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0069d9; margin-bottom:15px;">
    <span style="font-weight:bold; color:white; font-size:22px;">BUSCADOR DE CONTENIDO PRO</span>
    <div style="font-size:12px; color:#ccc; text-align:right;">
        <div>USER: <b style="color:white">{info.get('username')}</b></div>
        <div>EXP: <b style="color:#00C6FF">{exp}</b></div>
    </div>
</div>
""", unsafe_allow_html=True)

# MENÚ
c1, c2, c3, c4 = st.columns(4)
if c1.button("📡 TV EN VIVO"): st.session_state.mode = 'live'; st.rerun()
if c2.button("🎥 PELÍCULAS"): st.session_state.mode = 'vod'; st.rerun()
if c3.button("📺 SERIES"): st.session_state.mode = 'series'; st.rerun()
if c4.button("🔌 SALIR"): st.session_state.iptv_data = None; st.rerun()

# CARGA DATOS
def fetch_data(act_cont, act_cats):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        data = requests.get(f"{api}&action={act_cont}", headers=headers, timeout=30).json()
        cats = requests.get(f"{api}&action={act_cats}", headers=headers, timeout=20).json()
        return data, {str(c['category_id']): c['category_name'] for c in cats}
    except: return [], {}

mode = st.session_state.mode
if mode == 'live' and not st.session_state.data_live:
    with st.spinner("Cargando Canales..."): st.session_state.data_live = fetch_data('get_live_streams', 'get_live_categories')
elif mode == 'vod' and not st.session_state.data_vod:
    with st.spinner("Cargando Películas..."): st.session_state.data_vod = fetch_data('get_vod_streams', 'get_vod_categories')
elif mode == 'series' and not st.session_state.data_series:
    with st.spinner("Cargando Series..."): st.session_state.data_series = fetch_data('get_series', 'get_series_categories')

data, cat_map = [], {}
if mode == 'live': data, cat_map = st.session_state.data_live or ([], {})
elif mode == 'vod': data, cat_map = st.session_state.data_vod or ([], {})
elif mode == 'series': data, cat_map = st.session_state.data_series or ([], {})

# FILTROS
st.markdown("---")
cf, cb = st.columns([1, 2])
with cf:
    all_cats = ["Todas"] + sorted(list(cat_map.values()))
    sel_cat = st.selectbox("📂 Filtrar por Carpeta", all_cats)
with cb:
    query = st.text_input("🔍 Buscar Título", placeholder="Escribe para buscar...").lower()

filtered = data
if sel_cat != "Todas":
    t_ids = [k for k, v in cat_map.items() if v == sel_cat]
    if t_ids: filtered = [x for x in filtered if str(x.get('category_id')) in t_ids]
if query:
    filtered = [x for x in filtered if query in str(x.get('name')).lower()]

# RENDERIZADO
st.info(f"Mostrando {len(filtered)} resultados")

if mode == 'live':
    # LISTA CANALES (TEXTO GRANDE)
    html = ""
    for item in filtered[:100]:
        cat_name = cat_map.get(str(item.get('category_id')), "General")
        html += f"""
        <div class="channel-row">
            <div style="width:50px; color:#00C6FF; font-weight:bold; font-size:16px;">{item.get('num', '#')}</div>
            <div style="flex-grow:1;">
                <div style="font-size:13px; color:#aaa; font-weight:600; text-transform:uppercase;">{cat_name}</div>
                <div style="color:white; font-weight:500; font-size:15px;">{item.get('name')}</div>
            </div>
        </div>"""
    st.markdown(html, unsafe_allow_html=True)

else:
    # GRID HTML CONSTRUIDO LIMPIAMENTE (SIN st.columns)
    limit = 60
    view_items = filtered[:limit]
    
    # Inicio del contenedor Grid
    html_content = '<div class="vod-grid">'
    
    for item in view_items:
        img = proxy_img(item.get('stream_icon') or item.get('cover'))
        title = item.get('name').replace('"', '&quot;') # Escapar comillas
        folder = cat_map.get(str(item.get('category_id')), "VOD")
        
        # Tarjeta Individual
        html_content += f"""
        <div class="vod-card">
            <div class="vod-img-box">
                <img src="{img}" class="vod-img" loading="lazy">
            </div>
            <div class="vod-info">
                <div class="vod-title" title="{title}">{title}</div>
                <div class="vod-cat">📂 {folder}</div>
            </div>
        </div>
        """
    
    html_content += '</div>' # Fin del contenedor Grid
    
    st.markdown(html_content, unsafe_allow_html=True)
            
    if len(filtered) > limit:
        st.warning(f"⚠️ Mostrando los primeros {limit} resultados. Usa el buscador.")
