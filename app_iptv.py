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
st.set_page_config(page_title="IPTV Player Cloud", layout="wide", page_icon="📺")

# 🔴 TU ID DE GOOGLE SHEETS
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# 2. CSS VISUAL (EL ORIGINAL QUE TE GUSTA)
st.markdown("""
    <style>
    /* Ocultar elementos nativos */
    #MainMenu, header, footer, .stAppDeployButton {visibility: hidden !important;}
    
    /* FONDO DE PANTALLA */
    .stApp {
        background-color: #111;
        background-image: radial-gradient(circle at center, #222 0%, #000 100%);
        color: white;
    }

    /* FORMULARIOS */
    div[data-testid="stForm"] {
        background-color: rgba(15, 15, 15, 0.95);
        padding: 40px;
        border-radius: 10px;
        border: 1px solid #333;
        box-shadow: 0 0 20px rgba(0,198,255,0.1);
    }

    /* INPUTS */
    .stTextInput > div > div > input {
        background-color: #222; color: white; border: 1px solid #444; border-radius: 4px;
    }

    /* BOTONES */
    .stButton > button {
        width: 100%; background-color: #0069d9; color: white; border: none;
        font-weight: 600; text-transform: uppercase; height: 45px; transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #0056b3; box-shadow: 0 0 15px rgba(0, 105, 217, 0.6);
    }

    /* --- HEADER INTERNO --- */
    .header-container {
        background-color: rgba(20, 20, 20, 0.95); padding: 15px 25px;
        border-radius: 10px; border-bottom: 2px solid #0069d9;
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    }
    .status-pill {
        display: flex; align-items: center; gap: 10px; 
        background-color: #222; padding: 5px 15px; border-radius: 20px; border: 1px solid #444;
    }

    /* --- GRID VOD --- */
    .vod-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 15px; width: 100%; margin-top: 20px;
    }
    .vod-card {
        background-color: rgba(30, 30, 30, 0.95); border-radius: 6px; overflow: hidden;
        border: 1px solid #333; display: flex; flex-direction: column; transition: transform 0.2s;
    }
    .vod-card:hover { transform: scale(1.03); border-color: #0069d9; }
    .vod-img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .vod-info { padding: 8px; text-align: center; }
    .vod-title { font-size: 12px; font-weight: bold; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .vod-cat { font-size: 10px; color: #00C6FF; margin-top: 2px;}

    /* --- CANALES --- */
    .channel-row {
        background-color: rgba(30, 30, 30, 0.6); padding: 8px 15px; margin-bottom: 5px; border-radius: 4px;
        border-left: 3px solid #0069d9; display: flex; align-items: center;
    }
    </style>
""", unsafe_allow_html=True)

# 3. CONEXIÓN SEGURA Y UTILIDADES

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

def proxy_img(url):
    if not url or not url.startswith('http'): return "https://via.placeholder.com/150x225?text=No+Img"
    return f"https://wsrv.nl/?url={url}&w=150&h=225&fit=cover&output=webp"

# --- ESTADO DE SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'iptv_data' not in st.session_state: st.session_state.iptv_data = None
if 'menu_actual' not in st.session_state: st.session_state.menu_actual = "📡 Canales"
# Variable para guardar la IP y evitar recargas infinitas
if 'user_ip' not in st.session_state: st.session_state.user_ip = None

# ==============================================================================
#  PANTALLA A: LOGIN (SOLUCIÓN DOBLE CLIC)
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        # 1. DETECCIÓN DE IP (ANTES DE MOSTRAR NADA)
        if st.session_state.user_ip is None:
            st.warning("⏳ Conectando de forma segura...")
            try:
                url_ip = 'https://api.ipify.org'
                ip_js = st_javascript(f"await fetch('{url_ip}').then(r => r.text())")
                if ip_js and isinstance(ip_js, str) and len(ip_js) > 6:
                    st.session_state.user_ip = ip_js
                    st.rerun() # Recargamos UNA vez para guardar la IP
            except: pass
            st.stop() # Detenemos ejecución hasta tener IP
        
        # 2. SI YA TENEMOS IP, MOSTRAMOS LOGIN (ESTABLE)
        with st.form("security_login"):
            st.markdown("<h2 style='text-align:center; color:white;'>🔐 ACCESO SEGURO</h2>", unsafe_allow_html=True)
            st.caption(f"IP Verificada: {st.session_state.user_ip}")
            
            user = st.text_input("Usuario")
            passw = st.text_input("Contraseña", type="password")
            btn = st.form_submit_button("INGRESAR")
            
            if btn:
                hashed_pw = hashlib.sha256(str.encode(passw)).hexdigest()
                users_db = get_users_from_cloud()
                
                found = False
                for u_db in users_db:
                    if str(u_db['username']) == user and str(u_db['password']) == hashed_pw:
                        if str(u_db['allowed_ip']) == st.session_state.user_ip:
                            st.session_state.logged_in = True
                            st.session_state.admin_user = user
                            st.rerun()
                        else:
                            st.error(f"⛔ IP NO AUTORIZADA ({st.session_state.user_ip})")
                            found = True; break
                        found = True
                
                if not found: st.error("❌ Credenciales incorrectas.")
    st.stop()

