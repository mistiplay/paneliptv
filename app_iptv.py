import streamlit as st
import requests
import hashlib
import gspread
import time
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from streamlit_javascript import st_javascript

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="IPTV Player Pro", layout="wide", page_icon="📺")

# 🔴 TU ID DE GOOGLE SHEETS ACTUALIZADO
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# --- 🎨 ESTILOS VISUALES (RESTAURADOS: CARPETAS Y GRID) ---
st.markdown("""
    <style>
    /* Ocultar elementos nativos */
    #MainMenu, header, footer {visibility: hidden;}
    
    /* FONDO DE PANTALLA */
    .stApp {
        background-color: #0e0e0e;
        background-image: radial-gradient(circle at center, #1a1a1a 0%, #000 100%);
        color: white;
    }

    /* FORMULARIOS */
    div[data-testid="stForm"] {
        background-color: rgba(30, 30, 30, 0.95);
        padding: 30px;
        border-radius: 12px;
        border: 1px solid #333;
        box-shadow: 0 0 25px rgba(0, 198, 255, 0.1);
    }

    /* INPUTS Y SELECTBOX */
    .stTextInput > div > div > input {
        background-color: #222; color: white; border: 1px solid #444; border-radius: 5px;
    }
    div[data-baseweb="select"] > div {
        background-color: #222; color: white; border: 1px solid #444;
    }

    /* BOTONES */
    .stButton > button {
        width: 100%; background-color: #0069d9; color: white; border: none;
        font-weight: 600; text-transform: uppercase; height: 45px; transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #0056b3; box-shadow: 0 0 15px rgba(0, 105, 217, 0.6); transform: translateY(-2px);
    }

    /* --- GRID VOD (RESTORED) --- */
    .vod-card {
        background-color: #1e1e1e;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 10px;
        border: 1px solid #333;
        transition: transform 0.2s;
        height: 100%;
    }
    .vod-card:hover {
        transform: scale(1.03);
        border-color: #00C6FF;
        z-index: 10;
    }
    .vod-img-container {
        width: 100%;
        padding-top: 150%; /* Aspect Ratio 2:3 for Posters */
        position: relative;
    }
    .vod-img {
        position: absolute;
        top: 0; left: 0; bottom: 0; right: 0;
        width: 100%; height: 100%;
        object-fit: cover;
    }
    .vod-title {
        padding: 8px;
        font-size: 11px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        text-align: center;
        color: #eee;
        background: #111;
    }

    /* --- LISTA CANALES --- */
    .channel-row {
        background-color: rgba(40, 40, 40, 0.6);
        padding: 8px 12px;
        margin-bottom: 5px;
        border-radius: 4px;
        border-left: 4px solid #0069d9;
        display: flex;
        align-items: center;
        font-size: 14px;
    }
    </style>
""", unsafe_allow_html=True)

# --- ☁️ CONEXIÓN Y UTILIDADES ---

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
    """IP Real via JS"""
    try:
        url = 'https://api.ipify.org'
        ip_js = st_javascript(f"await fetch('{url}').then(r => r.text())")
        if ip_js and isinstance(ip_js, str) and len(ip_js) > 6: 
            return ip_js
        return None
    except: return None

def proxy_img(url):
    if not url or not url.startswith('http'): return "https://via.placeholder.com/150x225?text=No+Img"
    return f"https://wsrv.nl/?url={url}&w=200&h=300&fit=cover&output=webp"

# --- ESTADO DE SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'iptv_data' not in st.session_state: st.session_state.iptv_data = None
if 'mode' not in st.session_state: st.session_state.mode = 'live'
# Cache de datos temporal
if 'data_live' not in st.session_state: st.session_state.data_live = None
if 'data_vod' not in st.session_state: st.session_state.data_vod = None
if 'data_series' not in st.session_state: st.session_state.data_series = None

