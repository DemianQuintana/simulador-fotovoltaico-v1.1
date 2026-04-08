from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset_solar_santa_fe_LOCAL.parquet"

if not DATASET_PATH.exists():
    raise FileNotFoundError(
        f"No se encontro el dataset requerido: {DATASET_PATH}"
    )

dataset = pd.read_parquet(DATASET_PATH)

def calcular_generacion(inputs):

    lat = inputs["lat"]
    lon = inputs["lon"]
    betha = inputs["betha"]
    azimuth = inputs["azimuth"]
    pot_dc = inputs["pot_dc"]
    pot_ac = inputs["pot_ac"]
    tipo_panel = inputs["tipo_panel"]
    tipo_montaje = inputs["tipo_montaje"]
    perdidas = inputs["perdidas"]
    eficiencia_inversor = inputs["eficiencia_inversor"]

    if pot_ac <= 0:
        raise ValueError("La potencia AC del inversor debe ser mayor a 0")
    if pot_dc < 0:
        raise ValueError("La potencia DC no puede ser negativa")
    if not 0 <= betha <= 90:
        raise ValueError("La inclinacion de los paneles debe estar entre 0 y 90 grados")
    if not 0 <= perdidas <= 100:
        raise ValueError("Las perdidas deben estar entre 0 y 100")
    if not 0 < eficiencia_inversor <= 100:
        raise ValueError("La eficiencia del inversor debe estar entre 0 y 100")

    if tipo_montaje == "En techo":
        u0 = 23
        u1 = 4
        albedo = 0.18
    else:
        u0 = 27
        u1 = 6
        albedo = 0.22

    lat_cercana, lon_cercana = obtener_coordenadas(lat, lon, dataset)
    df_punto = obtener_datos_punto(lat_cercana, lon_cercana, dataset)

    df_punto = calcular_aoi(df_punto, betha, azimuth)
    df_punto = calcular_factores_perez(df_punto)
    df_punto = calcular_poa(df_punto, betha, albedo=albedo)
    df_punto = calcular_perdidas_vidrio(df_punto, tipo_panel)
    df_punto = calcular_temperatura_y_potencia_dc(df_punto, pot_dc, tipo_panel, u0=u0, u1=u1)
    df_punto["P_DC_bruta"] = df_punto["P_DC"]

    if perdidas > 0:
        df_punto["P_DC"] = df_punto["P_DC"] * (1 - perdidas / 100)

    df_punto = calcular_potencia_ac(df_punto, pot_ac, pot_dc, eta_nom=eficiencia_inversor / 100)

    df_punto["energia_horaria"] = df_punto["P_AC"]
    energia_mensual = df_punto.groupby("mes")["energia_horaria"].sum()
    energia_anual = df_punto["energia_horaria"].sum()
    factor_capacidad = (energia_anual / (pot_ac * 8760)) * 100

    meses = list(range(1, 13))
    generacion_mensual = [
        {
            "mes": mes,
            "energia": float(energia_mensual.get(mes, 0.0))
        }
        for mes in meses
    ]

    resultados = {
        "latitud_dataset": lat_cercana,
        "longitud_dataset": lon_cercana,
        "energia_anual": float(energia_anual),
        "energia_mensual": generacion_mensual,
        "factor_capacidad": float(factor_capacidad),
    }

    return resultados

def obtener_coordenadas(latitud_real, longitud_real, lista):

    coordenadas = lista[["lat", "lon"]].drop_duplicates()

    distancias = np.sqrt(
        (coordenadas["lat"] - latitud_real)**2 +
        (coordenadas["lon"] - longitud_real)**2
    )

    indice_min = distancias.idxmin()

    lat_cercana = coordenadas.loc[indice_min, "lat"]
    lon_cercana = coordenadas.loc[indice_min, "lon"]

    return lat_cercana, lon_cercana

def obtener_datos_punto(latitud, longitud, lista):

    columnas_base = [
        "time",
        "ghi",
        "dni",
        "dhi",
        "temp_air",
        "wind_speed_2m",
        "zenith",
        "azimuth",
        "lat",
        "lon",
        "dia",
    ]

    df_punto = lista.loc[
        (lista["lat"] == latitud) & (lista["lon"] == longitud),
        columnas_base
    ].copy()

    df_punto = df_punto.sort_values("time").reset_index(drop=True)
    df_punto["time"] = pd.to_datetime(df_punto["time"])
    df_punto["mes"] = df_punto["time"].dt.month

    return df_punto

