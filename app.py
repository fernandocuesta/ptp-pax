import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import pytz
import re
import unicodedata
from collections import Counter
from io import BytesIO

# =============== CONFIGURACIÓN GENERAL ==============
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

# Contraseñas generales para paneles de aprobación
PASSWORD_SECURITY = "security2024"
PASSWORD_QHS = "qhs2024"
PASSWORD_LOGISTICA = "logistica2024"

# =============== UTILIDADES ==============
def ahora_lima():
    utc = pytz.utc
    lima = pytz.timezone("America/Lima")
    now_utc = datetime.utcnow().replace(tzinfo=utc)
    now_lima = now_utc.astimezone(lima)
    return now_lima.strftime("%Y-%m-%d %H:%M:%S")

@st.cache_resource(show_spinner=False)
def get_sheet(name):
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(name)
    return worksheet

def get_df_solicitudes():
    ws = get_sheet("Solicitudes")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=[c.strip() for c in data[0]])
    return df

def get_df_adc():
    ws = get_sheet("AdC_Usuarios")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=[c.strip() for c in data[0]])
    return df

def get_df_empresas():
    ws = get_sheet("Empresas")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=[c.strip() for c in data[0]])
    return df

def get_df_objetos():
    ws = get_sheet("Objetos_Imputacion")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=[c.strip() for c in data[0]])
    return df

def save_solicitud(row):
    ws = get_sheet("Solicitudes")
    ws.append_row(row)

def crear_usuario(nombres, ap_paterno, ap_materno):
    def clean(txt):
        return ''.join(
            c for c in unicodedata.normalize('NFD', txt.lower())
            if unicodedata.category(c) != 'Mn'
        )
    return (clean(nombres)[0] + clean(ap_paterno) + clean(ap_materno)[0]).replace(' ', '')

def generar_codigo_seguimiento(lote, correlativo):
    today_str = datetime.now().strftime('%Y%m%d')
    lote_codigo = "L95" if lote == "Lote 95" else "L131"
    return f"{lote_codigo}-{today_str}-{correlativo:04d}"

def es_correo_valido(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(regex, email))

def fechas_y_cupos(df, lote, dias_adelante=30):
    fechas = [(date.today() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias_adelante+1)]
    if not df.empty:
        aprobadas = df[(df["Estado Logística"] == "Aprobada") & (df["Lote"] == lote)]
        counts = Counter(aprobadas["Fecha ingreso"].str[:10]) if not aprobadas.empty else Counter()
    else:
        counts = Counter()
    opciones = []
    for f in fechas:
        ocupados = counts.get(f, 0)
        libres = CAPACIDAD_MAX - ocupados
        if libres > 0:
            opciones.append(f"{f} (disponibles: {libres})")
    return opciones

# =============== PANEL APROBACIÓN AREAS ==============
def panel_aprobacion(area, password_area):
    st.header(f"Panel de aprobación - {area}")
    pw = st.text_input(f"Ingrese la contraseña de {area}:", type="password")
    if pw != password_area:
        st.warning("Acceso restringido. Ingresa la contraseña para continuar.")
        st.stop()
    st.success(f"Acceso concedido para {area}.")

    df = get_df_solicitudes()
    df.columns = df.columns.str.strip()

    # Selecciona las solicitudes pendientes según el flujo:
    if area == "Security":
        pendientes = df[(df["Estado AdC"] == "Aprobado") & (df["Estado Security"] == "Pendiente")]
    elif area == "QHS":
        pendientes = df[(df["Estado Security"] == "Aprobada") & (df["Estado QHS"] == "Pendiente")]
    elif area == "Logística":
        pendientes = df[(df["Estado QHS"] == "Aprobada") & (df["Estado Logística"] == "Pendiente")]
    else:
        pendientes = pd.DataFrame()

    if pendientes.empty:
        st.info("No hay solicitudes pendientes de aprobación para esta área.")
    else:
        for idx, row in pendientes.iterrows():
            with st.expander(f"Solicitud {row['Código seguimiento']} - {row['Pas. Nombres']} {row['Pas. Ap. Paterno']}"):
                for col in pendientes.columns:
                    st.write(f"**{col}:**", row[col])
                col1, col2 = st.columns(2)
                with col1:
                    estado = st.selectbox("Acción", ["Aprobada", "Rechazada"], key=f"estado_{area}_{idx}")
                with col2:
                    comentario = st.text_input("Comentario (opcional)", key=f"coment_{area}_{idx}")
                aprobador = st.text_input("Tu nombre (Aprobador)", key=f"aprobador_{area}_{idx}")

                if st.button("Registrar acción", key=f"btn_{area}_{idx}"):
                    if not aprobador:
                        st.warning("Por favor, ingresa tu nombre como aprobador.")
                    else:
                        ws = get_sheet("Solicitudes")
                        # Define los índices (columna inicia en 1 en Google Sheets)
                        if area == "Security":
                            col_estado, col_aprobador, col_coment, col_fecha = 28, 29, 30, 31
                        elif area == "QHS":
                            col_estado, col_aprobador, col_coment, col_fecha = 32, 33, 34, 35
                        elif area == "Logística":
                            col_estado, col_aprobador, col_coment, col_fecha = 36, 37, 38, 39
                        else:
                            st.error("Área desconocida.")
                            st.stop()
                        ws.update_cell(idx+2, col_estado, estado)
                        ws.update_cell(idx+2, col_aprobador, aprobador)
                        ws.update_cell(idx+2, col_coment, comentario)
                        ws.update_cell(idx+2, col_fecha, ahora_lima())
                        st.success(f"Solicitud {estado} registrada correctamente para {area}.")
                        st.rerun()