# ==============================================================================
#  PANTALLA 1: LOGIN
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        mi_ip = get_my_ip()
        
        if mi_ip is None:
            st.warning("⏳ Detectando ubicación... (Espera un segundo)")
            time.sleep(1) 
            st.rerun() 
        
        with st.form("login_form"):
            st.markdown("<h2 style='text-align:center; color:white;'>🔐 CLIENT ACCESS</h2>", unsafe_allow_html=True)
            st.caption(f"IP Detectada: {mi_ip}")

            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            
            if st.form_submit_button("INICIAR SESIÓN"):
                hashed_input = hashlib.sha256(str.encode(p)).hexdigest()
                users_db = get_users_from_cloud()
                
                if not users_db:
                    st.error("⚠️ Error de conexión DB.")
                    st.stop()

                found = False
                for user in users_db:
                    if str(user['username']) == u and str(user['password']) == hashed_input:
                        if str(user['allowed_ip']) == mi_ip:
                            st.session_state.logged_in = True
                            st.session_state.user = u
                            st.rerun()
                        else:
                            st.error(f"⛔ IP no autorizada ({mi_ip})")
                            found = True
                            break
                        found = True
                
                if not found:
                    st.error("❌ Credenciales incorrectas.")
    st.stop()

# ==============================================================================
#  PANTALLA 2: CONECTAR URL (SOLUCIÓN ERROR DE FORMATO)
# ==============================================================================
if st.session_state.iptv_data is None:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"<p style='text-align:center; color:#aaa'>Usuario: <b style='color:white'>{st.session_state.user}</b></p>", unsafe_allow_html=True)
        with st.form("connect_iptv"):
            st.markdown("<h3 style='text-align:center'>🔗 CONECTAR PLAYER</h3>", unsafe_allow_html=True)
            url = st.text_input("Pega tu enlace M3U / URL")
            
            if st.form_submit_button("CONECTAR"):
                # Validación más flexible
                if "http" in url and ("username=" in url or "get.php" in url or "player_api" in url):
                    with st.spinner("⏳ Conectando..."):
                        try:
                            # 1. Limpieza inteligente: Si ya es player_api, no romperla
                            final_api = url.strip()
                            
                            # Si es un enlace tipo get.php, lo convertimos
                            if "get.php" in final_api:
                                final_api = final_api.replace("/get.php", "/player_api.php")
                            
                            # Si tiene xmltv, lo quitamos
                            if "xmltv.php" in final_api:
                                final_api = final_api.replace("/xmltv.php", "/player_api.php")
                                
                            # Extraemos credenciales para asegurar
                            parsed = urlparse(final_api)
                            params = parse_qs(parsed.query)
                            
                            u_iptv = params.get('username', [''])[0]
                            p_iptv = params.get('password', [''])[0]
                            
                            # Reconstruimos la base limpia
                            host = f"{parsed.scheme}://{parsed.netloc}"
                            api_clean = f"{host}/player_api.php?username={u_iptv}&password={p_iptv}"
                            
                            # 2. Prueba de conexión
                            res = requests.get(api_clean, timeout=15) # Timeout más largo para servidores lentos
                            
                            if res.status_code == 200:
                                try:
                                    data = res.json()
                                    if 'user_info' in data:
                                        st.session_state.iptv_data = {
                                            "api": api_clean, 
                                            "host": host, 
                                            "info": data['user_info']
                                        }
                                        st.rerun()
                                    else:
                                        st.error("❌ El enlace no devolvió información de usuario.")
                                except:
                                    st.error("❌ El servidor no devolvió JSON válido.")
                            else: 
                                st.error(f"❌ Error HTTP: {res.status_code}")
                        except Exception as e: 
                            st.error(f"❌ Error procesando URL: {e}")
                else: 
                    st.warning("⚠️ URL inválida. Asegúrate de copiar el enlace completo.")
    st.stop()

# ==============================================================================
#  PANTALLA 3: DASHBOARD RESTAURADO (CARPETAS + GRID)
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# --- HEADER INFO ---
exp = "Indefinido"
if info.get('exp_date') and str(info.get('exp_date')) != 'null':
    exp = datetime.fromtimestamp(int(info['exp_date'])).strftime('%d/%m/%Y')

st.markdown(f"""
<div style="background: rgba(20,20,20,0.9); padding:10px 20px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0069d9; margin-bottom:15px;">
    <span style="font-weight:bold; color:white;">IPTV PLAYER PRO</span>
    <div style="font-size:11px; color:#ccc;">
        USER: <b style="color:white">{info.get('username')}</b> | 
        EXP: <b style="color:#00C6FF">{exp}</b> | 
        STATUS: <b style="color:#00FF00">{info.get('status')}</b>
    </div>
</div>
""", unsafe_allow_html=True)

# --- MENÚ SUPERIOR ---
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

