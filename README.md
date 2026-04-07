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
