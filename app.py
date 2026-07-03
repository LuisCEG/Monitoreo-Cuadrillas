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

# Nuevo Selector de Hito Operativo
hito = st.selectbox("Seleccione el Hito Operativo", [
    "🌅 Inicio de Jornada",
    "🥪 Salida a Almuerzo",
    "🔄 Regreso de Almuerzo",
    "🛑 Fin de Jornada"
])

st.markdown("---")

# 2. Geolocalización Automática (CANDADO DE SEGURIDAD)
st.subheader("2. Validación de Ubicación (GPS)")
st.write("Es obligatorio capturar la ubicación satelital para continuar con el reporte.")

ubicacion = streamlit_geolocation()
gps_coordenadas = None

if ubicacion['latitude'] is not None and ubicacion['longitude'] is not None:
    # Convertimos de inmediato a enlace clickable de Google Maps
    gps_coordenadas = f"https://www.google.com/maps?q={ubicacion['latitude']},{ubicacion['longitude']}"
    st.success("📍 Ubicación satelital confirmada y vinculada al mapa.")
else:
    st.warning("⚠️ El GPS está apagado o esperando permisos. Activa la ubicación en tu celular para desbloquear la cámara.")
    st.stop() # <--- CANDADO: Si no hay GPS, el código se congela aquí y no muestra lo de abajo.

st.markdown("---")

# 3. Evidencia Fotográfica y Registro de Hora Automático
st.subheader("3. Evidencia y Registro de Tiempos")
st.write(f"Al capturar la foto, se registrará la hora exacta para el hito: **{hito}**")

if 'hora_registro' not in st.session_state:
    st.session_state['hora_registro'] = None

foto = st.camera_input("Capturar fotografía de evidencia en sitio", key="camara_evidencia")

if foto:
    if st.session_state['hora_registro'] is None:
        st.session_state['hora_registro'] = datetime.now().strftime("%H:%M:%S")
    st.success(f"📸 Foto capturada. Hora asignada al reporte: {st.session_state['hora_registro']}")

st.markdown("---")

# =====================================================================
# PROCESAMIENTO Y ENVÍO DE DATOS
# =====================================================================
if st.button("🚀 Enviar Reporte al Centro de Gestión", type="primary", use_container_width=True):
    if not direccion or not foto or not st.session_state['hora_registro'] or not gps_coordenadas:
        st.warning("⚠️ Datos incompletos. Asegúrate de escribir la dirección y capturar la fotografía.")
    else:
        with st.spinner("Subiendo evidencia y registrando hito en la base de datos..."):
            try:
                # A. Subir la imagen a ImgBB
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
                    hito,
                    st.session_state['hora_registro'],
                    gps_coordenadas,
                    enlace_foto
                ]
                
                hoja.append_row(fila_nueva)
                
                st.success(f"✅ ¡Reporte de '{hito}' guardado exitosamente en el Centro de Gestión!")
                
                # Limpiar variable de tiempo para el próximo hito
                st.session_state['hora_registro'] = None
                
            except Exception as error:
                st.error(f"Ocurrió un error al enviar el reporte: {error}")
