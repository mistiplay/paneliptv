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

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Buscador PRO", layout="wide", page_icon="📺")

# 🔴 TU ID DE GOOGLE SHEETS
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# 2. ESTILOS VISUALES (AJUSTADOS: TEXTOS MÁS GRANDES Y TARJETAS COMPACTAS)
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

    /* --- TARJETAS VOD (PELIS/SERIES) - DISEÑO COMPACTO --- */
    .vod-card {
        background-color: #151515; /* Fondo más oscuro para fundirse con la imagen */
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 15px;
        border: 1px solid #333;
        transition: transform 0.2s;
        position: relative;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    }
    .vod-card:hover {
        transform: scale(1.05);
        border-color: #00C6FF;
        z-index: 10;
        box-shadow: 0 5px 20px rgba(0,0,0,0.7);
    }
    /* Contenedor de imagen 2:3 EXACTO */
    .vod-img-box {
        width: 100%;
        padding-top: 150%; /* Esto fuerza el aspecto de póster */
        position: relative;
    }
    .vod-img {
        position: absolute;
        top: 0; left: 0; bottom: 0; right: 0;
        width: 100%; height: 100%;
        object-fit: cover; /* La imagen llena el espacio sin deformarse */
    }
    .vod-info {
        padding: 8px 5px; /* Padding reducido para que no sea tan alto */
        text-align: center;
        background: #1a1a1a;
        border-top: 1px solid #222;
    }
    .vod-title {
        font-size: 13px; /* AUMENTADO */
        font-weight: bold; 
        color: white;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        margin-bottom: 3px;
    }
    .vod-cat {
        font-size: 11px; /* AUMENTADO Y CLARO */
        color: #00C6FF; 
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        font-weight: 500;
    }

    /* --- LISTA CANALES --- */
    .channel-row {
        background-color: rgba(35, 35, 35, 0.6);
        padding: 12px 15px; /* Más espacio para respirar */
        margin-bottom: 6px;
        border-radius: 5px;
        border-left: 4px solid #0069d9;
        display: flex; 
        align-items: center; 
    }
    </style>
