import streamlit as st
from datetime import datetime, date
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import pytz
import re

st.set_page_config(
    page_title="Logística - Pasajeros",
    page_icon="https://petrotalcorp.com/wp-content/uploads/2023/10/cropped-favicon-32x32.png",
    layout="wide"
)

st.image("assets/logo_petrotal.png", width=220)

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_URL = "https://docs.google.com/spreadsheets/d/1u1iu85t4IknDLk50GfZFB-OQvmkO8hHwPVMPNeSDOuA/edit#gid=0"

def ahora_lima():
    utc = pytz.utc
    lima = pytz.timezone("America/Lima")
    now_utc = datetime.utcnow().replace(tzinfo=utc)
    now_lima = now_utc.astimezone(lima)
    return now_lima.strftime("%Y-%m-%d %H:%M:%S")

@st.cache_resource(show_spinner=False)
def get_worksheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet("Solicitudes")
    return worksheet

def save_to_sheet(row):
    ws = get_worksheet()
    ws.append_row(row)

def get_all_requests():
    ws = get_worksheet()
    data = ws.get_all_values()
    headers = data[0]
    df = pd.DataFrame(data[1:], columns=headers)
    return df

def update_request(row_idx, estado, aprobador, comentario):
    ws = get_worksheet()
    fecha_revision = ahora_lima()
    ws.update_cell(row_idx + 2, 17, estado)
    ws.update_cell(row_idx + 2, 18, fecha_revision)
    ws.update_cell(row_idx + 2, 19, aprobador)
    ws.update_cell(row_idx + 2, 20, comentario)

def es_correo_valido(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(regex, email))

menu = st.sidebar.selectbox("Seleccione módulo", ["Solicitud de Cupo", "Panel de Aprobación (Logística)"])

if menu == "Solicitud de Cupo":
    st.header("Solicitud de cupo de transporte")
    st.info(
        "Completa el siguiente formulario para solicitar el cupo de transporte de ingreso al Lote 95. Solo se permite registrar un pasajero por solicitud.")

    today = date.today()
    min_birthdate = date(1950, 1, 1)
    max_birthdate = date(today.year - 18, today.month, today.day)

    with st.form("solicitud_cupo"):
        responsable_nombre = st.text_input("Responsable de la solicitud (nombre completo)", max_chars=60)
        responsable_correo = st.text_input("Correo electrónico del responsable", max_chars=60)
        fecha_solicitud = st.date_input("Fecha de Solicitud", value=today, min_value=today, max_value=today)

        st.markdown("**Datos del pasajero a ingresar:**")
        nombre = st.text_input("Nombre completo del pasajero", max_chars=60)
        dni = st.text_input("DNI / CE", max_chars=15)
        fecha_nacimiento = st.date_input("Fecha de nacimiento", min_value=min_birthdate, max_value=max_birthdate)
        genero = st.selectbox("Género", ["Masculino", "Femenino", "Otro"])
        nacionalidad = st.text_input("Nacionalidad")
        procedencia = st.text_input("Procedencia (Ciudad de origen)")
        cargo = st.text_input("Puesto / Cargo")
        empresa = st.text_input("Empresa contratista")
        fecha_ingreso = st.date_input("Fecha de ingreso solicitada", min_value=today)
        lugar_embarque = st.selectbox("Lugar de embarque", ["Iquitos", "Nauta", "Otros"])
        tiempo_permanencia = st.text_input("Tiempo estimado de permanencia (en días)", max_chars=10)
        observaciones = st.text_area("Observaciones relevantes (salud, alimentación, otros)", max_chars=200)

        submitted = st.form_submit_button("Enviar Solicitud")

    if submitted:
        campos_texto = {
            "Responsable de la solicitud": responsable_nombre,
            "Correo electrónico del responsable": responsable_correo,
            "Nombre completo del pasajero": nombre,
            "DNI / CE": dni,
            "Nacionalidad": nacionalidad,
            "Procedencia (Ciudad de origen)": procedencia,
            "Puesto / Cargo": cargo,
            "Empresa contratista": empresa,
            "Tiempo estimado de permanencia (en días)": tiempo_permanencia
        }
        campos_vacios = [k for k, v in campos_texto.items() if not v.strip()]
        correo_ok = es_correo_valido(responsable_correo)

        errores = []
        if campos_vacios:
            errores.append(f"Completa los siguientes campos obligatorios: {', '.join(campos_vacios)}")
        if not correo_ok:
            errores.append("El correo electrónico no es válido. Ejemplo: nombre@dominio.com")
        if fecha_solicitud != today:
            errores.append("La fecha de solicitud debe ser la del día de hoy.")
        if not (min_birthdate <= fecha_nacimiento <= max_birthdate):
            errores.append("La fecha de nacimiento debe ser entre 1950 y una edad mínima de 18 años.")

        if errores:
            for err in errores:
                st.error(err)
        else:
            timestamp_lima = ahora_lima()
            row = [
                timestamp_lima, fecha_solicitud.strftime("%Y-%m-%d"),
                responsable_nombre, responsable_correo,
                nombre, dni, fecha_nacimiento.strftime("%Y-%m-%d"), genero, nacionalidad,
                procedencia, cargo, empresa, fecha_ingreso.strftime("%Y-%m-%d"),
                lugar_embarque, tiempo_permanencia, observaciones,
                "Pendiente", "", "", ""
            ]
            save_to_sheet(row)
            st.success(
                "¡Solicitud registrada correctamente! El área de logística validará tu solicitud y confirmará el cupo.")
            st.balloons()

