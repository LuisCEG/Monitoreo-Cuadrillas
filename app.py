import streamlit as st
import pandas as pd
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# =====================================================================
# CONFIGURACIÓN DE CONEXIONES Y SEGURIDAD
# =====================================================================

# Configuración de los IDs de Google (Reemplazar con tus IDs reales o usar st.secrets)
SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
DRIVE_FOLDER_ID = st.secrets["general"]["drive_folder_id"]

@st.cache_resource
def inicializar_conexiones():
    """Inicializa los servicios de Google usando las credenciales seguras."""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Cargar credenciales desde los secretos de Streamlit
    creds_dict = json.loads(st.secrets["textkey"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    
    # Clientes de API
    client_gspread = gspread.authorize(creds)
    servicio_drive = build('drive', 'v3', credentials=creds)
    
    return client_gspread, servicio_drive

try:
    gc, drive_service = inicializar_conexiones()
except Exception as e:
    st.error("Error de configuración en las credenciales de Google. Verifica tus Secrets.")
    st.stop()

# =====================================================================
# INTERFAZ DE USUARIO (STREAMLIT)
# =====================================================================

st.set_page_config(page_title="Centro de Gestión - Monitoreo", page_icon="👷‍♂️", layout="centered")
st.title("Reporte de Operaciones en Campo 👷‍♂️")
st.markdown("---")

# 1. Datos Generales
st.subheader("1. Información del Frente de Trabajo")
cuadrilla = st.selectbox("Seleccione la Cuadrilla", ["Cuadrilla 1 - Instalaciones", "Cuadrilla 2 - Montajes", "Cuadrilla 3 - Mantenimiento"])
direccion = st.text_input("Proyecto / Dirección", placeholder="Ej: Hotel Aimarawa, San Antero / Proyecto Dosquebradas")

# 2. Geolocalización mediante HTML5 en el Navegador
st.markdown("### 2. Validación de Ubicación (GPS)")
# Pequeño script inyectado para capturar coordenadas reales desde el celular
componente_gps = """
<p id="status">Buscando señal GPS...</p>
<button onclick="getLocation()">📍 Validar Coordenadas</button>
<script>
var x = document.getElementById("status");
function getLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(showPosition, showError);
  } else { 
    x.innerHTML = "La geolocalización no es soportada por este navegador.";
  }
}
function showPosition(position) {
  x.innerHTML = position.coords.latitude + ", " + position.coords.longitude;
  // Enviar datos de vuelta a Streamlit mediante la URL o almacenamiento local si es necesario
  window.parent.postMessage({type: 'streamlit:setComponentValue', value: position.coords.latitude + "," + position.coords.longitude}, '*');
}
function showError(error) {
  switch(error.code) {
    case error.PERMISSION_DENIED:
      x.innerHTML = "Usuario denegó el acceso al GPS."
      break;
    case error.POSITION_UNAVAILABLE:
      x.innerHTML = "Ubicación no disponible."
      break;
    case error.TIMEOUT:
      x.innerHTML = "Tiempo de espera agotado."
      break;
  }
}
</script>
"""
# Entrada manual o asistida para asegurar el registro si el navegador bloquea el script
gps_coordenadas = st.text_input("Coordenadas Latitud, Longitud (Verifica que tu GPS esté encendido):", placeholder="Ej: 4.7486,-75.9124")

st.markdown("---")

# 3. Control de Tiempos
st.subheader("3. Registro de Horarios")
col1, col2 = st.columns(2)

if 'hora_llegada' not in st.session_state:
    st.session_state['hora_llegada'] = None
if 'hora_salida' not in st.session_state:
    st.session_state['hora_salida'] = None

with col1:
    if st.button("🟢 Registrar Llegada", use_container_width=True):
        st.session_state['hora_llegada'] = datetime.now().strftime("%H:%M:%S")
    if st.session_state['hora_llegada']:
        st.success(f"Llegada registrada: {st.session_state['hora_llegada']}")

with col2:
    if st.button("🔴 Registrar Salida", use_container_width=True):
        st.session_state['hora_salida'] = datetime.now().strftime("%H:%M:%S")
    if st.session_state['hora_salida']:
        st.error(f"Salida registrada: {st.session_state['hora_salida']}")

st.markdown("---")

# 4. Registro Fotográfico
st.subheader("4. Evidencia Fotográfica")
foto = st.camera_input("Capturar fotografía del avance o estado del sitio")

if foto:
    st.image(foto, caption="Vista previa de la evidencia", use_container_width=True)

st.markdown("---")

# =====================================================================
# PROCESAMIENTO Y ENVÍO DE DATOS
# =====================================================================
if st.button("🚀 Enviar Reporte al Centro de Gestión", type="primary", use_container_width=True):
    if not direccion or not foto or not st.session_state['hora_llegada'] or not gps_coordenadas:
        st.warning("⚠️ Datos incompletos. Se requiere: Dirección, Coordenadas GPS, Foto e ingresar la Hora de Llegada.")
    else:
        with st.spinner("Procesando y subiendo información a los servidores..."):
            try:
                # A. Subir la imagen a Google Drive
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nombre_archivo = f"{cuadrilla.replace(' ', '_')}_{timestamp}.jpg"
                
                # Convertir el buffer de la foto para la API de Google
                foto_bytes = foto.getvalue()
                fh = io.BytesIO(foto_bytes)
                media = MediaIoBaseUpload(fh, mimetype='image/jpeg', resumable=True)
                
                metadatos_archivo = {
                    'name': nombre_archivo,
                    'parents': [DRIVE_FOLDER_ID]
                }
                
                archivo_drive = drive_service.files().create(
                    body=metadatos_archivo,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
                
                enlace_foto = archivo_drive.get('webViewLink')
                
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
                
                st.success("✅ ¡Reporte guardado exitosamente! La información ya está disponible en el Centro de Gestión.")
                
                # Limpiar variables de tiempo para el próximo registro
                st.session_state['hora_llegada'] = None
                st.session_state['hora_salida'] = None
                
            except Exception as error:
                st.error(f"Ocurrió un error al enviar el reporte: {error}")