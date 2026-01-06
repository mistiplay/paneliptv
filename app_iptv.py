import streamlit as st
import requests
import time
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Maxplayer Search", layout="wide")

# 2. CSS VISUAL (ESTILO VOD COPIADO EXACTAMENTE DEL EJEMPLO)
st.markdown("""
    <style>
    /* Ocultar elementos nativos */
    #MainMenu, header, footer, .stAppDeployButton, [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stManageAppButton"] {
        visibility: hidden !important; display: none !important;
    }
    div[class*="viewerBadge"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }

    /* --- FONDO DE PANTALLA --- */
    .stApp {
        background-image: url("https://cdn.maxplayer.tv/demo/background.png");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }

    /* Ajuste contenedor */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 100% !important;
    }

    /* --- LOGIN CAJA (OSCURA Y CENTRADA) --- */
    div[data-testid="stForm"] {
        background-color: rgba(15, 15, 15, 0.90);
        padding: 40px;
        border-radius: 10px;
        border: 1px solid #333;
        box-shadow: 0 0 20px rgba(0,0,0,0.5);
    }
    
    /* LOGIN RESPONSIVO */
    @media (min-width: 768px) {
        div[data-testid="stForm"] { width: 450px !important; margin: 0 auto !important; }
    }
    @media (max-width: 767px) {
        div[data-testid="stForm"] { width: 95% !important; margin: 0 auto !important; }
    }
    
    /* --- BOTONES (AZUL) --- */
    .stButton > button {
        width: 100%; 
        border: none; 
        background-color: #0d6efd; 
        color: white; 
        border-radius: 5px;
        font-weight: 600;
        height: 45px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover { 
        background-color: #0b5ed7; 
        box-shadow: 0 4px 12px rgba(13, 110, 253, 0.4);
        color: white; 
    }

    /* --- HEADER INTERNO --- */
    .header-container {
        background-color: rgba(17, 17, 17, 0.95);
        padding: 12px 20px;
        border-radius: 10px;
        border: 1px solid #333;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    .user-pill {
        display: flex; align-items: center; gap: 10px; background-color: #222;
        padding: 5px 15px; border-radius: 20px; border: 1px solid #444;
    }

    /* --- GRID VOD (ESTILO EXACTO DEL EJEMPLO) --- */
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
    .vod-cat { font-size: 11px; color: #00C6FF; }

    /* --- CANALES --- */
    .channel-row {
        background-color: rgba(30, 30, 30, 0.95); padding: 10px; margin-bottom: 5px; border-radius: 5px;
        border-left: 4px solid #00C6FF; display: flex; align-items: center;
    }
    </style>
""", unsafe_allow_html=True)

# 3. SECRETOS
try:
    API_TOKEN = st.secrets["API_TOKEN"]
except:
    st.error("Error: Falta configurar API_TOKEN.")
    st.stop()

URL_API_MAXPLAYER = "https://api.maxplayer.tv/v3/api/public/users"

# Estado de sesión
if 'conectado' not in st.session_state: st.session_state.conectado = False
if 'menu_actual' not in st.session_state: st.session_state.menu_actual = "📡 Canales"
if 'lista_peliculas' not in st.session_state: st.session_state.lista_peliculas = []
if 'lista_series' not in st.session_state: st.session_state.lista_series = []
if 'cats_peliculas' not in st.session_state: st.session_state.cats_peliculas = {}
if 'cats_series' not in st.session_state: st.session_state.cats_series = {}

