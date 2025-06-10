import streamlit as st
from datetime import datetime, date, timedelta
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import pytz
import re
from collections import Counter
import plotly.express as px

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
CAPACIDAD_MAX = 60
LOTES = ["Lote 95", "Lote 131"]

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

def update_request(row_idx, area, estado, aprobador, comentario):
    ws = get_worksheet()
    fecha_revision = ahora_lima()
    cols = {
        "Security": (22, 23, 24, 25),
        "QHS": (26, 27, 28, 29),
        "Logística": (30, 31, 32, 33)
    }
    col_estado, col_coment, col_aprobador, col_fecha = cols[area]
    ws.update_cell(row_idx + 2, col_estado, estado)
    ws.update_cell(row_idx + 2, col_coment, comentario)
    ws.update_cell(row_idx + 2, col_aprobador, aprobador)
    ws.update_cell(row_idx + 2, col_fecha, fecha_revision)

def es_correo_valido(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(regex, email))

def fechas_y_cupos(df, lote, dias_adelante=30):
    fechas = [(date.today() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias_adelante+1)]
    if not df.empty:
        aprobadas = df[(df["Estado Logística"] == "Aprobada") & (df["Lote"] == lote)]
        counts = Counter(aprobadas["Fecha Ingreso"].str[:10]) if not aprobadas.empty else Counter()
    else:
        counts = Counter()
    opciones = []
    for f in fechas:
        ocupados = counts.get(f, 0)
        libres = CAPACIDAD_MAX - ocupados
        if libres > 0:
            opciones.append(f"{f} (disponibles: {libres})")
    return opciones

def resumen_ocupacion(df, lote, dias_adelante=30):
    fechas = [(date.today() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias_adelante+1)]
    if not df.empty:
        aprobadas = df[(df["Estado Logística"] == "Aprobada") & (df["Lote"] == lote)]
        counts = aprobadas["Fecha Ingreso"].str[:10].value_counts() if not aprobadas.empty else pd.Series(dtype=int)
    else:
        counts = pd.Series(dtype=int)
    ocupados = [counts.get(f, 0) for f in fechas]
    libres = [CAPACIDAD_MAX - ocup for ocup in ocupados]
    return fechas, ocupados, libres

# Cargar las imputaciones, usando el archivo actualizado y nombres exactos
@st.cache_data
def cargar_imputaciones():
    df_obj = pd.read_excel("Objetos de imputación.xlsx")
    return df_obj