def calcular_aoi(df_punto, beta, gamma_panel):
    df = df_punto.copy()

    zenith = np.radians(df["zenith"])
    gamma_sol = np.radians(df["azimuth"])
    beta = np.radians(beta)
    gamma_panel = np.radians(gamma_panel)

    cos_aoi = (
        np.sin(zenith) * np.cos(gamma_panel - gamma_sol) * np.sin(beta)
        + np.cos(zenith) * np.cos(beta)
    )

    cos_aoi = np.clip(cos_aoi, -1.0, 1.0)

    df["aoi"] = np.degrees(np.arccos(cos_aoi))

    return df

def calcular_factores_perez(df_punto):
    df = df_punto.copy()

    kappa = 1.041

    coeficientes = [
        (1.000, 1.065, -0.008,  0.588, -0.062, -0.060,  0.072, -0.022),
        (1.065, 1.230,  0.130,  0.683, -0.151, -0.019,  0.066, -0.029),
        (1.230, 1.500,  0.330,  0.487, -0.221,  0.055, -0.064, -0.026),
        (1.500, 1.950,  0.568,  0.187, -0.295,  0.109, -0.152, -0.014),
        (1.950, 2.800,  0.873, -0.392, -0.362,  0.226, -0.462,  0.001),
        (2.800, 4.500,  1.132, -1.237, -0.412,  0.288, -0.823,  0.056),
        (4.500, 6.200,  1.060, -1.600, -0.359,  0.264, -1.127,  0.131),
        (6.200, np.inf, 0.678, -0.327, -0.250,  0.156, -1.377,  0.251),
    ]

    z_grados = df["zenith"].astype(float)
    z_rad = np.radians(z_grados)
    dni = df["dni"].astype(float)
    dhi = df["dhi"].astype(float)
    dia_del_anio = df["dia"].astype(int)

    dhi_seguro = dhi.replace(0, np.nan)

    df["epsilon"] = (
        ((dhi + dni) / dhi_seguro) + kappa * (z_rad ** 3)
    ) / (
        1 + kappa * (z_rad ** 3)
    )

    df["E0"] = 1361 * (
        1 + 0.033 * np.cos(np.radians(360 * dia_del_anio / 365))
    )

    zenith_limitado = z_grados.clip(upper=90)
    df["m_aire"] = 1 / (
        np.cos(np.radians(zenith_limitado)) +
        0.50572 * ((96.07995 - zenith_limitado) ** -1.6364)
    )

    df["delta"] = (dhi * df["m_aire"]) / df["E0"]

    df["a"] = np.nan
    df["b"] = np.nan
    df["c"] = np.nan
    df["d"] = np.nan
    df["e"] = np.nan
    df["f"] = np.nan

    for eps_min, eps_max, a, b, c, d, e, f in coeficientes:
        mascara = (df["epsilon"] >= eps_min) & (df["epsilon"] < eps_max)
        df.loc[mascara, ["a", "b", "c", "d", "e", "f"]] = [a, b, c, d, e, f]

    df["F1"] = df["a"] + df["b"] * df["delta"] + df["c"] * z_rad
    df["F2"] = df["d"] + df["e"] * df["delta"] + df["f"] * z_rad

    df["F1"] = df["F1"].clip(lower=0)
    df["F2"] = df["F2"].clip(lower=0)

    return df

def calcular_poa(df_punto, beta, albedo=0.2):
    df = df_punto.copy()

    beta_rad = np.radians(beta)
    aoi_rad = np.radians(df["aoi"].astype(float))
    zenith_rad = np.radians(df["zenith"].astype(float))

    dni = df["dni"].astype(float)
    dhi = df["dhi"].astype(float)
    ghi = df["ghi"].astype(float)
    f1 = df["F1"].astype(float)
    f2 = df["F2"].astype(float)

    cos_aoi = np.cos(aoi_rad)
    cos_zenith = np.cos(zenith_rad)

    cos_aoi = cos_aoi.clip(lower=0)
    cielo_valido = (df["zenith"] < 87) & (dni > 0) & (dhi > 0) & (cos_zenith > 0)
    ratio_circunsolar = np.where(cielo_valido, cos_aoi / cos_zenith, 0.0)

    df["Ib"] = dni * cos_aoi

    df["Iground"] = ghi * albedo * ((1 - np.cos(beta_rad)) / 2)

    df["Iiso"] = dhi * (1 - f1) * ((1 + np.cos(beta_rad)) / 2)
    df["Icir"] = dhi * f1 * ratio_circunsolar
    df["Ihor"] = dhi * f2 * np.sin(beta_rad)

    df["Id"] = df["Iiso"] + df["Icir"] + df["Ihor"]
    df["Id"] = df["Id"].clip(lower=0)

    df["POA"] = df["Ib"] + df["Iground"] + df["Id"]
    df["POA"] = df["POA"].clip(lower=0)

    return df

