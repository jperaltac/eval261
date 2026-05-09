# Evaluación de estudiantes

Aplicación de escritorio liviana para evaluar estudiantes con una rúbrica en JSON. Usa solo la biblioteca estándar de Python y Tkinter, por lo que no requiere instalar paquetes de `pip`.

## Requisitos

- Python 3.10 o superior.
- Tkinter disponible en la instalación de Python.

En Ubuntu, Debian o WSL normalmente basta con:

```bash
sudo apt update
sudo apt install python3 python3-tk
```

> En WSL necesitas tener salida gráfica habilitada. Windows 11 con WSLg suele funcionar sin configuración extra.

## Ejecutar en Linux o WSL

Desde la carpeta del proyecto:

```bash
python3 evaluation_app.py
```

También puedes indicar rutas personalizadas si quieres mantener los datos en otra carpeta:

```bash
python3 evaluation_app.py \
  --data-dir . \
  --rubric-file rubric.json \
  --students-file students.json \
  --evaluations-dir evaluations
```

Las evaluaciones guardadas se escriben en la carpeta `evaluations/` por defecto.

## Ejecutar en Windows nativo

Si tienes Python instalado desde python.org, puedes probar:

```powershell
py evaluation_app.py
```

## Archivos principales

- `evaluation_app.py`: interfaz y lógica de guardado.
- `rubric.json`: criterios, ponderaciones y niveles de logro.
- `students.json`: lista de estudiantes.
- `evaluations/`: salida generada automáticamente con una evaluación por estudiante.