# ---------- Imputaciones hardcodeadas en el código ----------------
# Puedes copiar la tabla y editarla aquí, o incluso cargarla de un .csv si prefieres.
IMPUTACIONES = [
    # (TIPO, OBJETO, ORDEN/PEP)
    ("OPEX", "Órden CO", "600006 - OPERATIONS"),
    ("OPEX", "Órden CO", "600008 - MAINTENANCE"),
    ("OPEX", "Órden CO", "600011 - MEDICAL SERVICES"),
    ("OPEX", "Órden CO", "600012 - SECURITY"),
    ("OPEX", "Órden CO", "600014 - CAMP (MAINTENANCE/ CATERING /MEDICAL)"),
    ("OPEX", "Órden CO", "600015 - LABORATORY"),
    ("OPEX", "Órden CO", "600016 - LOGISTIC SERVICES - OLI"),
    ("OPEX", "Órden CO", "600017 - WASTE PLANT"),
    ("OPEX", "Órden CO", "600018 - WATER PLANTS (PTAR/PTAP)"),
    ("OPEX", "Órden CO", "600019 - WAREHOUSE SERVICES"),
    ("OPEX", "Órden CO", "600020 - IT SERVICES & COMMUNICATIONS"),
    ("OPEX", "Órden CO", "600023 - FLUVIAL (PASSENGER TRANSPORT)"),
    ("OPEX", "Órden CO", "600024 - O&M SERVICES"),
    ("OPEX", "Órden CO", "600025 - SLICKLINE SERVICES/MAINTENANCE CABEZAL"),
    ("OPEX", "Órden CO", "600026 - CONSTRUCTIONS SERVICES"),
    ("OPEX", "Órden CO", "600027 - MAINTENANCE MCS AND WAREOUSE"),
    ("OPEX", "Órden CO", "600028 - PULLING"),
    ("OPEX", "Órden CO", "600029 - ENERGY PACKAGE"),
    ("OPEX", "Órden CO", "600030 - PERSONNEL / TECHNICAL ADVICE"),
    ("OPEX", "Órden CO", "600031 - COMMUNITY RELATIONS PLAN"),
    ("OPEX", "Órden CO", "600032 - MONITORING (BIOTIC AND ABIOTIC)"),
    ("OPEX", "Órden CO", "600033 - ENVIRONMENTAL COMPENSATION PROGRAM"),
    ("OPEX", "Órden CO", "600034 - HSS MANAGMENT COSTS"),
    ("OPEX", "Órden CO", "600035 - PERMITS / OBLIGATIONS"),
    ("OPEX", "Órden CO", "600036 - HEALTH EXPENSES"),
    ("OPEX", "Órden CO", "600039 - OTHER SECURITY SUPPORT"),
    ("OPEX", "Órden CO", "600040 - EROSION CONTROL MANAGEMENT"),
    ("OPEX", "Órden CO", "600041 - MAINTENANCE OF THE RIVERBANK"),
    ("OPEX", "Órden CO", "600042 - MONITORING LOCATION"),
    ("OPEX", "Órden CO", "600045 - COMMUNICATIONS"),
    # ... Agrega aquí los de COMMUNITY SUPPORT y CAPEX ...
    ("COMMUNITY SUPPORT", "Órden CO", "500000 - PREPARATION PROJECT PROFILE AGREEMENT MP"),
    # ... (agrega todos los community support aquí como en tu lista) ...
    ("CAPEX", "Elementos PEP", "PT-20.F.03/05/04 - TRANSPORTE FLUVIAL PASAJEROS - BRETAÑA DOCK IMPROVEMENT"),
    # ... (agrega todos los capex aquí como en tu lista) ...
]

# --------------------------------------------------------------

menu = st.sidebar.selectbox(
    "Seleccione módulo",
    ["Solicitud de Cupo", "Resumen de Cupos", "Panel Security", "Panel QHS", "Panel Logística"]
)

df_requests = get_all_requests()
df_obj = cargar_imputaciones()

tipo_imputacion_col = 'TIPO DE IMPUTACIÓN'
objeto_imputacion_col = 'OBJETO DE IMPUTACIÓN'
orden_co_col = 'ORDEN CO/ELEMENTO PEP'

if menu == "Resumen de Cupos":
    st.header("Resumen visual de ocupación de cupos")
    lote_resumen = st.selectbox("Selecciona el Lote", LOTES)
    fechas, ocupados, libres = resumen_ocupacion(df_requests, lote_resumen, dias_adelante=30)

    df_plot = pd.DataFrame({
        "Fecha": fechas,
        "Ocupados": ocupados,
        "Disponibles": libres
    })

    fig = px.bar(
        df_plot, x="Fecha", y=["Ocupados", "Disponibles"],
        barmode="stack",
        labels={"value": "Pasajeros", "variable": "Estado"},
        title=f"Ocupación de cupos por fecha - {lote_resumen}",
        height=400
    )
    fig.update_layout(xaxis_tickangle=-45, xaxis_title="Fecha de Ingreso", yaxis_range=[0, CAPACIDAD_MAX + 5])
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df_plot)

