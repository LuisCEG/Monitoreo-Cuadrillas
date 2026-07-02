import streamlit as st
from datetime import datetime
import requests
import base64
import gspread
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation

# =====================================================================
# CONFIGURACIÓN DE CONEXIONES Y SEGURIDAD
# =====================================================================

SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
IMGBB_API_KEY = st.secrets["general"]["imgbb_api_key"]

@st.cache_resource
def inicializar_conexiones():
    """Inicializa la conexión con Google Sheets."""
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client_gspread = gspread.authorize(creds)
    return client_gspread

try:
    gc = inicializar_conexiones()
except Exception as e:
    st.error(f"Error técnico de conexión: {e}")
    st.stop()

# =====================================================================
# INTERFAZ DE USUARIO (STREAMLIT)
# =====================================================================

st.set_page_config(page_title="Centro de Gestión - Monitoreo", page_icon="👷‍♂️", layout="centered")
st.title("Reporte de Operaciones en Campo 👷‍♂️")
st.markdown("---")

# 1. Datos Generales
st.subheader("1. Información del Frente de Trabajo")
cuadrilla = st.selectbox("Seleccione la Cuadrilla", [
    "Cuadrilla 1 - Instalaciones", 
    "Cuadrilla 2 - Montajes", 
    "Cuadrilla 3 - Eje Cafetero / Mantenimiento"
])
direccion = st.text_input("Proyecto / Dirección", placeholder="Ej: Proyecto Dosquebradas, Hotel Aimarawa...")

st.markdown("---")

# 2. Geolocalización Automática
st.subheader("2. Validación de Ubicación (GPS)")
st.write("Haz clic en el botón para capturar las coordenadas exactas:")

ubicacion = streamlit_geolocation()
gps_coordenadas = None

if ubicacion['latitude'] is not None and ubicacion['longitude'] is not None:
    # Convertimos las coordenadas en un enlace directo de Google Maps
    gps_coordenadas = f"https://www.google.com/maps?q={ubicacion['latitude']},{ubicacion['longitude']}"
    st.success("📍 Ubicación confirmada y convertida a enlace de mapa.")
else:
    st.info("Esperando captura de GPS... (Recuerda dar permisos de ubicación en tu navegador)")

st.markdown("---")

# 3. Evidencia Fotográfica y Registro de Hora Automático
st.subheader("3. Evidencia y Registro de Tiempos")
st.write("Al tomar la fotografía, el sistema registrará automáticamente la hora de llegada.")

if 'hora_llegada' not in st.session_state:
    st.session_state['hora_llegada'] = None
if 'hora_salida' not in st.session_state:
    st.session_state['hora_salida'] = None

foto = st.camera_input("Capturar fotografía del avance o estado del sitio", key="camara_evidencia")

if foto:
    if st.session_state['hora_llegada'] is None:
        st.session_state['hora_llegada'] = datetime.now().strftime("%H:%M:%S")
    st.success(f"📸 Evidencia capturada. Hora de llegada registrada: {st.session_state['hora_llegada']}")

st.markdown("---")

# 4. Botón opcional de Salida
st.write("¿Terminó el turno?")
if st.button("🔴 Registrar Hora de Salida", use_container_width=True):
    st.session_state['hora_salida'] = datetime.now().strftime("%H:%M:%S")
    st.error(f"Salida registrada: {st.session_state['hora_salida']}")

st.markdown("---")

# =====================================================================
# PROCESAMIENTO Y ENVÍO DE DATOS
# =====================================================================
if st.button("🚀 Enviar Reporte al Centro de Gestión", type="primary", use_container_width=True):
    if not direccion or not foto or not st.session_state['hora_llegada'] or not gps_coordenadas:
        st.warning("⚠️ Datos incompletos. Asegúrate de ingresar la dirección, tomar la foto y capturar el GPS.")
    else:
        with st.spinner("Subiendo evidencia fotográfica y registrando datos..."):
            try:
                # A. Subir la imagen a ImgBB mediante API
                foto_bytes = foto.getvalue()
                foto_base64 = base64.b64encode(foto_bytes).decode('utf-8')
                
                url_imgbb = "https://api.imgbb.com/1/upload"
                payload = {
                    "key": IMGBB_API_KEY,
                    "image": foto_base64
                }
                
                respuesta_api = requests.post(url_imgbb, data=payload).json()
                enlace_foto = respuesta_api["data"]["url"]
                
                # B. Escribir los registros en Google Sheets
                hoja = gc.open_by_key(SPREADSHEET_ID).sheet1
                fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                
                fila_nueva = [
                    fecha_hoy,
                    cuadrilla,
                    direccion,
                    st.session_state['hora_llegada'],
                    st.session_state['hora_salida'] if st.session_state['hora_salida'] else "No registrada",
                    gps_coordenadas,
                    enlace_foto
                ]
                
                hoja.append_row(fila_nueva)
                
                st.success("✅ ¡Reporte guardado exitosamente en el Centro de Gestión!")
                
                # Limpiar variables de tiempo para el próximo registro
                st.session_state['hora_llegada'] = None
                st.session_state['hora_salida'] = None
                
            except Exception as error:
                st.error(f"Ocurrió un error al enviar el reporte: {error}")