elif menu == "Panel de Aprobación (Logística)":
    st.header("Panel de aprobación de solicitudes")
    pw = st.text_input("Ingrese contraseña de logística:", type="password")
    if pw != "logistica2024":
        st.warning("Acceso restringido al área de logística.")
        st.stop()

    st.success("Acceso concedido. Panel de aprobación disponible.")
    df = get_all_requests()
    if df.empty:
        st.info("No hay solicitudes registradas aún.")
    else:
        pendientes = df[df["Estado Solicitud"] == "Pendiente"]
        if pendientes.empty:
            st.info("No hay solicitudes pendientes de aprobación.")
        else:
            for idx, row in pendientes.iterrows():
                with st.expander(f"{row['Nombre Pasajero']} - Fecha Ingreso: {row['Fecha Ingreso']}"):
                    st.write("**Responsable:**", row["Responsable"])
                    st.write("**Correo Responsable:**", row["Correo Responsable"])
                    st.write("**Pasajero:**", row["Nombre Pasajero"])
                    st.write("**DNI:**", row["DNI"])
                    st.write("**Fecha Nacimiento:**", row["Fecha Nacimiento"])
                    st.write("**Género:**", row["Género"])
                    st.write("**Nacionalidad:**", row["Nacionalidad"])
                    st.write("**Procedencia:**", row["Procedencia"])
                    st.write("**Cargo:**", row["Cargo"])
                    st.write("**Empresa:**", row["Empresa"])
                    st.write("**Fecha Ingreso:**", row["Fecha Ingreso"])
                    st.write("**Lugar Embarque:**", row["Lugar Embarque"])
                    st.write("**Tiempo Permanencia:**", row["Tiempo Permanencia"])
                    st.write("**Observaciones:**", row["Observaciones"])

                    col1, col2 = st.columns(2)
                    with col1:
                        estado = st.selectbox("Acción", ["Aprobada", "Rechazada"], key=f"estado_{idx}")
                    with col2:
                        comentario = st.text_input("Comentario (opcional)", key=f"coment_{idx}")

                    aprobador = st.text_input("Tu nombre (Aprobador)", key=f"aprobador_{idx}")

                    if st.button("Registrar acción", key=f"btn_{idx}"):
                        if not aprobador:
                            st.warning("Por favor, ingresa tu nombre como aprobador.")
                        else:
                            update_request(idx, estado, aprobador, comentario)
                            st.success(f"Solicitud {estado} registrada correctamente.")
                            st.rerun()
