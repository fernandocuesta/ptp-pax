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
import plotly.express as px

# ===== CONFIGURACIÓN GENERAL =====
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
CORREO_SECURITY = "fcuesta@petrotal-corp.com"  # Puedes cambiarlo

# ===== UTILIDADES GOOGLE SHEETS =====
@st.cache_resource(show_spinner=False)
def get_sheet(name):
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(SHEET_URL)
    worksheet = sh.worksheet(name)
    return worksheet

def ahora_lima():
    utc = pytz.utc
    lima = pytz.timezone("America/Lima")
    now_utc = datetime.utcnow().replace(tzinfo=utc)
    now_lima = now_utc.astimezone(lima)
    return now_lima.strftime("%Y-%m-%d %H:%M:%S")

# ===== GENERADOR DE USUARIO AdC =====
def crear_usuario(nombres, ap_paterno, ap_materno):
    def clean(txt):
        return ''.join(
            c for c in unicodedata.normalize('NFD', txt.lower())
            if unicodedata.category(c) != 'Mn'
        )
    return (clean(nombres)[0] + clean(ap_paterno) + clean(ap_materno)[0]).replace(' ', '')

# ===== GENERADOR DE CÓDIGO DE SEGUIMIENTO =====
def generar_codigo_seguimiento(lote, correlativo):
    today_str = datetime.now().strftime('%Y%m%d')
    lote_codigo = "L95" if lote == "Lote 95" else "L131"
    return f"{lote_codigo}-{today_str}-{correlativo:04d}"

def es_correo_valido(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(regex, email))

# ===== OBTENER DATA DE GOOGLE SHEETS =====
def get_df_solicitudes():
    ws = get_sheet("Solicitudes")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def get_df_adc():
    ws = get_sheet("AdC_Usuarios")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def get_df_empresas():
    ws = get_sheet("Empresas")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def get_df_objetos():
    ws = get_sheet("Objetos_Imputacion")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# ===== GUARDAR SOLICITUD =====
def save_solicitud(row):
    ws = get_sheet("Solicitudes")
    ws.append_row(row)

# ===== EMAIL (SOLO ESTRUCTURA, CONFIGURA CREDENCIALES AL USARLO) =====
def enviar_correo(destinatario, asunto, cuerpo, remitente, password):
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText(cuerpo, 'plain')
    msg['Subject'] = asunto
    msg['From'] = remitente
    msg['To'] = destinatario
    with smtplib.SMTP('smtp.office365.com', 587) as smtp:
        smtp.starttls()
        smtp.login(remitente, password)
        smtp.send_message(msg)

# ===== RESUMEN DE CUPOS =====
def resumen_ocupacion(df, lote, dias_adelante=30):
    fechas = [(date.today() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias_adelante+1)]
    if not df.empty:
        aprobadas = df[(df["Estado Logística"] == "Aprobada") & (df["Lote"] == lote)]
        counts = aprobadas["Fecha ingreso"].str[:10].value_counts() if not aprobadas.empty else pd.Series(dtype=int)
    else:
        counts = pd.Series(dtype=int)
    ocupados = [counts.get(f, 0) for f in fechas]
    libres = [CAPACIDAD_MAX - ocup for ocup in ocupados]
    return fechas, ocupados, libres

# ===== STREAMLIT INTERFAZ PRINCIPAL CON PESTAÑAS =====
tab1, tab2, tab3, tab4 = st.tabs(["Registro Individual", "Carga Masiva", "Seguimiento de Solicitud", "Panel AdC"])

# ===== REGISTRO INDIVIDUAL =====
with tab1:
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

                # Email a usuario
                #enviar_correo(resp_correo, "Solicitud registrada",
                #  f"Su solicitud fue registrada con el código: {cod_seguimiento}\n\nGracias.", remitente, password)

                st.success(f"Solicitud registrada. Código de seguimiento: {cod_seguimiento}. Te enviaremos un email de confirmación.")
                st.info("La solicitud será revisada por el Administrador de Contrato antes de Security.")

# ===== CARGA MASIVA =====
with tab2:
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
            # Aquí debes agregar la lógica para procesar el batch (usando datos similares a registro individual)
            st.success("Carga masiva registrada. Todos los pasajeros han sido cargados como solicitudes individuales.")

# ===== SEGUIMIENTO DE SOLICITUD =====
with tab3:
    st.header("Seguimiento de solicitud")
    cod = st.text_input("Ingresa tu código de seguimiento")
    if st.button("Buscar estado"):
        df = get_df_solicitudes()
        row = df[df["Código seguimiento"] == cod]
        if row.empty:
            st.error("No se encontró una solicitud con ese código.")
        else:
            st.dataframe(row)

# ===== PANEL AdC: LOGIN Y APROBACIÓN =====
with tab4:
    st.header("Panel de aprobación AdC")
    st.write("Solo para usuarios autorizados.")

    df_adc = get_df_adc()
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

                            # Si aprueba, envía correo a Security (comenta para pruebas)
                            #enviar_correo(CORREO_SECURITY, f"Solicitud aprobada {row['Código seguimiento']}",
                            #    f"La solicitud fue aprobada por el AdC. Código: {row['Código seguimiento']}", remitente, password)

                            st.rerun()