# ==============================================================================
#  PANTALLA B: CONEXIÓN IPTV (URL SIMPLE)
# ==============================================================================
if st.session_state.iptv_data is None:
    st.markdown("<br>", unsafe_allow_html=True)
    c_izq, c_cen, c_der = st.columns([1, 2, 1])
    with c_cen:
        with st.form("iptv_connect"):
            st.markdown(f"<p style='text-align:center; color:#888;'>Bienvenido, {st.session_state.admin_user}</p>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align:center; color:white;'>🔗 CONECTAR LISTA</h3>", unsafe_allow_html=True)
            
            url_input = st.text_input("URL / Enlace M3U", placeholder="http://dominio.com:8080/get.php?username=...").strip()
            submitted = st.form_submit_button("CONECTAR")
            
            if submitted:
                if "http" in url_input:
                    with st.spinner("⏳ Conectando..."):
                        try:
                            # 1. LÓGICA SIMPLE (Reemplazo de texto como en PC)
                            final_api = url_input.replace("/get.php", "/player_api.php").replace("/xmltv.php", "/player_api.php")
                            
                            # 2. Header de Navegador (Evita bloqueos 403)
                            headers = {"User-Agent": "Mozilla/5.0"}
                            
                            # 3. Petición
                            res = requests.get(final_api, headers=headers, timeout=20)
                            
                            if res.status_code == 200:
                                try:
                                    data = res.json()
                                    if 'user_info' in data:
                                        # Guardar en sesión
                                        st.session_state.iptv_data = {
                                            "api": final_api,
                                            "info": data['user_info']
                                        }
                                        # Inicializar listas vacías
                                        st.session_state.live_list = []
                                        st.session_state.vod_list = []
                                        st.session_state.series_list = []
                                        st.rerun()
                                    else: st.error("❌ Login fallido (Revisa usuario/pass en la URL).")
                                except: st.error("❌ Error: El servidor no devolvió datos válidos.")
                            else: st.error(f"❌ Error HTTP {res.status_code}")
                        except Exception as e: st.error(f"❌ Error conexión: {e}")
                else: st.warning("URL inválida.")
    st.stop()

# ==============================================================================
#  PANTALLA C: DASHBOARD (TU CÓDIGO VISUAL RESTAURADO)
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# --- HEADER ---
exp = "Indefinido"
if info.get('exp_date') and str(info.get('exp_date')) != 'null':
    exp = datetime.fromtimestamp(int(info['exp_date'])).strftime('%d/%m/%Y')

