import streamlit as st
import requests
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# CONFIGURACIÓN
st.set_page_config(page_title="IPTV Player", layout="wide", page_icon="📺")

# 🔴 PEGA TU ENLACE DE GOOGLE SHEETS AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/TU_ID_DE_HOJA_AQUI/edit"

# --- ESTILOS VISUALES (Negro/Azul) ---
st.markdown("""
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp { background-color: #0e0e0e; color: white; }
    div[data-testid="stForm"] { 
        background-color: #1e1e1e; padding: 40px; border-radius: 12px; 
        border: 1px solid #333; box-shadow: 0 4px 20px rgba(0,0,0,0.5); 
    }
    .stTextInput>div>div>input { background-color: #2d2d2d; color: white; border: 1px solid #444; }
    .stButton>button { 
        background-color: #0069d9; color: white; border: none; font-weight: bold; 
        height: 45px; transition: 0.3s; width: 100%;
    }
    .stButton>button:hover { background-color: #0056b3; box-shadow: 0 0 15px rgba(0,105,217,0.5); }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN SEGURA Y CACHÉ ---
# Usamos cache para no leer la hoja de Google en cada clic (ahorra cuota y es más rápido)
@st.cache_data(ttl=10) 
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
    try: return requests.get('https://api.ipify.org', timeout=3).text
    except: return "Unknown"

# --- LÓGICA DE SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'iptv_data' not in st.session_state: st.session_state.iptv_data = None

# ==============================================================================
#  PANTALLA 1: LOGIN (Valida contra Google Sheets)
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login"):
            st.markdown("<h2 style='text-align:center'>🔐 ACCESO CLIENTES</h2>", unsafe_allow_html=True)
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            
            if st.form_submit_button("INGRESAR"):
                current_ip = get_my_ip()
                hashed_input = hashlib.sha256(str.encode(p)).hexdigest()
                
                # Descargar usuarios de la nube
                users_db = get_users_from_cloud()
                
                found = False
                for user in users_db:
                    # Validar credenciales
                    if str(user['username']) == u and str(user['password']) == hashed_input:
                        # Validar IP
                        if str(user['allowed_ip']) == current_ip:
                            st.session_state.logged_in = True
                            st.session_state.user = u
                            st.rerun()
                        else:
                            st.error(f"⛔ IP no autorizada: {current_ip}")
                            found = True
                            break
                        found = True
                
                if not found:
                    st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==============================================================================
#  PANTALLA 2: CONECTAR URL IPTV
# ==============================================================================
if st.session_state.iptv_data is None:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"<p style='text-align:center; color:#888'>Hola, {st.session_state.user}</p>", unsafe_allow_html=True)
        with st.form("connect_iptv"):
            st.markdown("<h3 style='text-align:center'>🔗 CONECTAR LISTA</h3>", unsafe_allow_html=True)
            url = st.text_input("Pega tu enlace M3U / URL")
            
            if st.form_submit_button("CONECTAR"):
                if "http" in url and "username=" in url:
                    with st.spinner("Conectando..."):
                        try:
                            # Limpieza básica URL
                            clean_url = url.split("?")[0].replace("/get.php", "/player_api.php")
                            params = parse_qs(urlparse(url).query)
                            u_iptv = params.get('username')[0]
                            p_iptv = params.get('password')[0]
                            host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                            
                            # Test de conexión
                            api = f"{host}/player_api.php?username={u_iptv}&password={p_iptv}"
                            res = requests.get(api, timeout=10)
                            
                            if res.status_code == 200 and 'user_info' in res.json():
                                st.session_state.iptv_data = {
                                    "api": api, "host": host, "u": u_iptv, "p": p_iptv,
                                    "info": res.json()['user_info']
                                }
                                st.rerun()
                            else: st.error("No se pudo conectar. Revisa el enlace.")
                        except: st.error("URL inválida.")
                else: st.warning("Formato de URL incorrecto.")
    st.stop()

# ==============================================================================
#  PANTALLA 3: DASHBOARD (BUSCADOR)
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# Header
st.markdown(f"""
<div style="background:#222; padding:15px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0069d9; margin-bottom:20px;">
    <div style="font-weight:bold; font-size:18px;">📺 PLAYER</div>
    <div style="text-align:right; font-size:12px; color:#aaa;">
        CLIENTE: <b style="color:white">{info.get('username')}</b><br>
        EXPIRA: <b style="color:#00C6FF">{datetime.fromtimestamp(int(info.get('exp_date', 0))).strftime('%d/%m/%Y')}</b>
    </div>
</div>
""", unsafe_allow_html=True)

# Menú
col1, col2, col3, col4 = st.columns(4)
mode = st.session_state.get('mode', 'live')
if col1.button("📡 TV EN VIVO"): st.session_state.mode = 'live'; st.rerun()
if col2.button("🎥 PELÍCULAS"): st.session_state.mode = 'vod'; st.rerun()
if col3.button("📺 SERIES"): st.session_state.mode = 'series'; st.rerun()
if col4.button("🔌 SALIR"): st.session_state.iptv_data = None; st.rerun()

# Buscador
q = st.text_input(f"🔍 Buscar en {st.session_state.mode}...", placeholder="Escribe nombre...").lower()

if q:
    action_map = {'live': 'get_live_streams', 'vod': 'get_vod_streams', 'series': 'get_series'}
    with st.spinner("Buscando..."):
        try:
            url = f"{api}&action={action_map[st.session_state.mode]}"
            data = requests.get(url, timeout=15).json()
            
            # Filtrar
            results = [x for x in data if q in str(x.get('name')).lower()]
            
            if results:
                st.success(f"Encontrados: {len(results)}")
                # Grid simple visual
                cols = st.columns(4)
                for idx, item in enumerate(results[:40]):
                    with cols[idx % 4]:
                        img = item.get('stream_icon') or item.get('cover')
                        if not img or "http" not in img: img = "https://via.placeholder.com/150"
                        else: img = f"https://wsrv.nl/?url={img}&w=200&h=300&fit=cover"
                        
                        st.markdown(f"""
                        <div style="background:#222; border-radius:8px; overflow:hidden; margin-bottom:10px;">
                            <img src="{img}" style="width:100%; aspect-ratio:2/3; object-fit:cover;">
                            <div style="padding:8px; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                                {item.get('name')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else: st.warning("No encontrado.")
        except: st.error("Error al buscar.")