# --- PANTALLA 1: LOGIN ---
if not st.session_state.conectado:
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Columnas para centrar la caja en PC
    c_izq, c_cen, c_der = st.columns([1, 2, 1])
    
    with c_cen:
        with st.form("login_form"):
            # LOGO Y TEXTO
            st.markdown(f"""
                <div style="text-align: center; margin-bottom: 25px;">
                    <img src="https://my.maxplayer.tv/images/logomax.png" width="150">
                </div>
                <h4 style="text-align: center; color: white; margin-bottom: 25px; font-weight: normal;">Bienvenido</h4>
            """, unsafe_allow_html=True)
            
            # INPUT
            u_input = st.text_input("Usuario", placeholder="Ingrese su usuario").strip().lower()
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # BOTÓN
            submitted = st.form_submit_button("INICIAR SESIÓN", use_container_width=True)
            
            # ICONOS
            st.markdown(f"""
                <div style="text-align: center; margin-top: 30px; opacity: 0.9;">
                    <img src="https://i.postimg.cc/zfQL3S24/iconos.png" style="max-width: 100%; height: auto;">
                </div>
            """, unsafe_allow_html=True)
            
            if submitted:
                if not u_input:
                    st.warning("Por favor escriba un usuario.")
                else:
                    # LÓGICA DE VALIDACIÓN CON FEEDBACK VISUAL
                    with st.spinner("⏳ Validando credenciales..."):
                        try:
                            headers = {"Api-Token": API_TOKEN}
                            # 1. Buscamos en Maxplayer
                            res_max = requests.get(URL_API_MAXPLAYER, headers=headers, timeout=10).json()
                            usuarios = res_max.get('data', []) if isinstance(res_max, dict) else res_max
                            cliente = next((x for x in usuarios if str(x.get('username')).lower() == u_input), None)
                            
                            if cliente:
                                if cliente.get('status') == 0:
                                    st.error("❌ Cuenta deshabilitada por el administrador.")
                                else:
                                    iptv = cliente['lists'][0]['iptv_info']
                                    base_url = f"http://{iptv['fqdn']}:{iptv['port']}"
                                    api_check = f"{base_url}/player_api.php?username={iptv['username']}&password={iptv['password']}"
                                    
                                    # 2. Validamos estado IPTV
                                    try:
                                        r_check = requests.get(api_check, timeout=20)
                                        if r_check.status_code == 200:
                                            info = r_check.json().get('user_info', {})
                                            status_acc = info.get('status')
                                            exp_ts = info.get('exp_date')
                                            
                                            cuenta_valida = True
                                            if status_acc != "Active": cuenta_valida = False
                                            if exp_ts and str(exp_ts) != "null":
                                                if datetime.fromtimestamp(int(exp_ts)) < datetime.now():
                                                    cuenta_valida = False
                                            
                                            if cuenta_valida:
                                                # ÉXITO: Mensaje y Pausa
                                                msg_placeholder = st.empty()
                                                msg_placeholder.success("✅ ACCESO CONCEDIDO")
                                                time.sleep(1.5) # Pausa dramática solicitada
                                                
                                                st.session_state.user_name = u_input
                                                st.session_state.iptv = {"base": base_url, "u": iptv['username'], "p": iptv['password']}
                                                st.session_state.lista_peliculas = []
                                                st.session_state.lista_series = []
                                                st.session_state.conectado = True
                                                st.rerun()
                                            else:
                                                st.error("⛔ SU CUENTA HA VENCIDO. Contacte a soporte.")
                                        else:
                                            st.error("⚠️ Error de credenciales IPTV.")
                                    except Exception as e:
                                        st.error(f"⚠️ El servidor tarda demasiado en responder.")
                            else:
                                st.error("Usuario no encontrado.")
                        except Exception as e:
                            st.error(f"Error de conexión: {e}")

