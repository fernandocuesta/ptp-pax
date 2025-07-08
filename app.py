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

# =============== VALIDACIÓN IMPUTACIÓN ==============
def validar_imputacion(tipo_imp, codigo):
    if tipo_imp == "CAPEX" and not codigo.startswith("P"):
        return False, "El CAPEX debe tener un elemento PEP (que inicia con 'P')."
    if tipo_imp == "OPEX" and not codigo.isdigit():
        return False, "El OPEX debe tener una Orden CO numérica."
    return True, ""

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

        # Limpieza previa de columnas
        df_objetos["TIPO DE IMPUTACIÓN"] = df_objetos["TIPO DE IMPUTACIÓN"].str.strip().str.upper()
        df_objetos["OBJETO DE IMPUTACIÓN"] = df_objetos["OBJETO DE IMPUTACIÓN"].astype(str).str.upper()
        df_objetos["ORDEN CO/ELEMENTO PEP"] = df_objetos["ORDEN CO/ELEMENTO PEP"].astype(str).str.strip()

        # Filtro por tipo de imputación
        if tipo_imp == "CAPEX":
            df_filtrado = df_objetos[
                (df_objetos["TIPO DE IMPUTACIÓN"] == "CAPEX") &
                (df_objetos["OBJETO DE IMPUTACIÓN"].str.contains("PEP", na=False, case=False))
            ]
        elif tipo_imp == "OPEX":
            df_filtrado = df_objetos[
                (df_objetos["TIPO DE IMPUTACIÓN"] == "OPEX") &
                (df_objetos["OBJETO DE IMPUTACIÓN"].str.contains("CO", na=False)) &
                (df_objetos["ORDEN CO/ELEMENTO PEP"].str.match(r'^\d+', na=False))
            ]
        else:
            df_filtrado = df_objetos[df_objetos["TIPO DE IMPUTACIÓN"] == tipo_imp]

        if df_filtrado.empty:
            st.warning("No hay objetos de imputación disponibles para el tipo seleccionado.")
            obj_imp_opciones = []
        else:
            obj_imp_opciones = df_filtrado.apply(
                lambda x: f"{x['OBJETO DE IMPUTACIÓN']} - {x['ORDEN CO/ELEMENTO PEP']}", axis=1
            ).tolist()

        obj_imp_sel = st.selectbox("Objeto de Imputación*", obj_imp_opciones)

        if obj_imp_opciones:
            obj_imp_codigo = obj_imp_sel.split(' - ', 1)[-1]
        else:
            obj_imp_codigo = ""  # Solo código

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
            valido, mensaje = validar_imputacion(tipo_imp, obj_imp_codigo)
            if not valido:
                errores.append(mensaje)

            if errores:
                for e in errores:
                    st.error(e)
            else:
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