def calcular_perdidas_vidrio(df_punto, tipo_panel, n_vidrio=1.526, n_ar=1.3, n_aire=1.0):
    df = df_punto.copy()

    theta_aire = np.radians(df["aoi"].astype(float)).clip(0, np.pi / 2)
    poa = df["POA"].astype(float)

    def transmitancia_fresnel(theta_i, n1, n2):
        seno_theta_t = (n1 / n2) * np.sin(theta_i)
        seno_theta_t = np.clip(seno_theta_t, -1.0, 1.0)

        theta_t = np.arcsin(seno_theta_t)

        sen_suma = np.sin(theta_t + theta_i)
        sen_dif = np.sin(theta_t - theta_i)
        tan_suma = np.tan(theta_t + theta_i)
        tan_dif = np.tan(theta_t - theta_i)

        sen_suma = np.where(np.abs(sen_suma) < 1e-9, np.nan, sen_suma)
        tan_suma = np.where(np.abs(tan_suma) < 1e-9, np.nan, tan_suma)

        tau = 1 - 0.5 * (
            (sen_dif ** 2) / (sen_suma ** 2) +
            (tan_dif ** 2) / (tan_suma ** 2)
        )

        tau = np.nan_to_num(tau, nan=1.0, posinf=0.0, neginf=0.0)
        tau = np.clip(tau, 0.0, 1.0)

        return theta_t, tau

    if tipo_panel.lower() == "premium":
        theta_ar, tau_ar = transmitancia_fresnel(theta_aire, n_aire, n_ar)
        theta_vidrio, tau_vidrio = transmitancia_fresnel(theta_ar, n_ar, n_vidrio)

        df["theta_AR"] = np.degrees(theta_ar)
        df["theta_vidrio"] = np.degrees(theta_vidrio)
        df["tau_AR"] = tau_ar
        df["tau_vidrio"] = tau_vidrio
        df["tau_cover"] = tau_ar * tau_vidrio

    else:
        theta_vidrio, tau_cover = transmitancia_fresnel(theta_aire, n_aire, n_vidrio)

        df["theta_vidrio"] = np.degrees(theta_vidrio)
        df["tau_cover"] = tau_cover

    df["I_transmitida"] = poa * df["tau_cover"]

    return df

def calcular_temperatura_y_potencia_dc(df_punto, pdc0, tipo_panel, u0=25, u1=6, t_ref=25):
    df = df_punto.copy()

    if tipo_panel.lower() == "premium":
        gamma = -0.0035
    else:
        gamma = -0.0047

    temp_aire = df["temp_air"].astype(float)
    viento = df["wind_speed_2m"].astype(float)
    poa = df["POA"].astype(float)
    i_trans = df["I_transmitida"].astype(float)

    df["T_celda"] = temp_aire + (poa / (u0 + u1 * viento))

    df["P_DC"] = pdc0 * (i_trans / 1000) * (1 + gamma * (df["T_celda"] - t_ref))

    df["P_DC"] = df["P_DC"].clip(lower=0)

    return df

def calcular_potencia_ac(df_punto, p_inv, pdc0, eta_nom=0.96, eta_ref=0.9637):
    df = df_punto.copy()

    p_dc = df["P_DC"].astype(float)
    p_dc_bruta = df.get("P_DC_bruta", df["P_DC"]).astype(float)
    if p_inv <= 0:
        raise ValueError("La potencia nominal del inversor debe ser mayor a 0")
    if pdc0 <= 0:
        raise ValueError("La potencia nominal DC debe ser mayor a 0")

    ratio = p_dc_bruta / pdc0
    ratio_seguro = ratio.replace(0, np.nan)

    df["ratio"] = ratio

    df["rend"] = (eta_nom / eta_ref) * (-0.0162 * ratio - (0.0059 / ratio_seguro) + 0.9858)
    df["rend"] = df["rend"].fillna(0).clip(lower=0)

    df["P_AC"] = df["rend"] * p_dc
    df["P_AC"] = df["P_AC"].fillna(0).clip(upper=p_inv, lower=0)

    return df