# --- LÓGICA DE CARGA DE DATOS (CON CATEGORÍAS) ---

def fetch_data(action_streams, action_cats):
    """Descarga streams y categorías"""
    try:
        url_s = f"{api}&action={action_streams}"
        url_c = f"{api}&action={action_cats}"
        streams = requests.get(url_s, timeout=25).json()
        cats = requests.get(url_c, timeout=25).json()
        # Mapa de categorías: ID -> Nombre
        cat_map = {c['category_id']: c['category_name'] for c in cats}
        return streams, cat_map
    except: return [], {}

# Carga perezosa según la pestaña
if st.session_state.mode == 'live' and st.session_state.data_live is None:
    with st.spinner("Cargando Canales y Categorías..."):
        st.session_state.data_live = fetch_data('get_live_streams', 'get_live_categories')

elif st.session_state.mode == 'vod' and st.session_state.data_vod is None:
    with st.spinner("Cargando Películas..."):
        st.session_state.data_vod = fetch_data('get_vod_streams', 'get_vod_categories')

elif st.session_state.mode == 'series' and st.session_state.data_series is None:
    with st.spinner("Cargando Series..."):
        st.session_state.data_series = fetch_data('get_series', 'get_series_categories')

# --- SELECCIÓN DE DATOS ACTUALES ---
current_data = []
current_cats = {}
if st.session_state.mode == 'live': current_data, current_cats = st.session_state.data_live or ([], {})
elif st.session_state.mode == 'vod': current_data, current_cats = st.session_state.data_vod or ([], {})
elif st.session_state.mode == 'series': current_data, current_cats = st.session_state.data_series or ([], {})

# --- BARRA DE FILTROS (CATEGORÍA + BÚSQUEDA) ---
st.markdown("---")
c_filtro, c_busq = st.columns([1, 2])

with c_filtro:
    # Crear lista de categorías ordenadas
    cat_names = ["Todo"] + sorted(list(current_cats.values()))
    selected_cat_name = st.selectbox("📂 Carpeta / Categoría", cat_names)

with c_busq:
    search_q = st.text_input("🔍 Buscar Título", placeholder="Escribe para filtrar...")

# --- LÓGICA DE FILTRADO ---
filtered_items = []

# 1. Filtrar por Categoría
if selected_cat_name == "Todo":
    filtered_items = current_data
else:
    # Buscar el ID de la categoría seleccionada
    target_id = next((k for k, v in current_cats.items() if v == selected_cat_name), None)
    if target_id:
        filtered_items = [x for x in current_data if x.get('category_id') == target_id]

# 2. Filtrar por Texto
if search_q:
    filtered_items = [x for x in filtered_items if search_q.lower() in str(x.get('name')).lower()]

# --- VISUALIZACIÓN ---

st.info(f"Mostrando {len(filtered_items)} resultados")

if st.session_state.mode == 'live':
    # MODO LISTA SIMPLE
    html = ""
    for item in filtered_items[:100]: # Limite visual
        html += f"""
        <div class="channel-row">
            <span style="color:#00C6FF; font-weight:bold; width:50px;">{item.get('num', '#')}</span>
            <span style="color:white; font-weight:500;">{item.get('name')}</span>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)

else:
    # MODO GRID (PELICULAS / SERIES) - PORTADAS VERTICALES
    
    # Paginación simple para no explotar el navegador con 5000 imagenes
    page_size = 60
    # Mostramos solo los primeros 60 del filtro para velocidad
    visible_items = filtered_items[:page_size]
    
    # CSS Grid Layout nativo de Streamlit
    cols = st.columns(6) # 6 Columnas para que se vea mas denso
    
    for idx, item in enumerate(visible_items):
        with cols[idx % 6]:
            img_url = item.get('stream_icon') or item.get('cover')
            final_img = proxy_img(img_url)
            
            # HTML Card
            st.markdown(f"""
            <div class="vod-card">
                <div class="vod-img-container">
                    <img src="{final_img}" class="vod-img" loading="lazy">
                </div>
                <div class="vod-title" title="{item.get('name')}">
                    {item.get('name')}
                </div>
            </div>
            """, unsafe_allow_html=True)

    if len(filtered_items) > page_size:
        st.warning(f"⚠️ Mostrando solo los primeros {page_size} resultados. Usa el buscador o filtros para ver más.")