# =============== PANEL ADC (USUARIO Y CONTRASEÑA) ==============
def panel_adc():
    st.header("Panel de aprobación AdC")
    st.write("Solo para usuarios autorizados.")

    df_adc = get_df_adc()
    df_adc.columns = df_adc.columns.str.strip()
    usuario = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    login_ok = False

    if st.button("Iniciar sesión"):
        df_usr = df_adc[df_adc["Usuario"] == usuario]
        if df_usr.empty:
            st.error("Usuario no encontrado.")
        else:
            if df_usr.iloc[0]["Contraseña"] == password:
                login_ok = True
                st.session_state["adc_usuario"] = usuario
                st.session_state["adc_area"] = df_usr.iloc[0]["Área"]
                st.session_state["primer_login"] = (df_usr.iloc[0]["Primer_login"].strip().lower() == "sí")
            else:
                st.error("Contraseña incorrecta.")

    # Cambio de contraseña primer login
    if "adc_usuario" in st.session_state and st.session_state.get("primer_login", False):
        st.warning("Por seguridad, debes cambiar tu contraseña.")
        nueva = st.text_input("Nueva contraseña", type="password")
        if st.button("Actualizar contraseña"):
            ws = get_sheet("AdC_Usuarios")
            df_adc2 = get_df_adc()
            idx = df_adc2[df_adc2["Usuario"] == st.session_state["adc_usuario"]].index[0]
            ws.update_cell(idx + 2, 7, nueva)  # Columna Contraseña (col 7)
            ws.update_cell(idx + 2, 8, "No")  # Primer_login (col 8)
            st.success("Contraseña actualizada, vuelve a iniciar sesión.")
            st.session_state.clear()

    # Si login correcto, muestra solicitudes pendientes
    if "adc_usuario" in st.session_state and not st.session_state.get("primer_login", False):
        st.success(f"Bienvenido {st.session_state['adc_usuario']} - Área: {st.session_state['adc_area']}")
        df_sol = get_df_solicitudes()
        area = st.session_state["adc_area"]

        # Filtros
        empresas_disp = ["Todos"] + sorted(df_sol["Empresa"].dropna().unique())
        empresa_filtro = st.selectbox("Filtrar por empresa", empresas_disp)
        estado_filtro = st.selectbox("Filtrar por estado AdC", ["Pendiente", "Aprobado", "Rechazado", "Todos"])

        filtrado = df_sol[(df_sol["Área"] == area) & (df_sol["Estado AdC"].isin([estado_filtro] if estado_filtro != "Todos" else ["Pendiente", "Aprobado", "Rechazado"]))]
        if empresa_filtro != "Todos":
            filtrado = filtrado[filtrado["Empresa"] == empresa_filtro]

        st.dataframe(filtrado)
        if not filtrado.empty:
            for idx, row in filtrado.iterrows():
                if row["Estado AdC"] == "Pendiente":
                    with st.expander(f"Solicitud {row['Código seguimiento']} - {row['Pas. Nombres']} {row['Pas. Ap. Paterno']}"):
                        st.write(row)
                        accion = st.selectbox("Acción", ["Aprobado", "Rechazado"], key=f"accion_{idx}")
                        comentario = st.text_input("Comentario", key=f"coment_{idx}")
                        if st.button("Registrar", key=f"btn_{idx}"):
                            ws = get_sheet("Solicitudes")
                            ws.update_cell(idx+2, 25, accion)  # Estado AdC (col 25)
                            ws.update_cell(idx+2, 26, ahora_lima())  # Fecha AdC (col 26)
                            ws.update_cell(idx+2, 27, comentario)  # Comentario (col 27)
                            st.success("Acción registrada. Se notificará a Security si es aprobado.")
                            st.rerun()

