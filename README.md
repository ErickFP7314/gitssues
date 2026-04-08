# GitLab Issue Provisioner

Herramienta CLI para procesar archivos PDF estructurados y crear issues en GitLab automáticamente mediante su API REST. Desarrollado íntegramente en Python, sin dependencias externas de LLMs o APIs de procesamiento de lenguaje natural.

## Características
- **Parsing Determinista**: Utiliza expresiones regulares para extraer títulos, tipos, objetivos, alcances y dependencias.
- **Flujo en Dos Pasos**: Genera un archivo JSON intermedio para validación manual antes de subir a GitLab.
- **Markdown Automático**: Transforma los bloques del PDF en descripciones con formato Markdown profesional.
- **Seguro y Privado**: Procesamiento 100% local.

## Requisitos
- Python 3.10+
- `pip` (gestor de paquetes de Python)

## Instalación
1. Clonar o descargar este repositorio.
2. Crear un entorno virtual y activar:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # En Linux/macOS
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Configuración
Edita el archivo `config.env` con tus credenciales de GitLab:
```env
GITLAB_URL=https://gitlab.tu-instancia.com
GITLAB_TOKEN=tu_private_token
PROJECT_ID=tu_id_de_proyecto
```

## Uso

### Paso 1: Extracción de Issues (PDF -> JSON)
Ejecuta el comando `parse` para procesar el PDF y generar el JSON de revisión:
```bash
python main.py parse "archivo.pdf" --output issues.json
```
*Revisa el archivo `issues.json` generado para corregir cualquier detalle antes de la carga.*

### Paso 2: Carga a GitLab (JSON -> GitLab)
Una vez validado el JSON, sincroniza las issues con el proyecto:
```bash
python main.py upload issues.json
```
**Novedades Interactivas:**
Durante la carga, el CLI te preguntará opcionalmente por:
- **Etiquetas Globales**: Añadir etiquetas (ej: `Sprint-2`) a todas las issues procesadas.
- **Milestones**: Detecta automáticamente los milestones activos de tu proyecto y te permite seleccionar uno para asociar todas las issues.
- **Fechas**: Configurar una Fecha de Inicio y una Fecha Límite (`Due Date`) global para el lote de issues.

## Estructura del Proyecto
- `main.py`: Punto de entrada de la CLI.
- `parser.py`: Lógica de extracción de texto y Regex.
- `uploader.py`: Cliente de integración con la API de GitLab.
- `config.env`: Configuración de variables de entorno (Token, URL, ID).
- `requirements.txt`: Librerías requeridas.