if menu == "Solicitud de Cupo":
    st.header("Solicitud de cupo de transporte")
    st.info("Completa el siguiente formulario para solicitar el cupo de transporte de ingreso. Solo se permite registrar un pasajero por solicitud.")

    today = date.today()
    min_birthdate = date(1950, 1, 1)
    max_birthdate = date(today.year - 18, today.month, today.day)

    lote = st.selectbox("Lote al que solicita el ingreso", LOTES)
    fechas_con_cupos = fechas_y_cupos(df_requests, lote, dias_adelante=30)
    if not fechas_con_cupos:
        st.warning("No hay fechas con cupos disponibles para este lote.")
        st.stop()
    fecha_seleccionada = st.selectbox(
        "Fecha de ingreso solicitada (con cupos disponibles)",
        options=fechas_con_cupos
    )
    fecha_ingreso = fecha_seleccionada.split(" ")[0]

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
        lugar_embarque = st.selectbox("Lugar de embarque", ["Iquitos", "Nauta", "Otros"])
        tiempo_permanencia = st.text_input("Tiempo estimado de permanencia (en días)", max_chars=10)
        observaciones = st.text_area("Observaciones relevantes (salud, alimentación, otros)", max_chars=200)

        # --- BLOQUE CRÍTICO: TIPOS Y OBJETOS DE IMPUTACIÓN ---
        tipos_disponibles = df_obj[tipo_imputacion_col].dropna().unique().tolist()
        # ------- Imputación hardcodeada -----------
        tipos_disponibles = sorted(list(set([x[0] for x in IMPUTACIONES])))
        tipo_imputacion = st.selectbox("Tipo de Imputación", tipos_disponibles)

        df_filtrado = df_obj[df_obj[tipo_imputacion_col].astype(str).str.strip() == tipo_imputacion]

        lista_objetos = [
            f"{row[orden_co_col]} - {row[objeto_imputacion_col]}"
            for idx, row in df_filtrado.iterrows()
        objetos_disponibles = [
            (obj, cod)
            for (tipo, obj, cod) in IMPUTACIONES
            if tipo == tipo_imputacion
        ]

        if not lista_objetos:
        objeto_imputacion_opciones = [f"{obj} - {cod}" for obj, cod in objetos_disponibles]
        if not objeto_imputacion_opciones:
            st.warning("No existen objetos de imputación para este tipo seleccionado.")
            st.stop()

        seleccion = st.selectbox("Objeto de Imputación (Orden CO o Elemento PEP)", lista_objetos)

        idx_seleccion = [i for i, txt in enumerate(lista_objetos) if txt == seleccion][0]
        row_obj = df_filtrado.iloc[idx_seleccion]

        objeto_imputacion = row_obj[orden_co_col]
        descripcion_imputacion = row_obj[objeto_imputacion_col]
        proyecto = "-"  # Si tu archivo tiene columna proyecto agrégala aquí
        seleccion = st.selectbox("Objeto de Imputación (Orden CO o Elemento PEP)", objeto_imputacion_opciones)
        idx = objeto_imputacion_opciones.index(seleccion)
        objeto_imputacion = objetos_disponibles[idx][1]
        descripcion_imputacion = objeto_imputacion  # Si tienes una descripción diferente, agrégala aquí.
        proyecto = "-"

        st.text_input("Descripción Imputación", value=descripcion_imputacion, disabled=True)
        st.text_input("Proyecto", value=proyecto, disabled=True)

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
                "Tiempo estimado de permanencia (en días)": tiempo_permanencia,
                "Tipo de Imputación": tipo_imputacion,
                "Objeto de Imputación": objeto_imputacion,
                "Descripción Imputación": descripcion_imputacion,
                "Proyecto": proyecto
            }
            campos_vacios = [k for k, v in campos_texto.items() if not v or not str(v).strip()]
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

            if not errores:
                aprobadas = df_requests[(df_requests["Estado Logística"] == "Aprobada") & (df_requests["Lote"] == lote)]
                count_actual = (aprobadas["Fecha Ingreso"].str[:10] == fecha_ingreso).sum()
                if count_actual >= CAPACIDAD_MAX:
                    errores.append(f"Ya no hay cupos disponibles para la fecha {fecha_ingreso} en {lote}.")

            if errores:
                for err in errores:
                    st.error(err)
            else:
                extra_cols = ["Pendiente", "", "", "",   # Security
                              "Pendiente", "", "", "",   # QHS
                              "Pendiente", "", "", ""]   # Logística
                timestamp_lima = ahora_lima()
                row = [
                    timestamp_lima, fecha_solicitud.strftime("%Y-%m-%d"),
                    responsable_nombre, responsable_correo,
                    nombre, dni, fecha_nacimiento.strftime("%Y-%m-%d"), genero, nacionalidad,
                    procedencia, cargo, empresa, fecha_ingreso,
                    lugar_embarque, tiempo_permanencia, observaciones,
                    lote, tipo_imputacion, objeto_imputacion, descripcion_imputacion, proyecto
                ] + extra_cols
                save_to_sheet(row)
                st.success(
                    "¡Solicitud registrada correctamente! Security, QHS y Logística revisarán tu solicitud.")
                st.balloons()