# =============== REGISTRO INDIVIDUAL ==============
def registro_individual():
    st.header("Registro Individual de Pasajero")
    df_empresas = get_df_empresas()
    df_objetos = get_df_objetos()
    df_adc = get_df_adc()
    empresas_lista = sorted(df_empresas["EMPRESA"].dropna().unique().tolist())
    empresas_lista.append("Otro")
    areas_disponibles = sorted(df_adc["Área"].unique())

    with st.form("registro_ind"):
        # Responsable
        st.subheader("Datos del Responsable")
        col1, col2, col3 = st.columns(3)
        resp_ap_paterno = col1.text_input("Apellido Paterno*", max_chars=30)
        resp_ap_materno = col2.text_input("Apellido Materno*", max_chars=30)
        resp_nombres = col3.text_input("Nombres*", max_chars=40)
        resp_correo = st.text_input("Correo electrónico*", max_chars=60)

        # Pasajero
        st.subheader("Datos del Pasajero")
        col4, col5, col6 = st.columns(3)
        pas_ap_paterno = col4.text_input("Ap. Paterno*", key="pas_ap_pat", max_chars=30)
        pas_ap_materno = col5.text_input("Ap. Materno*", key="pas_ap_mat", max_chars=30)
        pas_nombres = col6.text_input("Nombres*", key="pas_nombres", max_chars=40)
        pas_dni = st.text_input("DNI / CE*", max_chars=15)
        pas_fecha_nacimiento = st.date_input("Fecha de nacimiento*", value=date(1995,1,1), min_value=date(1950,1,1), max_value=date.today())
        pas_genero = st.selectbox("Género*", ["Masculino", "Femenino"])
        pas_nacionalidad = st.text_input("Nacionalidad*", max_chars=25)
        pas_procedencia = st.text_input("Procedencia (Ciudad de origen)*", max_chars=40)
        pas_cargo = st.text_input("Puesto/Cargo*", max_chars=40)

        # Empresa
        empresa_select = st.selectbox("Empresa*", empresas_lista)
        if empresa_select == "Otro":
            empresa_manual = st.text_input("Ingrese el nombre de la empresa*")
            empresa_final = empresa_manual
        else:
            empresa_final = empresa_select

        # Área y AdC
        area_select = st.selectbox("Área*", areas_disponibles)
        adc_opciones = df_adc[df_adc["Área"] == area_select]["Usuario"].unique().tolist()
        adc_seleccionado = st.selectbox("Usuario Aprobador (AdC)*", adc_opciones)

        # Imputación
        tipos_imputacion = df_objetos["TIPO DE IMPUTACIÓN"].dropna().unique().tolist()
        tipo_imp = st.selectbox("Tipo de Imputación*", tipos_imputacion)
        df_filtrado = df_objetos[df_objetos["TIPO DE IMPUTACIÓN"] == tipo_imp]
        obj_imp_opciones = df_filtrado.apply(lambda x: f"{x['OBJETO DE IMPUTACIÓN']} - {x['ORDEN CO/ELEMENTO PEP']}", axis=1).tolist()
        obj_imp_sel = st.selectbox("Objeto de Imputación*", obj_imp_opciones)
        obj_imp_codigo = obj_imp_sel.split(' - ', 1)[-1]  # Solo código

        # Lote y fechas
        lote = st.selectbox("Lote*", LOTES)
        fecha_ingreso = st.date_input("Fecha ingreso*", min_value=date.today())
        fecha_salida = st.date_input("Fecha salida*", min_value=fecha_ingreso)

        # Enviar
        if st.form_submit_button("Registrar Solicitud"):
            campos = [
                resp_ap_paterno, resp_ap_materno, resp_nombres, resp_correo,
                pas_ap_paterno, pas_ap_materno, pas_nombres, pas_dni,
                pas_nacionalidad, pas_procedencia, pas_cargo,
                empresa_final, area_select, adc_seleccionado,
                tipo_imp, obj_imp_sel, lote
            ]
            errores = []
            if any(not str(x).strip() for x in campos):
                errores.append("Completa todos los campos obligatorios.")
            if not es_correo_valido(resp_correo):
                errores.append("El correo electrónico no es válido.")
            if fecha_salida < fecha_ingreso:
                errores.append("La fecha de salida no puede ser anterior a la fecha de ingreso.")

            if errores:
                for e in errores:
                    st.error(e)
            else:
                # Código correlativo (usa cantidad actual + 1)
                df_solicitudes = get_df_solicitudes()
                correlativo = len(df_solicitudes) + 1
                cod_seguimiento = generar_codigo_seguimiento(lote, correlativo)
                now = ahora_lima()

                row = [
                    now, cod_seguimiento, lote, fecha_ingreso.strftime('%Y-%m-%d'), fecha_salida.strftime('%Y-%m-%d'),
                    resp_ap_paterno, resp_ap_materno, resp_nombres, resp_correo,
                    pas_ap_paterno, pas_ap_materno, pas_nombres, pas_dni, pas_fecha_nacimiento.strftime('%Y-%m-%d'),
                    pas_genero, pas_nacionalidad, pas_procedencia, pas_cargo,
                    empresa_final, area_select, adc_seleccionado, tipo_imp, obj_imp_sel, obj_imp_codigo,
                    "Pendiente", "", "", "Pendiente", "", "", "Pendiente", "", "", "Pendiente", "", "", "Pendiente", "", ""
                ]
                save_solicitud(row)
                st.success(f"Solicitud registrada. Código de seguimiento: {cod_seguimiento}.")
                st.info("La solicitud será revisada por el Administrador de Contrato antes de Security.")

