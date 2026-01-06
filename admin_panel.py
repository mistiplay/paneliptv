import streamlit as st
import pandas as pd
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="☁️ Admin Panel", page_icon="⚙️", layout="centered")

# 🔴 PEGA TU ENLACE DE GOOGLE SHEETS AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1lyj55UiweI75ej3hbPxvsxlqv2iKWEkKTzEmAvoF6lI/edit"

# --- CONEXIÓN SEGURA A LA NUBE ---
def connect_db():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # Lee credenciales desde los Secretos de Streamlit Cloud
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1
        return sheet
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        st.stop()

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- INTERFAZ ---
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    div[data-testid="stForm"] { background-color: #2d2d2d; padding: 20px; border-radius: 10px; }
    .stButton>button { width: 100%; background-color: #00C6FF; color: white; border:none; font-weight:bold;}
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("⚙️ Gestión de Usuarios (Nube)")

    # 1. LOGIN DEL ADMINISTRADOR (Protege tu panel en la nube)
    if 'admin_ok' not in st.session_state: st.session_state.admin_ok = False

    if not st.session_state.admin_ok:
        pwd = st.text_input("🔒 Contraseña Maestra", type="password")
        if st.button("Entrar"):
            # CAMBIA "admin123" POR TU CLAVE SEGURA
            if pwd == "franchesca92": 
                st.session_state.admin_ok = True
                st.rerun()
            else: st.error("Acceso denegado")
        st.stop()

    # 2. CARGAR DATOS EN VIVO
    sheet = connect_db()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    st.success(f"Conectado a Google Sheets | Usuarios: {len(df)}")

    tab1, tab2 = st.tabs(["👥 Lista y Editar", "➕ Crear Nuevo"])

    with tab1:
        if not df.empty:
            # Mostrar tabla limpia
            st.dataframe(df[['username', 'allowed_ip', 'notas']], use_container_width=True)
            
            # Selector para editar
            user_select = st.selectbox("Editar usuario:", df['username'].tolist())
            if user_select:
                # Buscar fila exacta (Google Sheets usa base 1, +1 por encabezado)
                cell = sheet.find(user_select)
                row_idx = cell.row
                user_info = df[df['username'] == user_select].iloc[0]

                with st.form("edit_form"):
                    st.write(f"Editando: **{user_select}**")
                    new_ip = st.text_input("IP Permitida", value=user_info['allowed_ip'])
                    new_note = st.text_input("Notas", value=user_info['notas'])
                    new_pass = st.text_input("Cambiar Contraseña (Opcional)", type="password")
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        with st.spinner("Actualizando nube..."):
                            sheet.update_cell(row_idx, 3, new_ip) # Col 3 = IP
                            sheet.update_cell(row_idx, 4, new_note) # Col 4 = Notas
                            if new_pass:
                                sheet.update_cell(row_idx, 2, make_hash(new_pass)) # Col 2 = Pass
                            st.success("¡Guardado!")
                            time.sleep(1)
                            st.rerun()
                
                if st.button("🗑️ Eliminar Usuario"):
                    sheet.delete_rows(row_idx)
                    st.warning("Usuario eliminado.")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("No hay usuarios todavía.")

    with tab2:
        with st.form("add_form"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            i = st.text_input("IP Permitida (Ej: 190.23.12.1)")
            n = st.text_input("Notas")
            
            if st.form_submit_button("🚀 Crear Usuario"):
                if u and p and i:
                    # Verificar duplicados
                    if u in df['username'].values:
                        st.error("¡El usuario ya existe!")
                    else:
                        with st.spinner("Creando..."):
                            sheet.append_row([u, make_hash(p), i, n])
                            st.success("Usuario creado exitosamente.")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.warning("Completa usuario, contraseña e IP.")

if __name__ == '__main__':

    main()
