# Simulador fotovoltaico

Aplicacion en Streamlit para simular la generacion de energia fotovoltaica a partir de un dataset solar horario de la provincia de Santa Fe.

## Archivos principales

- `web.py`: interfaz web en Streamlit.
- `motor.py`: motor de calculo de irradiancia, perdidas y generacion.
- `dataset_solar_santa_fe_LOCAL.parquet`: dataset solar horario local versionado con Git LFS.
- `ciudades_con_coordenadas.csv`: catálogo de ciudades y coordenadas usado por la interfaz.

## Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run web.py
```

## Despliegue

El archivo de entrada para Streamlit es `web.py`.

## Desplegar en Streamlit Community Cloud

1. Inicia sesion en Streamlit Community Cloud con tu cuenta de GitHub.
2. Crea una nueva app desde el repositorio `DemianQuintana/simulador-fotovoltaico-v1.1`.
3. Selecciona la rama `main`.
4. Indica `web.py` como archivo principal.
5. Streamlit instalara las dependencias desde `requirements.txt` y descargara el `.parquet` versionado con Git LFS al clonar el repositorio.
