import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
from streamlit_javascript import st_javascript

# CONFIGURACIÓN
st.set_page_config(page_title="Admin Panel", page_icon="⚙️", layout="wide")

# 🔴 PEGA TU ENLACE DE GOOGLE SHEETS AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# --- 🎨 ESTILOS VISUALES ---
st.markdown("""
    <style>
    /* TAPAR ELEMENTOS DE ARRIBA */
    #MainMenu, header, footer {visibility: hidden;}
    
    .stApp { background-color: #0e0e0e; color: white; }
    div[data-testid="stForm"] { 
        background-color: #1e1e1e; padding: 25px; border-radius: 10px; border: 1px solid #333; 
    }
    .stTextInput>div>div>input { background-color: #2d2d2d; color: white; border: 1px solid #555; }
    .stButton>button { 
        width: 100%; background-color: #0069d9; color: white; border: none; font-weight: bold; 
        height: 45px; transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #0b5ed7; box-shadow: 0 4px 12px rgba(13, 110, 253, 0.4);
    }
    
    div[data-testid="stDataFrame"] { background-color: #1e1e1e; border-radius: 5px; }
    
    /* BADGE ADMIN */
    .admin-badge {
        display: inline-block;
        background-color: rgba(255, 193, 7, 0.2);
        border: 2px solid #FFC107;
        color: #FFC107;
        padding: 10px 16px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        margin: 10px 0;
        text-transform: uppercase;
    }
    
    /* IP BADGE */
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
    
    /* SPINNER */
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
    
    /* CONEXIÓN ROW */
    .conexion-row {
        background-color: rgba(30, 30, 30, 0.95);
        border: 1px solid #333;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .conexion-row:hover {
        border-color: #00C6FF;
        box-shadow: 0 0 15px rgba(0, 198, 255, 0.2);
    }
    .conexion-field {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        font-size: 13px;
    }
    .conexion-label {
        color: #00C6FF;
        font-weight: 600;
        min-width: 150px;
    }
    .conexion-value {
        color: white;
        background-color: rgba(0, 198, 255, 0.1);
        padding: 6px 12px;
        border-radius: 4px;
        flex-grow: 1;
        font-family: monospace;
        word-break: break-all;
    }
    
    /* INFO PANEL */
    .info-panel {
        background-color: rgba(20, 20, 20, 0.95);
        border: 2px solid #00C6FF;
        border-radius: 10px;
        padding: 20px;
    }
    .info-field {
        margin-bottom: 15px;
        padding-bottom: 15px;
        border-bottom: 1px solid rgba(0, 198, 255, 0.2);
    }
    .info-field:last-child {
        border-bottom: none;
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .info-label {
        color: #00C6FF;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 5px;
        letter-spacing: 0.5px;
    }
    .info-value {
        color: white;
        font-size: 14px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE VARIABLES ---
if 'admin_ok' not in st.session_state: 
    st.session_state.admin_ok = False
if 'user_ip' not in st.session_state: 
    st.session_state.user_ip = None
if 'ip_loading' not in st.session_state: 
    st.session_state.ip_loading = True
if 'selected_connection_detail' not in st.session_state:
    st.session_state.selected_connection_detail = None

# --- FUNCIONES ---
def connect_db():
    """Conecta a Google Sheets HOJA 1 (Usuarios)"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1
        return sheet
    except Exception as e:
        st.error(f"Error Sheets: {e}")
        st.stop()

def connect_db_conexiones():
    """Conecta a Google Sheets HOJA 2 (Conexiones)"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(SHEET_URL)
        
        try:
            sheet2 = spreadsheet.get_worksheet(1)
        except:
            sheet2 = spreadsheet.add_worksheet(title="Conexiones", rows=100, cols=5)
        
        return sheet2
    except:
        return None

def get_my_ip():
    """Detecta IP Real del cliente via JavaScript"""
    try:
        url = 'https://api.ipify.org'
        ip_js = st_javascript(f"await fetch('{url}').then(r => r.text())")
        if ip_js and isinstance(ip_js, str) and len(ip_js) > 6: 
            return ip_js
        return None
    except: 
        return None

def check_ip_is_admin(ip):
    """Verifica si la IP coincide con admin_ip en secrets"""
    try:
        admin_ip = st.secrets["general"]["admin_ip"]
        return ip == admin_ip
    except:
        return False

# --- INTERFAZ ---
st.markdown("<h1 style='text-align:center; color:#00C6FF;'>⚙️ PANEL MAESTRO</h1>", unsafe_allow_html=True)

# 1. DETECCIÓN DE IP
if st.session_state.user_ip is None and st.session_state.ip_loading:
    ip = get_my_ip()
    if ip: 
        st.session_state.user_ip = ip
        st.session_state.ip_loading = False
        st.rerun()

# 2. LOGIN POR IP
if not st.session_state.admin_ok:
    if st.session_state.user_ip:
        st.markdown(f'<div class="ip-badge">IP Detectada: {st.session_state.user_ip}</div>', unsafe_allow_html=True)
        
        if st.button("Verificar Acceso"):
            if check_ip_is_admin(st.session_state.user_ip):
                st.session_state.admin_ok = True
                st.rerun()
            else: 
                st.error(f"❌ IP no autorizada: {st.session_state.user_ip}")
    else:
        st.markdown("""
            <div style="text-align:center; margin:15px 0;">
                <span class="loading-spinner"></span>
                <span style="color:#00C6FF; font-size:13px;">Detectando IP...</span>
            </div>
        """, unsafe_allow_html=True)
    st.stop()

# 3. MOSTRAR BADGE SI ES ADMIN
st.markdown(f'<div class="admin-badge">🔐 ADMIN MODE - IP: {st.session_state.user_ip}</div>', unsafe_allow_html=True)

# 4. CARGAR DATOS
sheet = connect_db()
df = pd.DataFrame(sheet.get_all_records())

st.info(f"Usuarios activos: {len(df)}")

# TABS
tab1, tab2, tab3 = st.tabs(["📝 Gestionar", "➕ Nuevo Usuario", "📊 Conexiones"])

# ========== TAB 1: GESTIONAR USUARIOS ==========
with tab1:
    if not df.empty:
        st.dataframe(df[['username', 'allowed_ip', 'notas']], use_container_width=True)
        
        user_select = st.selectbox("Seleccionar Usuario para Editar/Borrar:", df['username'].tolist())
        
        if user_select:
            cell = sheet.find(user_select)
            row_idx = cell.row
            user_data = df[df['username'] == user_select].iloc[0]
            
            with st.form("edit"):
                st.write(f"Editando a: **{user_select}**")
                n_ip = st.text_input("IP", value=user_data['allowed_ip'])
                n_nota = st.text_input("Nota", value=user_data.get('notas', ''))
                
                if st.form_submit_button("💾 Guardar Cambios"):
                    sheet.update_cell(row_idx, 2, n_ip)
                    sheet.update_cell(row_idx, 3, n_nota)
                    st.success("✅ Actualizado.")
                    time.sleep(1)
                    st.rerun()
            
            if st.button("🗑️ Eliminar Usuario Permanentemente"):
                sheet.delete_rows(row_idx)
                st.warning("⚠️ Eliminado.")
                time.sleep(1)
                st.rerun()
    else:
        st.warning("La base de datos está vacía.")

# ========== TAB 2: CREAR NUEVO USUARIO ==========
with tab2:
    st.markdown("<h3>➕ Crear Nuevo Usuario</h3>", unsafe_allow_html=True)
    st.info("💡 Solo USERNAME e IP (sin contraseña)")
    
    with st.form("add"):
        c1, c2 = st.columns(2)
        u = c1.text_input("Usuario")
        i = c2.text_input("IP Permitida")
        n = st.text_input("Notas (Cliente)")
        
        if st.form_submit_button("✅ Crear Usuario"):
            if u and i:
                if not df.empty and u in df['username'].values:
                    st.error("❌ El usuario ya existe.")
                else:
                    sheet.append_row([u, i, n])
                    st.success(f"✅ Usuario '{u}' creado correctamente.")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("⚠️ Faltan datos obligatorios (Usuario e IP).")

# ========== TAB 3: VER CONEXIONES (HOJA 2) ==========
with tab3:
    st.markdown("<h3>📊 Conexiones Registradas (Hoja 2)</h3>", unsafe_allow_html=True)
    
    sheet2 = connect_db_conexiones()
    
    if sheet2:
        conexiones = sheet2.get_all_records()
        
        if not conexiones:
            st.warning("⚠️ No hay conexiones registradas aún.")
        else:
            # DEDUPLICAR por usuario_iptv (mantener primera aparición)
            seen = set()
            conexiones_unicas = []
            for conn in conexiones:
                usuario = conn.get('usuario_iptv', '')
                if usuario and usuario not in seen:
                    seen.add(usuario)
                    conexiones_unicas.append(conn)
            
            st.info(f"Total de conexiones únicas: {len(conexiones_unicas)}")
            
            col_list, col_info = st.columns([1.5, 1])
            
            with col_list:
                st.markdown("**📊 Lista de Conexiones:**")
                
                # Listar conexiones
                for idx, conn in enumerate(conexiones_unicas):
                    username_login = conn.get('username_login', 'N/A')
                    usuario_iptv = conn.get('usuario_iptv', 'N/A')
                    password_iptv = conn.get('password_iptv', 'N/A')
                    dominio_puerto = conn.get('dominio:puerto', 'N/A')
                    timestamp = conn.get('timestamp', 'N/A')
                    
                    # Layout: datos + botón info
                    col_data, col_btn = st.columns([4, 1])
                    
                    with col_data:
                        html_conn = f"""
                        <div class="conexion-row">
                            <div class="conexion-field">
                                <span class="conexion-label">👤 Username Login:</span>
                                <span class="conexion-value">{username_login}</span>
                            </div>
                            <div class="conexion-field">
                                <span class="conexion-label">📱 Usuario IPTV:</span>
                                <span class="conexion-value">{usuario_iptv}</span>
                            </div>
                            <div class="conexion-field">
                                <span class="conexion-label">🔐 Password IPTV:</span>
                                <span class="conexion-value">{password_iptv}</span>
                            </div>
                            <div class="conexion-field">
                                <span class="conexion-label">🌐 Dominio:Puerto:</span>
                                <span class="conexion-value">{dominio_puerto}</span>
                            </div>
                            <div class="conexion-field">
                                <span class="conexion-label">📅 Timestamp:</span>
                                <span class="conexion-value">{timestamp}</span>
                            </div>
                        </div>
                        """
                        st.markdown(html_conn, unsafe_allow_html=True)
                    
                    with col_btn:
                        # Botón ℹ️ para ver detalles
                        if st.button("ℹ️", key=f"info_btn_{idx}", help="Ver detalles"):
                            st.session_state.selected_connection_detail = conn
                            st.rerun()
            
            with col_info:
                st.markdown("**ℹ️ Detalles:**")
                
                if st.session_state.selected_connection_detail:
                    conn_sel = st.session_state.selected_connection_detail
                    
                    # Obtener datos de la API (info del usuario IPTV)
                    usuario_iptv = conn_sel.get('usuario_iptv', '')
                    password_iptv = conn_sel.get('password_iptv', '')
                    dominio_puerto = conn_sel.get('dominio:puerto', '')
                    
                    # Construir URL de API
                    try:
                        api_url = f"http://{dominio_puerto}/player_api.php?username={usuario_iptv}&password={password_iptv}"
                        
                        headers = {"User-Agent": "Mozilla/5.0"}
                        res = requests.get(api_url, headers=headers, timeout=10)
                        
                        if res.status_code == 200:
                            data = res.json()
                            user_info = data.get('user_info', {})
                            
                            # Extraer información
                            status = user_info.get('status', 'Desconocido')
                            exp_date = user_info.get('exp_date')
                            active_cons = user_info.get('active_cons', '0')
                            max_cons = user_info.get('max_connections', '?')
                            
                            # Formatear fecha
                            if exp_date and str(exp_date) != 'null':
                                try:
                                    exp_formatted = datetime.fromtimestamp(int(exp_date)).strftime('%d/%m/%Y')
                                except:
                                    exp_formatted = "N/A"
                            else:
                                exp_formatted = "Indefinido"
                            
                            # Color estado
                            color_estado = "#00FF00" if status == "Active" else "#FF6B6B"
                            
                            # Renderizar panel
                            st.markdown(f"""
                            <div class="info-panel">
                                <div class="info-field">
                                    <div class="info-label">📊 Estado</div>
                                    <div class="info-value" style="color:{color_estado};">🟢 {status}</div>
                                </div>
                                <div class="info-field">
                                    <div class="info-label">📆 Vencimiento</div>
                                    <div class="info-value">{exp_formatted}</div>
                                </div>
                                <div class="info-field">
                                    <div class="info-label">🔗 Conexiones</div>
                                    <div class="info-value">{active_cons}/{max_cons}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ No se pudo obtener info de la API")
                    except Exception as e:
                        st.warning(f"⚠️ Error conectando: {str(e)}")
                    
                    # Botón para cerrar
                    if st.button("✕ Cerrar", use_container_width=True):
                        st.session_state.selected_connection_detail = None
                        st.rerun()
                else:
                    st.markdown("<p style='color:#aaa; text-align:center; margin-top:30px;'>👆 Haz clic en ℹ️<br>para ver detalles</p>", unsafe_allow_html=True)
    else:
        st.error("❌ Error al conectar con Hoja 2")
