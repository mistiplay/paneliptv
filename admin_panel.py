import streamlit as st
import pandas as pd
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from streamlit_javascript import st_javascript

# CONFIGURACIÓN
st.set_page_config(page_title="Admin Panel", page_icon="⚙️", layout="centered")

# 🔴 PEGA TU ENLACE DE GOOGLE SHEETS AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# --- 🎨 ESTILOS VISUALES ---
st.markdown("""
    <style>
    .stApp { background-color: #0e0e0e; color: white; }
    div[data-testid="stForm"] { 
        background-color: #1e1e1e; padding: 25px; border-radius: 10px; border: 1px solid #333; 
    }
    .stTextInput>div>div>input { background-color: #2d2d2d; color: white; border: 1px solid #555; }
    .stButton>button { 
        width: 100%; background-color: #0069d9; color: white; border: none; font-weight: bold; 
    }
    div[data-testid="stDataFrame"] { background-color: #1e1e1e; border-radius: 5px; }
    
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
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE VARIABLES ---
if 'admin_ok' not in st.session_state: 
    st.session_state.admin_ok = False
if 'is_admin' not in st.session_state: 
    st.session_state.is_admin = False
if 'user_ip' not in st.session_state: 
    st.session_state.user_ip = None
if 'ip_loading' not in st.session_state: 
    st.session_state.ip_loading = True

# --- FUNCIONES ---
def connect_db():
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

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

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

def check_is_admin(password):
    """Verifica si la contraseña es la de admin"""
    try:
        secret_pass = st.secrets["general"]["admin_password"]
        return password == secret_pass
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

# 2. LOGIN ADMIN
if not st.session_state.admin_ok:
    if st.session_state.user_ip:
        st.markdown(f'<div class="ip-badge">IP Detectada: {st.session_state.user_ip}</div>', unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style="text-align:center; margin:15px 0;">
                <span class="loading-spinner"></span>
                <span style="color:#00C6FF; font-size:13px;">Detectando IP...</span>
            </div>
        """, unsafe_allow_html=True)
    
    pwd = st.text_input("🔑 Clave de Administrador", type="password")
    if st.button("Entrar"):
        if check_is_admin(pwd):
            st.session_state.admin_ok = True
            st.session_state.is_admin = True
            st.rerun()
        else: 
            st.error("Clave incorrecta")
    st.stop()

# 3. MOSTRAR BADGE SI ES ADMIN
if st.session_state.is_admin:
    if st.session_state.user_ip:
        st.markdown(f'<div class="admin-badge">🔐 ADMIN MODE - IP: {st.session_state.user_ip}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="admin-badge">🔐 MODO ADMINISTRADOR</div>', unsafe_allow_html=True)

# 4. GESTIÓN
sheet = connect_db()
df = pd.DataFrame(sheet.get_all_records())

st.info(f"Usuarios activos: {len(df)}")

tab1, tab2 = st.tabs(["📝 Gestionar", "➕ Nuevo Usuario"])

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
                n_nota = st.text_input("Nota", value=user_data['notas'])
                n_pass = st.text_input("Nueva Contraseña (Opcional)", type="password")
                
                if st.form_submit_button("Guardar Cambios"):
                    sheet.update_cell(row_idx, 3, n_ip)
                    sheet.update_cell(row_idx, 4, n_nota)
                    if n_pass:
                        sheet.update_cell(row_idx, 2, make_hash(n_pass))
                    st.success("Actualizado.")
                    time.sleep(1)
                    st.rerun()
            
            if st.button("🗑️ Eliminar Usuario Permanentemente"):
                sheet.delete_rows(row_idx)
                st.warning("Eliminado.")
                time.sleep(1)
                st.rerun()
    else:
        st.warning("La base de datos está vacía.")

with tab2:
    with st.form("add"):
        c1, c2 = st.columns(2)
        u = c1.text_input("Usuario")
        p = c2.text_input("Contraseña", type="password")
        i = st.text_input("IP Permitida")
        n = st.text_input("Notas (Cliente)")
        
        if st.form_submit_button("Crear Usuario"):
            if u and p and i:
                if not df.empty and u in df['username'].values:
                    st.error("El usuario ya existe.")
                else:
                    sheet.append_row([u, make_hash(p), i, n])
                    st.success("Usuario creado.")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("Faltan datos obligatorios.")