def panel_aprobacion(area, pw_requerido):
    st.header(f"Panel de aprobación - {area}")
    pw = st.text_input(f"Ingrese contraseña de {area}:", type="password")
    if pw != pw_requerido:
        st.warning("Acceso restringido.")
        st.stop()

    st.success(f"Acceso concedido para {area}.")
    df = get_all_requests()
    if df.empty:
        st.info("No hay solicitudes registradas aún.")
    else:
        if area == "Security":
            pendientes = df[df["Estado Security"] == "Pendiente"]
        elif area == "QHS":
            pendientes = df[
                (df["Estado Security"] == "Aprobada") &
                (df["Estado QHS"] == "Pendiente")
            ]
        elif area == "Logística":
            pendientes = df[
                (df["Estado Security"] == "Aprobada") &
                (df["Estado QHS"] == "Aprobada") &
                (df["Estado Logística"] == "Pendiente")
            ]
        else:
            pendientes = pd.DataFrame()

        if pendientes.empty:
            st.info(f"No hay solicitudes pendientes de aprobación para {area}.")
        else:
            for idx, row in pendientes.iterrows():
                with st.expander(f"{row['Nombre Pasajero']} - Fecha Ingreso: {row['Fecha Ingreso']} - {row['Lote']}"):
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
                    st.write("**Lote:**", row["Lote"])
                    st.write("**Tipo de Imputación:**", row["Tipo de Imputación"])
                    st.write("**Objeto de Imputación:**", row["Objeto de Imputación"])
                    st.write("**Descripción Imputación:**", row["Descripción Imputación"])
                    st.write("**Proyecto:**", row["Proyecto"])

                    col1, col2 = st.columns(2)
                    with col1:
                        estado = st.selectbox("Acción", ["Aprobada", "Rechazada"], key=f"estado_{area}_{idx}")
                    with col2:
                        comentario = st.text_input("Comentario (opcional)", key=f"coment_{area}_{idx}")

                    aprobador = st.text_input("Tu nombre (Aprobador)", key=f"aprobador_{area}_{idx}")

                    boton_habilitado = True
                    advertencia = ""
                    if area == "Logística" and estado == "Aprobada":
                        fecha_ingreso = row["Fecha Ingreso"][:10]
                        lote = row["Lote"]
                        aprobadas = df[(df["Estado Logística"] == "Aprobada") & (df["Lote"] == lote)]
                        count_actual = (aprobadas["Fecha Ingreso"].str[:10] == fecha_ingreso).sum()
                        if count_actual >= CAPACIDAD_MAX:
                            boton_habilitado = False
                            advertencia = f"Ya no hay cupos disponibles para la fecha {fecha_ingreso} en {lote}. No puedes aprobar más pasajeros para ese día."
                            st.error(advertencia)

                    if st.button("Registrar acción", key=f"btn_{area}_{idx}", disabled=not boton_habilitado):
                        if not aprobador:
                            st.warning("Por favor, ingresa tu nombre como aprobador.")
                        else:
                            if advertencia:
                                st.error(advertencia)
                            else:
                                update_request(idx, area, estado, aprobador, comentario)More actions
                                st.success(f"Solicitud {estado} registrada correctamente.")
                                st.rerun()

if menu == "Panel Security":
    panel_aprobacion("Security", pw_requerido="security2024")
elif menu == "Panel QHS":
    panel_aprobacion("QHS", pw_requerido="qhs2024")
elif menu == "Panel Logística":
    panel_aprobacion("Logística", pw_requerido="logistica2024")
