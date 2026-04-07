import streamlit as st
import pandas as pd
import altair as alt

from motor import calcular_generacion

st.set_page_config(layout="wide")

MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",]
LATITUD_INICIAL = -31.6475
LONGITUD_INICIAL = -60.6985
RESULTADOS_KEY = "resultados"
ARCHIVO_CIUDADES = "ciudades_con_coordenadas.csv"


@st.cache_data
def cargar_ciudades():
    df_ciudades = pd.read_csv(ARCHIVO_CIUDADES, encoding="utf-8")
    df_ciudades = df_ciudades.rename(columns={
        "Columna 1": "ciudad",
        "Latitud": "lat",
        "Longitud": "lon",
    })
    df_ciudades["ciudad"] = df_ciudades["ciudad"].astype(str).str.strip()
    df_ciudades["lat"] = df_ciudades["lat"].astype(float)
    df_ciudades["lon"] = df_ciudades["lon"].astype(float)
    df_ciudades = df_ciudades.dropna(subset=["ciudad", "lat", "lon"])
    df_ciudades = df_ciudades.sort_values("ciudad", kind="stable").reset_index(drop=True)

    ciudades = {
        fila["ciudad"]: {"lat": fila["lat"], "lon": fila["lon"]}
        for _, fila in df_ciudades.iterrows()
    }
    opciones = ["Manual", *ciudades.keys()]

    return ciudades, opciones

def inicializar_estado():
    if "lat" not in st.session_state:
        st.session_state.lat = LATITUD_INICIAL
        st.session_state.lon = LONGITUD_INICIAL
    if "ciudad_seleccionada" not in st.session_state:
        st.session_state.ciudad_seleccionada = "Manual"
    if "vista_activa" not in st.session_state:
        st.session_state.vista_activa = "ubicacion"
    if "mensaje_exito" not in st.session_state:
        st.session_state.mensaje_exito = None


def actualizar_coordenadas(latitud, longitud):
    st.session_state.lat = float(latitud)
    st.session_state.lon = float(longitud)


inicializar_estado()
CIUDADES_SANTA_FE, OPCIONES_UBICACION = cargar_ciudades()

st.title("Simulador de Energia Fotovoltaica ☀️")

with st.sidebar:
    st.title("📋Datos del sistema")
    potAC = st.number_input("Potencia del inversor (kW)", min_value=0.0, step=0.1)
    potDC = st.number_input("Potencia total de los paneles (kW)", min_value=0.0, step=0.05)
    betha = st.number_input("Inclinacion de los paneles (grados)", min_value=30, max_value=90, step=1)
    azimuth = st.number_input("Azimuth (grados)", min_value=0, max_value=360, step=1)
    tipoPanel = st.selectbox("Tipo de panel", ("Estandar", "Premium"))
    perdidas = st.number_input("Perdidas del sistema (%)", value=14.08, min_value=10.0, max_value=30.0, step=0.1)
    calcular = st.button("Calcular", use_container_width=True)

col_vista_1, col_vista_2 = st.columns(2)
with col_vista_1:
    if st.button("📍Ubicacion", use_container_width=True):
        st.session_state.vista_activa = "ubicacion"
with col_vista_2:
    if st.button("📊Resultados", use_container_width=True):
        st.session_state.vista_activa = "resultados"

if calcular:
    inputs = {
        "lat": st.session_state.lat,
        "lon": st.session_state.lon,
        "betha": betha,
        "azimuth": azimuth,
        "pot_dc": potDC,
        "pot_ac": potAC,
        "tipo_panel": tipoPanel,
        "perdidas": perdidas
    }

    try:
        resultados = calcular_generacion(inputs)
        st.session_state[RESULTADOS_KEY] = resultados
        st.session_state.vista_activa = "resultados"
        
        st.rerun()
    except ValueError as error:
        st.error(str(error))

if st.session_state.vista_activa == "ubicacion":
    col_ciudad, col_lat, col_lon = st.columns([2.4, 1, 1])
    with col_ciudad:
        ciudad = st.selectbox(
            "Ciudad de Santa Fe",
            options=OPCIONES_UBICACION,
            key="ciudad_seleccionada"
        )

    if ciudad != "Manual":
        coordenadas = CIUDADES_SANTA_FE[ciudad]
        actualizar_coordenadas(coordenadas["lat"], coordenadas["lon"])

        with col_lat:
            st.number_input(
                "Latitud",
                value=float(st.session_state.lat),
                format="%.6f",
                disabled=True
            )
        with col_lon:
            st.number_input(
                "Longitud",
                value=float(st.session_state.lon),
                format="%.6f",
                disabled=True
            )
    else:
        with col_lat:
            lat_manual = st.number_input(
                "Latitud",
                value=float(st.session_state.lat),
                format="%.6f",
                key="lat_manual"
            )
        with col_lon:
            lon_manual = st.number_input(
                "Longitud",
                value=float(st.session_state.lon),
                format="%.6f",
                key="lon_manual"
            )

        actualizar_coordenadas(lat_manual, lon_manual)

    df_mapa = pd.DataFrame([{"lat": st.session_state.lat, "lon": st.session_state.lon}])

    st.map(df_mapa, size=22, zoom=15)

if st.session_state.vista_activa == "resultados":
    st.header("Resultados de la simulacion")

    if st.session_state.mensaje_exito:
        st.success(st.session_state.mensaje_exito)
        st.session_state.mensaje_exito = None

    if RESULTADOS_KEY not in st.session_state:
        st.info("Ejecuta una simulacion para ver los resultados.")
    else:
        res = st.session_state[RESULTADOS_KEY]
        df_mensual = pd.DataFrame(res["energia_mensual"])
        df_mensual = df_mensual.sort_values("mes").reset_index(drop=True)
        df_mensual["Mes"] = MESES_CORTOS
        df_mensual["Energia (kWh)"] = df_mensual["energia"].round(2)
        df_grafico = df_mensual[["Mes", "Energia (kWh)"]]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Energia anual (kWh)", round(res["energia_anual"], 2))
        with col2:
            st.metric("Factor de capacidad (%)", round(res["factor_capacidad"], 2))
        with col3:
            st.metric(
                "Coordenada del dataset",
                f'{res["latitud_dataset"]:.4f}, {res["longitud_dataset"]:.4f}'
            )

        st.subheader("Generacion mensual")
        grafico_mensual = (
            alt.Chart(df_grafico)
            .mark_bar()
            .encode(
                x=alt.X("Mes:N", sort=MESES_CORTOS, title="Mes"),
                y=alt.Y("Energia (kWh):Q", title="Energia (kWh)")
            )
        )
        st.altair_chart(grafico_mensual, use_container_width=True)
        st.dataframe(df_grafico, use_container_width=True, hide_index=True)