""", unsafe_allow_html=True)

# 3. FUNCIONES DE CONEXIÓN Y UTILIDAD

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
    """Detecta IP Real via JS (Non-Blocking)"""
    try:
        url = 'https://api.ipify.org'
        ip_js = st_javascript(f"await fetch('{url}').then(r => r.text())")
        if ip_js and isinstance(ip_js, str) and len(ip_js) > 6: 
            return ip_js
        return None
    except: return None

def proxy_img(url):
    """Proxy para imágenes http inseguras"""
    if not url or not url.startswith('http'): return "https://via.placeholder.com/200x300?text=No+Img"
    # Ajustado a 200x300 para el ratio 2:3 exacto
    return f"https://wsrv.nl/?url={url}&w=200&h=300&fit=cover&output=webp"

# --- ESTADO DE SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'iptv_data' not in st.session_state: st.session_state.iptv_data = None
if 'mode' not in st.session_state: st.session_state.mode = 'live'
# Cache local para datos
if 'data_live' not in st.session_state: st.session_state.data_live = None
if 'data_vod' not in st.session_state: st.session_state.data_vod = None
if 'data_series' not in st.session_state: st.session_state.data_series = None
# IP Cache
if 'user_ip_cached' not in st.session_state: st.session_state.user_ip_cached = None

# ==============================================================================
#  PANTALLA 1: LOGIN (ESTABILIZADO)
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        # Detectar IP sin bloquear
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
            btn = st.form_submit_button("INICIAR SESIÓN")
            
            if btn:
                # Validar IP
                if not st.session_state.user_ip_cached:
                    st.error("⚠️ Aún no se detecta tu IP. Espera 2 segundos y vuelve a dar clic.")
                    st.stop()

                hashed_input = hashlib.sha256(str.encode(p)).hexdigest()
                users_db = get_users_from_cloud()
                
                if not users_db:
                    st.error("⚠️ Error de conexión DB.")
                    st.stop()

                found = False
                for user in users_db:
                    if str(user['username']) == u and str(user['password']) == hashed_input:
                        if str(user['allowed_ip']) == st.session_state.user_ip_cached:
                            st.session_state.logged_in = True
                            st.session_state.admin_user = u
                            st.rerun()
                        else:
                            st.error(f"⛔ IP no autorizada ({st.session_state.user_ip_cached})")
                            found = True
                            break
                        found = True
                
                if not found:
                    st.error("❌ Credenciales incorrectas.")
    st.stop()

# ==============================================================================
#  PANTALLA 2: CONECTAR URL (SOLUCIÓN JSON/SERVER ERROR)
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
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                            }
                            
                            # Timeout aumentado a 25s
                            res = requests.get(final_api, headers=headers, timeout=25)
                            
                            if res.status_code == 200:
                                try:
                                    data = res.json()
                                    if isinstance(data, dict) and 'user_info' in data:
                                        st.session_state.iptv_data = {
                                            "api": final_api, 
                                            "info": data['user_info']
                                        }
                                        # Resetear caches de contenido
                                        st.session_state.data_live = None
                                        st.session_state.data_vod = None
                                        st.session_state.data_series = None
                                        st.rerun()
                                    else:
                                        st.error("❌ Login fallido: El enlace no contiene información de usuario válida.")
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
#  PANTALLA 3: DASHBOARD VISUAL (DISEÑO AJUSTADO)
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# --- HEADER MODIFICADO (TÍTULO CAMBIADO) ---
exp = "Indefinido"
if info.get('exp_date') and str(info.get('exp_date')) != 'null':
    try:
        exp = datetime.fromtimestamp(int(info['exp_date'])).strftime('%d/%m/%Y')
    except: pass

st.markdown(f"""
<div style="background: rgba(20,20,20,0.95); padding:10px 20px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0069d9; margin-bottom:15px;">
    <span style="font-weight:bold; color:white; font-size:18px;">BUSCADOR DE CONTENIDO PRO</span>
    <div style="font-size:11px; color:#ccc; text-align:right;">
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
    """Descarga contenido y categorías"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url_content = f"{api}&action={action_content}"
        url_cats = f"{api}&action={action_cats}"
        
        data = requests.get(url_content, headers=headers, timeout=30).json()
        cats = requests.get(url_cats, headers=headers, timeout=20).json()
        
        # Crear diccionario {category_id: "Nombre Carpeta"}
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

# Selección de datos
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

# 1. Filtro Carpeta
if sel_cat != "Todas":
    target_ids = [k for k, v in cat_map.items() if v == sel_cat]
    if target_ids:
        filtered = [x for x in filtered if str(x.get('category_id')) in target_ids]

# 2. Filtro Texto
if query:
    filtered = [x for x in filtered if query in str(x.get('name')).lower()]

# --- VISUALIZACIÓN ---
st.info(f"Mostrando {len(filtered)} resultados")

if mode == 'live':
    # LISTA PARA CANALES (LETRA AUMENTADA)
    html = ""
    for item in filtered[:100]:
        cat_name = cat_map.get(str(item.get('category_id')), "General")
        html += f"""
        <div class="channel-row">
            <div style="width:50px; color:#00C6FF; font-weight:bold; font-size:16px;">{item.get('num', '#')}</div>
            <div style="flex-grow:1;">
                <div style="font-size:11px; color:#aaa; text-transform:uppercase; font-weight:600; margin-bottom:2px;">{cat_name}</div>
                <div style="color:white; font-weight:500; font-size:15px;">{item.get('name')}</div>
            </div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)

else:
    # GRID PARA VOD (PELIS/SERIES) - DISEÑO COMPACTO Y TEXTO GRANDE
    limit = 60
    view_items = filtered[:limit]
    
    # 6 columnas para aspecto PC
    cols = st.columns(6)
    
    for i, item in enumerate(view_items):
        with cols[i % 6]:
            img = proxy_img(item.get('stream_icon') or item.get('cover'))
            title = item.get('name')
            folder_name = cat_map.get(str(item.get('category_id')), "VOD")
            
            st.markdown(f"""
            <div class="vod-card">
                <div class="vod-img-box">
                    <img src="{img}" class="vod-img" loading="lazy">
                </div>
                <div class="vod-info">
                    <div class="vod-title" title="{title}">{title}</div>
                    <div class="vod-cat">📂 {folder_name}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    if len(filtered) > limit:
        st.warning(f"⚠️ Mostrando los primeros {limit} resultados. Usa el buscador para ver más.")
