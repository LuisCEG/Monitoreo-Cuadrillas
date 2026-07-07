import streamlit as st
from datetime import datetime, timezone, timedelta
import requests
import base64
import gspread
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io

# =====================================================================
# CONFIGURACIÓN Y CONEXIONES (CON ZONA HORARIA DE COLOMBIA)
# =====================================================================

# Definimos la zona horaria de Colombia (UTC -5 horas)
ZONA_COLOMBIA = timezone(timedelta(hours=-5))

SPREADSHEET_ID = st.secrets["general"]["spreadsheet_id"]
IMGBB_API_KEY = st.secrets["general"]["imgbb_api_key"]

@st.cache_resource
def inicializar_conexiones():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

try:
    gc = inicializar_conexiones()
except Exception as e:
    st.error(f"Error técnico de conexión: {e}")
    st.stop()

# =====================================================================
# MOTOR DE EXTRACCIÓN EXIF (DETECTOR DE EXCUSAS)
# =====================================================================

def extraer_metadatos_foto(image_bytes):
    """Extrae la hora real y el GPS oculto dentro de una fotografía."""
    try:
        imagen = Image.open(io.BytesIO(image_bytes))
        exif = imagen._getexif()
        
        if not exif:
            return None, None

        gps_info = {}
        hora_original = None

        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "DateTimeOriginal":
                hora_original = value.split(" ")[1] # Extrae solo la hora H:M:S
            elif tag == "GPSInfo":
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    gps_info[sub_tag] = value[t]

        # Convertir coordenadas a formato Google Maps si existen
        coordenadas_mapa = None
        if gps_info and "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = gps_info["GPSLatitude"]
            lon = gps_info["GPSLongitude"]
            lat_ref = gps_info.get("GPSLatitudeRef", "N")
            lon_ref = gps_info.get("GPSLongitudeRef", "W")

            lat_dec = float(lat[0]) + float(lat[1])/60 + float(lat[2])/3600
            if lat_ref == 'S': lat_dec = -lat_dec

            lon_dec = float(lon[0]) + float(lon[1])/60 + float(lon[2])/3600
            if lon_ref == 'W': lon_dec = -lon_dec

            coordenadas_mapa = f"https://www.google.com/maps?q={lat_dec},{lon_dec}"

        return hora_original, coordenadas_mapa
    except Exception:
        return None, None

# =====================================================================
# INTERFAZ DE USUARIO
# =====================================================================

st.set_page_config(page_title="Centro de Gestión - Monitoreo", page_icon="👷‍♂️", layout="centered")
st.title("Reporte de Operaciones en Campo 👷‍♂️")

# 1. Datos Generales
st.subheader("1. Información del Frente de Trabajo")
cuadrilla = st.selectbox("Seleccione la Cuadrilla", [
    "Cuadrilla 1 - Instalaciones", 
    "Cuadrilla 2 - Montajes", 
    "Cuadrilla 3 - Eje Cafetero / Mantenimiento"
])
direccion = st.text_input("Proyecto / Dirección", placeholder="Ej: Proyecto Dosquebradas...")
hito = st.selectbox("Seleccione el Hito Operativo", [
    "🌅 Inicio de Jornada", "🥪 Salida a Almuerzo", "🔄 Regreso de Almuerzo", "🛑 Fin de Jornada"
])

st.markdown("---")

# 2. Selección del Método de Reporte
st.subheader("2. Método de Evidencia")
metodo_reporte = st.radio("¿Cómo enviarás el reporte?", ["En Vivo (Con señal)", "Diferido (Tomé la foto sin señal)"])

gps_coordenadas = None
hora_registro = None
foto_bytes = None

if metodo_reporte == "En Vivo (Con señal)":
    st.write("Captura tu ubicación actual:")
    ubicacion = streamlit_geolocation()
    
    if ubicacion['latitude'] is not None and ubicacion['longitude'] is not None:
        gps_coordenadas = f"https://www.google.com/maps?q={ubicacion['latitude']},{ubicacion['longitude']}"
        st.success("📍 Ubicación en vivo confirmada.")
        
        foto = st.camera_input("Capturar fotografía de evidencia", key="camara_viva")
        if foto:
            foto_bytes = foto.getvalue()
            # SE APLICA LA ZONA HORARIA DE COLOMBIA
            hora_registro = datetime.now(ZONA_COLOMBIA).strftime("%H:%M:%S")
            st.success(f"📸 Foto en vivo capturada. Hora asignada: {hora_registro}")
    else:
        st.warning("⚠️ Activa el GPS para habilitar la cámara en vivo.")

elif metodo_reporte == "Diferido (Tomé la foto sin señal)":
    st.info("Sube la foto que tomaste con la cámara de tu celular. El sistema extraerá la hora y ubicación reales.")
    foto_subida = st.file_uploader("Seleccionar imagen de la galería", type=['jpg', 'jpeg', 'png'])
    
    if foto_subida:
        foto_bytes = foto_subida.getvalue()
        hora_extraida, gps_extraido = extraer_metadatos_foto(foto_bytes)
        
        if hora_extraida:
            hora_registro = hora_extraida
            st.success(f"🕒 HORA DETECTADA EN LA FOTO: {hora_registro}")
        else:
            st.error("❌ La foto no tiene registro de hora. (Posible captura de pantalla o imagen enviada por WhatsApp).")
            
        if gps_extraido:
            gps_coordenadas = gps_extraido
            st.success("📍 UBICACIÓN DETECTADA EN LA FOTO. Todo en orden.")
        else:
            st.error("❌ La foto no tiene ubicación satelital. El técnico tenía el GPS apagado al momento de tomarla.")

st.markdown("---")

# =====================================================================
# ENVÍO AL CENTRO DE GESTIÓN
# =====================================================================
if st.button("🚀 Enviar Reporte al Centro de Gestión", type="primary", use_container_width=True):
    if not direccion or not foto_bytes or not hora_registro or not gps_coordenadas:
        st.warning("⚠️ El reporte está bloqueado. Faltan datos o la foto diferida no superó la auditoría del sistema (Sin GPS u Hora).")
    else:
        with st.spinner("Subiendo evidencia y registrando en la base de datos..."):
            try:
                # A. Subir a ImgBB
                foto_base64 = base64.b64encode(foto_bytes).decode('utf-8')
                url_imgbb = "https://api.imgbb.com/1/upload"
                respuesta_api = requests.post(url_imgbb, data={"key": IMGBB_API_KEY, "image": foto_base64}).json()
                enlace_foto = respuesta_api["data"]["url"]
                
                # B. Escribir en Sheets (SE APLICA LA ZONA HORARIA DE COLOMBIA PARA LA FECHA)
                hoja = gc.open_by_key(SPREADSHEET_ID).sheet1
                fecha_colombia = datetime.now(ZONA_COLOMBIA).strftime("%Y-%m-%d")
                fila_nueva = [fecha_colombia, cuadrilla, direccion, hito, hora_registro, gps_coordenadas, enlace_foto]
                hoja.append_row(fila_nueva)
                
                st.success(f"✅ ¡Reporte guardado exitosamente!")
            except Exception as error:
                st.error(f"Ocurrió un error al enviar el reporte: {error}")
