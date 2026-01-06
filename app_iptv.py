import streamlit as st
import requests
import hashlib
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_javascript import st_javascript
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="IPTV Player Cloud", layout="wide", page_icon="📺")

# 🔴 TU ID DE GOOGLE SHEETS
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# 2. ESTILOS VISUALES (VERSIÓN ORIGINAL GRID/CARPETAS)
st.markdown("""
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp {
        background-color: #0e0e0e;
        background-image: radial-gradient(circle at center, #1a1a1a 0%, #000 100%);
        color: white;
    }
    div[data-testid="stForm"] {
        background-color: rgba(20, 20, 20, 0.95);
        padding: 30px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    .stTextInput > div > div > input {
        background-color: #222; color: white; border: 1px solid #444;
    }
    .stButton > button {
        width: 100%; background-color: #0069d9; color: white; border: none;
        font-weight: 600; text-transform: uppercase; height: 45px;
    }
    .stButton > button:hover { background-color: #0056b3; }
    
    /* VOD CARD GRID */
    .vod-card {
        background-color: #1e1e1e; border-radius: 6px; overflow: hidden;
        margin-bottom: 15px; border: 1px solid #333; position: relative;
    }
    .vod-img-box {
        width: 100%; padding-top: 150%; position: relative;
    }
    .vod-img {
        position: absolute; top: 0; left: 0; bottom: 0; right: 0;
        width: 100%; height: 100%; object-fit: cover;
    }
    .vod-info { padding: 8px; text-align: center; background: rgba(0,0,0,0.8); }
    .vod-title { font-size: 11px; font-weight: bold; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .vod-cat { font-size: 9px; color: #00C6FF; margin-top: 2px; }
    
    /* CANALES */
    .channel-row {
        background-color: rgba(40, 40, 40, 0.5); padding: 8px 12px; margin-bottom: 5px;
        border-radius: 4px; border-left: 3px solid #0069d9; display: flex; align-items: center; font-size: 13px;
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

def proxy_img(url):
    if not url or not url.startswith('http'): return "https://via.placeholder.com/200x300?text=No+Img"
    return f"https://wsrv.nl/?url={url}&w=150&h=225&fit=cover&output=webp"

# --- ESTADO ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'iptv_data' not in st.session_state: st.session_state.iptv_data = None
if 'mode' not in st.session_state: st.session_state.mode = 'live'
if 'data_live' not in st.session_state: st.session_state.data_live = None
if 'data_vod' not in st.session_state: st.session_state.data_vod = None
if 'data_series' not in st.session_state: st.session_state.data_series = None

# ==============================================================================
#  PANTALLA A: LOGIN (NON-BLOCKING)
# ==============================================================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        # 1. EJECUTAR JS PARA IP (SIN BLOQUEAR UI)
        try:
            url_ip = 'https://api.ipify.org'
            ip_js = st_javascript(f"await fetch('{url_ip}').then(r => r.text())")
        except: ip_js = None

        # 2. MOSTRAR LOGIN DIRECTAMENTE
        with st.form("login_form"):
            st.markdown("<h2 style='text-align:center; color:white;'>🔐 CLIENT ACCESS</h2>", unsafe_allow_html=True)
            
            # Mostrar estado de IP visualmente
            if ip_js and len(str(ip_js)) > 6:
                st.success(f"📡 IP Verificada: {ip_js}")
            else:
                st.warning("⏳ Detectando IP... (Puedes escribir tus datos mientras)")

            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            btn = st.form_submit_button("INICIAR SESIÓN")
            
            if btn:
                # Validar IP al momento de dar click
                if not ip_js or len(str(ip_js)) < 6:
                    st.error("⚠️ Aún no se detecta tu IP. Espera unos segundos y vuelve a dar click.")
                    st.stop()
                
                hashed_pw = hashlib.sha256(str.encode(p)).hexdigest()
                users_db = get_users_from_cloud()
                
                if not users_db:
                    st.error("Error de conexión con la base de datos.")
                    st.stop()

                found = False
                for user in users_db:
                    if str(user['username']) == u and str(user['password']) == hashed_pw:
                        if str(user['allowed_ip']) == ip_js:
                            st.session_state.logged_in = True
                            st.session_state.admin_user = u
                            st.rerun()
                        else:
                            st.error(f"⛔ IP NO AUTORIZADA ({ip_js})")
                            found = True; break
                        found = True
                
                if not found: st.error("❌ Credenciales incorrectas.")
    st.stop()

# ==============================================================================
#  PANTALLA B: CONEXIÓN (CON ANTI-BLOQUEO)
# ==============================================================================
if st.session_state.iptv_data is None:
    st.markdown("<br>", unsafe_allow_html=True)
    c_izq, c_cen, c_der = st.columns([1, 2, 1])
    with c_cen:
        with st.form("iptv_connect"):
            st.markdown(f"<p style='text-align:center; color:#888;'>Usuario: {st.session_state.admin_user}</p>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align:center; color:white;'>🔗 CONECTAR LISTA</h3>", unsafe_allow_html=True)
            
            url_input = st.text_input("Enlace M3U / URL").strip()
            submitted = st.form_submit_button("CONECTAR")
            
            if submitted:
                if "http" in url_input:
                    with st.spinner("⏳ Conectando al servidor..."):
                        try:
                            # 1. REEMPLAZO SIMPLE (Igual que en PC)
                            final_api = url_input.replace("/get.php", "/player_api.php").replace("/xmltv.php", "/player_api.php")
                            
                            # 2. MÁSCARA DE NAVEGADOR (CRUCIAL PARA TVDIRECT.PRO)
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                            }
                            
                            # 3. CONEXIÓN
                            res = requests.get(final_api, headers=headers, timeout=25)
                            
                            if res.status_code == 200:
                                try:
                                    data = res.json()
                                    if 'user_info' in data:
                                        st.session_state.iptv_data = {
                                            "api": final_api,
                                            "info": data['user_info']
                                        }
                                        # Resetear caches
                                        st.session_state.data_live = None
                                        st.session_state.data_vod = None
                                        st.session_state.data_series = None
                                        st.rerun()
                                    else:
                                        st.error("❌ Login fallido: Revisa usuario/contraseña en el enlace.")
                                except:
                                    # Si no es JSON, mostrar los primeros caracteres para entender qué pasó
                                    st.error(f"❌ Error: El servidor envió algo que no es JSON. (Respuesta: {res.text[:50]}...)")
                            else:
                                st.error(f"❌ Error HTTP {res.status_code}")
                        except Exception as e: st.error(f"❌ Error técnico: {e}")
                else: st.warning("URL inválida.")
    st.stop()

# ==============================================================================
#  PANTALLA C: DASHBOARD (VISUAL ORIGINAL)
# ==============================================================================
info = st.session_state.iptv_data['info']
api = st.session_state.iptv_data['api']

# HEADER
exp = "Indefinido"
if info.get('exp_date') and str(info.get('exp_date')) != 'null':
    exp = datetime.fromtimestamp(int(info['exp_date'])).strftime('%d/%m/%Y')

st.markdown(f"""
<div style="background: rgba(20,20,20,0.95); padding:10px 20px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0069d9; margin-bottom:15px;">
    <span style="font-weight:bold; color:white; font-size:18px;">IPTV PLAYER</span>
    <div style="font-size:11px; color:#ccc; text-align:right;">
        <div>USER: <b style="color:white">{info.get('username')}</b></div>
        <div>EXP: <b style="color:#00C6FF">{exp}</b> | STS: <b style="color:#00FF00">{info.get('status')}</b></div>
    </div>
</div>
""", unsafe_allow_html=True)

# MENÚ
c1, c2, c3, c4 = st.columns(4)
if c1.button("📡 TV EN VIVO"): st.session_state.mode = 'live'; st.rerun()
if c2.button("🎥 PELÍCULAS"): st.session_state.mode = 'vod'; st.rerun()
if c3.button("📺 SERIES"): st.session_state.mode = 'series'; st.rerun()
if c4.button("🔌 SALIR"): st.session_state.iptv_data = None; st.rerun()

# FUNCION DE CARGA
def fetch_data(act_content, act_cats):
    try:
        # USAR MISMOS HEADERS ANTI-BLOQUEO
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        u_cont = f"{api}&action={act_content}"
        u_cats = f"{api}&action={act_cats}"
        
        d = requests.get(u_cont, headers=headers, timeout=30).json()
        c = requests.get(u_cats, headers=headers, timeout=20).json()
        
        cmap = {str(x['category_id']): x['category_name'] for x in c}
        return d, cmap
    except: return [], {}

mode = st.session_state.mode

# LOGICA DE CARGA LAZY
if mode == 'live' and st.session_state.data_live is None:
    with st.spinner("Cargando Canales..."):
        st.session_state.data_live = fetch_data('get_live_streams', 'get_live_categories')
elif mode == 'vod' and st.session_state.data_vod is None:
    with st.spinner("Cargando Películas..."):
        st.session_state.data_vod = fetch_data('get_vod_streams', 'get_vod_categories')
elif mode == 'series' and st.session_state.data_series is None:
    with st.spinner("Cargando Series..."):
        st.session_state.data_series = fetch_data('get_series', 'get_series_categories')

# SELECCION
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
    query = st.text_input("🔍 Buscar Título").lower()

# APLICAR
filtered = data
if sel_cat != "Todas":
    t_ids = [k for k,v in cat_map.items() if v == sel_cat]
    if t_ids: filtered = [x for x in filtered if str(x.get('category_id')) in t_ids]
if query:
    filtered = [x for x in filtered if query in str(x.get('name')).lower()]

# RENDER
st.info(f"Resultados: {len(filtered)}")

if mode == 'live':
    html = ""
    for item in filtered[:100]:
        cname = cat_map.get(str(item.get('category_id')), "Gen")
        html += f"""
        <div class="channel-row">
            <div style="width:50px; color:#00C6FF; font-weight:bold;">{item.get('num', '#')}</div>
            <div style="flex-grow:1;">
                <div style="font-size:9px; color:#888;">{cname}</div>
                <div style="color:white; font-weight:500;">{item.get('name')}</div>
            </div>
        </div>"""
    st.markdown(html, unsafe_allow_html=True)
else:
    limit = 60
    view = filtered[:limit]
    cols = st.columns(6)
    for i, item in enumerate(view):
        with cols[i % 6]:
            img = proxy_img(item.get('stream_icon') or item.get('cover'))
            cat = cat_map.get(str(item.get('category_id')), "VOD")
            st.markdown(f"""
            <div class="vod-card">
                <div class="vod-img-box"><img src="{img}" class="vod-img" loading="lazy"></div>
                <div class="vod-info">
                    <div class="vod-title" title="{item.get('name')}">{item.get('name')}</div>
                    <div class="vod-cat">📂 {cat}</div>
                </div>
            </div>""", unsafe_allow_html=True)
    if len(filtered) > limit: st.warning(f"Mostrando primeros {limit}. Usa el buscador.")