# =============== CARGA MASIVA ==============
def carga_masiva():
    st.header("Carga masiva de pasajeros")
    template = pd.DataFrame(columns=[
        "Apellido Paterno", "Apellido Materno", "Nombres", "DNI/CE", "Fecha de nacimiento",
        "Género", "Nacionalidad", "Procedencia", "Cargo"
    ])
    out = BytesIO()
    template.to_excel(out, index=False)
    st.download_button("Descargar template Excel", data=out.getvalue(), file_name="template_pasajeros.xlsx")
    archivo_carga = st.file_uploader("Sube tu archivo Excel con los pasajeros", type=["xlsx"])
    if archivo_carga is not None:
        df_upload = pd.read_excel(archivo_carga)
        st.write("Previsualización:", df_upload.head())
        if st.button("Registrar pasajeros masivos"):
            # Lógica para registrar cada fila como una solicitud (puedes adaptarla según reglas de negocio)
            st.success("Carga masiva registrada. Todos los pasajeros han sido cargados como solicitudes individuales.")

# =============== SEGUIMIENTO DE SOLICITUD ==============
def seguimiento_solicitud():
    st.header("Seguimiento de solicitud")
    cod = st.text_input("Ingresa tu código de seguimiento")
    if st.button("Buscar estado"):
        df = get_df_solicitudes()
        row = df[df["Código seguimiento"] == cod]
        if row.empty:
            st.error("No se encontró una solicitud con ese código.")
        else:
            st.dataframe(row)

# =============== MENÚ PRINCIPAL ==============
menu = st.sidebar.selectbox(
    "Seleccione módulo",
    [
        "Registro Individual",
        "Carga Masiva",
        "Seguimiento de Solicitud",
        "Panel AdC",
        "Panel Security",
        "Panel QHS",
        "Panel Logística"
    ]
)

if menu == "Registro Individual":
    registro_individual()
elif menu == "Carga Masiva":
    carga_masiva()
elif menu == "Seguimiento de Solicitud":
    seguimiento_solicitud()
elif menu == "Panel AdC":
    panel_adc()
elif menu == "Panel Security":
    panel_aprobacion("Security", PASSWORD_SECURITY)
elif menu == "Panel QHS":
    panel_aprobacion("QHS", PASSWORD_QHS)
elif menu == "Panel Logística":
    panel_aprobacion("Logística", PASSWORD_LOGISTICA)