st.markdown(f"""
<div class="header-container">
    <div style="font-weight:bold; font-size:20px; color:white;">🔍 CONTENT VIEWER</div>
    <div class="status-pill">
        <div style="text-align:right; line-height:1.2;">
            <div style="color:#aaa; font-size:10px;">CLIENTE</div>
            <div style="color:white; font-size:14px; font-weight:bold;">{info.get('username')}</div>
        </div>
        <div style="border-left:1px solid #444; padding-left:10px; line-height:1.2;">
            <div style="color:#aaa; font-size:10px;">VENCE</div>
            <div style="color:#00C6FF; font-size:12px;">{exp}</div>
        </div>
        <div style="border-left:1px solid #444; padding-left:10px; line-height:1.2;">
            <div style="color:#aaa; font-size:10px;">CONEXIONES</div>
            <div style="color:orange; font-size:12px;">{info.get('active_cons')} / {info.get('max_connections')}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- MENÚ ---
c1, c2, c3, c4 = st.columns(4)
if c1.button("📡 TV EN VIVO"): st.session_state.menu_actual = "📡 Canales"; st.rerun()
if c2.button("🎥 PELÍCULAS"): st.session_state.menu_actual = "🎥 Películas"; st.rerun()
if c3.button("📺 SERIES"): st.session_state.menu_actual = "📺 Series"; st.rerun()
if c4.button("🔌 SALIR"): st.session_state.iptv_data = None; st.rerun()

# --- BUSCADOR ---
st.markdown("---")
query = st.text_input(f"🔎 Buscar en {st.session_state.menu_actual}...", placeholder="Escribe para filtrar resultados...").lower()

# --- LÓGICA DE CARGA Y VISUALIZACIÓN ---
headers = {"User-Agent": "Mozilla/5.0"}

# 1. CANALES
if st.session_state.menu_actual == "📡 Canales":
    if not st.session_state.live_list:
        with st.spinner("Descargando canales..."):
            try:
                st.session_state.live_list = requests.get(f"{api}&action=get_live_streams", headers=headers, timeout=20).json()
                cats = requests.get(f"{api}&action=get_live_categories", headers=headers, timeout=15).json()
                st.session_state.live_cats = {c['category_id']: c['category_name'] for c in cats}
            except: pass

    if query:
        items = [x for x in st.session_state.live_list if query in str(x.get('name')).lower()]
        if not items: st.warning("No encontrado.")
        
        html = ""
        for i in items[:100]:
            cat_name = st.session_state.live_cats.get(i.get('category_id'), 'General')
            html += f"""
            <div class="channel-row">
                <span style="color:#00C6FF; font-weight:bold; width:50px;">{i.get('num', '0')}</span>
                <div>
                    <div style="font-size:9px; color:#888; text-transform:uppercase;">{cat_name}</div>
                    <div style="color:#eee; font-weight:500;">{i.get('name')}</div>
                </div>
            </div>"""
        st.markdown(html, unsafe_allow_html=True)
    else: st.info("👆 Usa el buscador.")

# 2. PELÍCULAS (CON CATEGORÍAS)
elif st.session_state.menu_actual == "🎥 Películas":
    if not st.session_state.vod_list:
        with st.spinner("Descargando películas..."):
            try:
                st.session_state.vod_list = requests.get(f"{api}&action=get_vod_streams", headers=headers, timeout=35).json()
                cats = requests.get(f"{api}&action=get_vod_categories", headers=headers, timeout=15).json()
                st.session_state.vod_cats = {c['category_id']: c['category_name'] for c in cats}
            except: pass

    if query:
        items = [x for x in st.session_state.vod_list if query in str(x.get('name')).lower()]
        if not items: st.warning("No encontrado.")
        else:
            st.success(f"Encontrados: {len(items)}")
            html = '<div class="vod-grid">'
            for item in items[:60]:
                img = proxy_img(item.get('stream_icon'))
                cat = st.session_state.vod_cats.get(item.get('category_id'), 'VOD')
                html += f"""
                <div class="vod-card">
                    <img src="{img}" class="vod-img" loading="lazy">
                    <div class="vod-info">
                        <div class="vod-title" title="{item.get('name')}">{item.get('name')}</div>
                        <div class="vod-cat">📂 {cat}</div>
                    </div>
                </div>"""
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
    else: st.info("👆 Escribe el nombre de la película.")

# 3. SERIES (CON CATEGORÍAS)
elif st.session_state.menu_actual == "📺 Series":
    if not st.session_state.series_list:
        with st.spinner("Descargando series..."):
            try:
                st.session_state.series_list = requests.get(f"{api}&action=get_series", headers=headers, timeout=35).json()
                cats = requests.get(f"{api}&action=get_series_categories", headers=headers, timeout=15).json()
                st.session_state.series_cats = {c['category_id']: c['category_name'] for c in cats}
            except: pass

    if query:
        items = [x for x in st.session_state.series_list if query in str(x.get('name')).lower()]
        if not items: st.warning("No encontrado.")
        else:
            st.success(f"Encontrados: {len(items)}")
            html = '<div class="vod-grid">'
            for item in items[:60]:
                img = proxy_img(item.get('cover'))
                cat = st.session_state.series_cats.get(item.get('category_id'), 'Series')
                html += f"""
                <div class="vod-card">
                    <img src="{img}" class="vod-img" loading="lazy">
                    <div class="vod-info">
                        <div class="vod-title" title="{item.get('name')}">{item.get('name')}</div>
                        <div class="vod-cat">📂 {cat}</div>
                    </div>
                </div>"""
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
    else: st.info("👆 Escribe el nombre de la serie.")