# --- PANTALLA 2: APP PRINCIPAL ---
else:
    data = st.session_state.iptv
    url_base = f"{data['base']}/player_api.php?username={data['u']}&password={data['p']}"
    
    # HEADER PROFESIONAL
    st.markdown(f"""
    <div class="header-container">
        <img src='https://my.maxplayer.tv/images/logomax.png' width='90'>
        <div class="user-pill">
            <span style="font-size: 20px;">👤</span>
            <div style="display:flex; flex-direction:column; line-height:1.1;">
                <span style="color:#888; font-size:10px;">Usuario</span>
                <span style="color:white; font-weight:bold; font-size:14px;">{st.session_state.user_name}</span>
            </div>
            <span style="color:#00FF00; font-size:10px;">●</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # MENÚ
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("📡 TV"): st.session_state.menu_actual = "📡 Canales"; st.rerun()
    if c2.button("🎥 Pelis"): st.session_state.menu_actual = "🎥 Películas"; st.rerun()
    if c3.button("📺 Series"): st.session_state.menu_actual = "📺 Series"; st.rerun()
    if c4.button("🚪 Salir"): st.session_state.conectado = False; st.rerun()

    # LOGICA CARGA
    if st.session_state.menu_actual == "🎥 Películas" and not st.session_state.lista_peliculas:
        with st.spinner("Descargando Películas..."):
            try:
                st.session_state.lista_peliculas = requests.get(f"{url_base}&action=get_vod_streams", timeout=30).json()
                cats = requests.get(f"{url_base}&action=get_vod_categories", timeout=20).json()
                st.session_state.cats_peliculas = {c['category_id']: c['category_name'] for c in cats}
            except: pass

    elif st.session_state.menu_actual == "📺 Series" and not st.session_state.lista_series:
        with st.spinner("Descargando Series..."):
            try:
                st.session_state.lista_series = requests.get(f"{url_base}&action=get_series", timeout=30).json()
                cats = requests.get(f"{url_base}&action=get_series_categories", timeout=20).json()
                st.session_state.cats_series = {c['category_id']: c['category_name'] for c in cats}
            except: pass

    # BUSCADOR
    st.markdown("---")
    c_in, c_bt = st.columns([0.85, 0.15])
    query = c_in.text_input("Buscador", placeholder=f"Buscar en {st.session_state.menu_actual}...", label_visibility="collapsed")
    c_bt.button("🔍")

    if query:
        query_lower = query.lower()

        # 1. CANALES
        if "Canales" in st.session_state.menu_actual:
            try:
                res = requests.get(f"{url_base}&action=get_live_streams", timeout=12).json()
                cats = {c['category_id']: c['category_name'] for c in requests.get(f"{url_base}&action=get_live_categories", timeout=12).json()}
                items = [x for x in res if query_lower in str(x.get('name')).lower()]
                
                if not items: st.warning("No encontrado.")
                
                html = ""
                for i in items[:50]:
                    cat_name = cats.get(i.get('category_id'), 'GRAL').upper()
                    html += f"""
                    <div class="channel-row">
                        <span style="color:white; font-weight:bold; width:40px;">{i.get('num', '0')}</span>
                        <div>
                            <div style="font-size:10px; color:#888;">{cat_name}</div>
                            <div style="color:#eee;">{i.get('name')}</div>
                        </div>
                    </div>"""
                st.markdown(html, unsafe_allow_html=True)
            except: st.error("Error obteniendo canales.")

        # 2. VOD (PELÍCULAS Y SERIES - DISEÑO EXACTO DEL EJEMPLO)
        else:
            es_peli = "Películas" in st.session_state.menu_actual
            lista = st.session_state.lista_peliculas if es_peli else st.session_state.lista_series
            categorias = st.session_state.cats_peliculas if es_peli else st.session_state.cats_series
            
            if not lista:
                st.warning("Lista vacía o error de carga.")
            else:
                items = [x for x in lista if query_lower in str(x.get('name')).lower()]
                
                if not items: 
                    st.warning("No encontrado.")
                else:
                    st.success(f"Encontrados: {len(items)}")
                    
                    # Generación HTML IDÉNTICA al ejemplo proporcionado
                    html = '<div class="vod-grid">'
                    for item in items[:60]:
                        img = item.get('stream_icon') or item.get('cover')
                        if not img or not img.startswith("http"): img = "https://via.placeholder.com/150x225?text=..."
                        
                        html += f"""
                        <div class="vod-card">
                            <img src="{img}" class="vod-img" loading="lazy">
                            <div class="vod-info">
                                <div class="vod-title">{item.get('name')}</div>
                                <div class="vod-cat">📂 {categorias.get(item.get('category_id'), '')}</div>
                            </div>
                        </div>"""
                    html += '</div>'
                    st.markdown(html, unsafe_allow_html=True)
