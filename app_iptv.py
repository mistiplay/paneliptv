import streamlit as st
import requests
import hashlib
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from streamlit_javascript import st_javascript

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="IPTV Player Pro", layout="wide", page_icon="📺")

# 🔴 PEGA TU ENLACE DE GOOGLE SHEETS AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/TU_ID_DE_HOJA_AQUI/edit"

# --- 🎨 ESTILOS VISUALES ---
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
        padding: 40px;
        border-radius: 12px;
        border: 1px solid #333;
        box-shadow: 0 0 25px rgba(0, 198, 255, 0.1);
    }

    /* INPUTS */
    .stTextInput > div > div > input {
        background-color: #222;
        color: white;
        border: 1px solid #444;
        border-radius: 5px;
    }

    /* BOTONES */
    .stButton > button {
        width: 100%;
        background-color: #0069d9;
        color: white;
        border: none;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        height: 45px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #0056b3;
        box-shadow: 0 0 15px rgba(0, 105, 217, 0.6);
        transform: translateY(-2px);
    }

    /* --- GRID VOD --- */
    .vod-card-container {
        background-color: #1e1e1e;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 15px;
        border: 1px solid #333;
        transition: transform 0.2s;
    }
    .vod-card-container:hover {
        transform: scale(1.03);
        border-color: #00C6FF;
    }
    .vod-img {
        width: 100%;
        aspect-ratio: 2/3;
        object-fit: cover;
    }
    .vod-title {
        padding: 8px;
        font-size: 12px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        text-align: center;
        color: #eee;
    }

    /* --- LISTA CANALES --- */
    .channel-row {
        background-color: rgba(40, 40, 40, 0.6);
        padding: 10px 15px;
        margin-bottom: 8px;
        border-radius: 6px;
        border-left: 4px solid #0069d9;
        display: flex;
        align-items: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- ☁️ CONEXIÓN NUBE Y UTILIDADES ---

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
    except Exception as e:
        return []

def get_my_ip():
    """Detecta la IP REAL del cliente usando Javascript"""
    try:
        url = 'https://api.ipify.org'
        # Ejecuta JS en el navegador del usuario para pedir la IP
        ip_js = st_javascript(f"await fetch('{url}').then(r => r.text())")
        
        # Validamos que sea una IP real y no un objeto vacío cargando
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

# ==============================================================================
#  PANTALLA 1: LOGIN (Validación REAL de IP)
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            st.markdown("<h2 style='text-align:center; color:white;'>🔐 CLIENT ACCESS</h2>", unsafe_allow_html=True)
            
            # --- LÓGICA DE ESPERA DE IP ---
            mi_ip = get_my_ip()
            
            if mi_ip is None:
                st.warning("⏳ Detectando ubicación... (Espera un segundo)")
                time.sleep(1) # Pequeña pausa
                st.rerun()    # Recargar hasta tener la IP
            else:
                st.info(f"📡 Tu IP detectada: **{mi_ip}**")
            # ------------------------------

            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            
            if st.form_submit_button("INICIAR SESIÓN"):
                if not mi_ip:
                    st.error("⚠️ Aún no se detecta la IP. Intenta de nuevo.")
                    st.stop()

                # Hasheamos entrada
                hashed_input = hashlib.sha256(str.encode(p)).hexdigest()
                
                # Leemos la BD
                users_db = get_users_from_cloud()
                
                if not users_db:
                    st.error("⚠️ Error conectando a base de datos. Avisa al administrador.")
                    st.stop()

                found = False
                for user in users_db:
                    # Validar credenciales
                    if str(user['username']) == u and str(user['password']) == hashed_input:
                        # Validar IP
                        if str(user['allowed_ip']) == mi_ip:
                            st.session_state.logged_in = True
                            st.session_state.user = u
                            st.rerun()
                        else:
                            st.error(f"⛔ IP no autorizada. El sistema ve: {mi_ip}")
                            found = True
                            break
                        found = True
                
                if not found:
                    st.error("❌ Usuario o contraseña incorrectos.")
    st.stop()

# ==============================================================================
#  PANTALLA 2: CONECTAR URL
# ==============================================================================
if st.session_state.iptv_data is None:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"<p style='text-align:center; color:#aaa'>Bienvenido, <b style='color:white'>{st.session_state.user}</b></p>", unsafe_allow_html=True)
        with st.form("connect_iptv"):
            st.markdown("<h3 style='text-align:center'>🔗 CONECTAR PLAYER</h3>", unsafe_allow_html=True)
            url = st.text_input("Pega tu enlace M3U / URL del proveedor")
            
            if st.form_submit_button("CONECTAR"):
                if "http" in url and "username=" in url:
                    with st.spinner("⏳ Estableciendo conexión segura..."):
                        try:
                            clean_url = url.split("?")[0].replace("/get.php", "/player_api.php").replace("/xmltv.php", "/player_api.php")
                            parsed = urlparse(url)
                            params = parse_qs(parsed.query)
                            
                            u_iptv = params.get('username')[0]
                            p_iptv = params.get('password')[0]
                            host = f"{parsed.scheme}://{parsed.netloc}"
                            
                            api = f"{host}/player_api.php?username={u_iptv}&password={p_iptv}"
                            res = requests.get(api, timeout=10)
                            
                            if res.status_code == 200 and 'user_info' in res.json():
                                st.session_state.iptv_data = {
                                    "api": api, "host": host, 
                                    "info": res.json()['user_info']
                                }
                                st.rerun()
                            else: st.error("❌ Credenciales IPTV inválidas o expiradas.")
                        except: st.error("❌ Error de formato en la URL.")
                else: st.warning("⚠️ URL inválida. Debe contener usuario y contraseña.")
    st.stop()

# ==============================================================================
#  PANTALLA 3: DASHBOARD VISUAL
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# --- HEADER ---
exp_date = "Indefinido"
if info.get('exp_date') and str(info.get('exp_date')) != 'null':
    exp_date = datetime.fromtimestamp(int(info['exp_date'])).strftime('%d/%m/%Y')

st.markdown(f"""
<div style="background: rgba(20,20,20,0.9); padding:15px 25px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0069d9; margin-bottom:20px;">
    <div style="display:flex; align-items:center; gap:10px;">
        <span style="font-size:24px;">📺</span>
        <span style="font-weight:bold; font-size:18px; color:white;">IPTV PLAYER</span>
    </div>
    <div style="display:flex; gap:20px; text-align:right; font-size:12px;">
        <div>
            <div style="color:#888;">USUARIO</div>
            <div style="color:white; font-weight:bold;">{info.get('username')}</div>
        </div>
        <div style="border-left:1px solid #444; padding-left:20px;">
            <div style="color:#888;">EXPIRA</div>
            <div style="color:#00C6FF; font-weight:bold;">{exp_date}</div>
        </div>
        <div style="border-left:1px solid #444; padding-left:20px;">
            <div style="color:#888;">ESTADO</div>
            <div style="color:#00FF00; font-weight:bold;">{info.get('status')}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- MENÚ ---
c1, c2, c3, c4 = st.columns(4)
if c1.button("📡 TV EN VIVO"): st.session_state.mode = 'live'; st.rerun()
if c2.button("🎥 PELÍCULAS"): st.session_state.mode = 'vod'; st.rerun()
if c3.button("📺 SERIES"): st.session_state.mode = 'series'; st.rerun()
if c4.button("🔌 SALIR"): st.session_state.iptv_data = None; st.rerun()

# --- CONTENIDO ---
st.markdown("---")
q = st.text_input(f"🔍 BUSCAR EN {st.session_state.mode.upper()}...", placeholder="Escribe el nombre aquí...").lower()

if q:
    action_map = {'live': 'get_live_streams', 'vod': 'get_vod_streams', 'series': 'get_series'}
    
    with st.spinner(f"Buscando en catálogo {st.session_state.mode.upper()}..."):
        try:
            url_req = f"{api}&action={action_map[st.session_state.mode]}"
            data = requests.get(url_req, timeout=15).json()
            
            results = [x for x in data if q in str(x.get('name')).lower()]
            
            if results:
                st.success(f"✅ Se encontraron {len(results)} resultados.")
                
                # MODO LISTA (CANALES)
                if st.session_state.mode == 'live':
                    html = ""
                    for item in results[:50]:
                        html += f"""
                        <div class="channel-row">
                            <span style="color:#00C6FF; font-weight:bold; width:50px; font-size:14px;">{item.get('num', '#')}</span>
                            <span style="color:white; font-weight:500;">{item.get('name')}</span>
                        </div>
                        """
                    st.markdown(html, unsafe_allow_html=True)
                
                # MODO GRID (PELIS/SERIES)
                else:
                    cols = st.columns(5)
                    for idx, item in enumerate(results[:50]):
                        with cols[idx % 5]:
                            img_url = item.get('stream_icon') or item.get('cover')
                            final_img = proxy_img(img_url)
                            st.markdown(f"""
                            <div class="vod-card-container">
                                <img src="{final_img}" class="vod-img" loading="lazy">
                                <div class="vod-title" title="{item.get('name')}">
                                    {item.get('name')}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ No se encontraron coincidencias.")
        except Exception as e:
            st.error(f"Error de conexión con el proveedor: {e}")
else:
    st.info("👆 Usa el buscador para encontrar contenido.")
