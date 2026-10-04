# Filtro de textos resaltados en Word

Requiere Python 3.10 o posterior. No necesita instalar paquetes.

## Construir Windows y Mac trabajando desde Linux

No existe un único ejecutable compatible con Windows y macOS. Este proyecto incluye una tarea de GitHub Actions que construye automáticamente las aplicaciones usando computadoras de GitHub con cada sistema operativo. Tú puedes seguir trabajando solamente desde Linux.

1. Sube el proyecto a un repositorio de GitHub.
2. En el repositorio abre **Actions** y selecciona **Compilar aplicaciones**.
3. Pulsa **Run workflow** y espera a que los tres trabajos terminen.
4. En la ejecución terminada, descarga los archivos de la sección **Artifacts**:
   - `TextFilter-Windows`
   - `TextFilter-Mac-Apple-Silicon`
   - `TextFilter-Mac-Intel`
5. Entrega a cada usuario el ZIP correspondiente. Ningún usuario final necesita Python.

La automatización está en `.github/workflows/compilar-aplicaciones.yml`. Se ejecuta manualmente para que puedas generar versiones nuevas solo cuando las necesites.

## Entregar a usuarios de Windows sin Python

El usuario final no necesita Python ni instalar paquetes. Recibe una carpeta con `TextFilter.exe`, hace doble clic y usa la aplicación desde el navegador que ya tenga instalado.

El ejecutable debe construirse una sola vez en una computadora con Windows y Python:

1. Copia este proyecto a una computadora con Windows.
2. Haz doble clic en `construir_windows.bat` y espera a que termine. La primera construcción necesita internet para descargar PyInstaller.
3. Encontrarás `TextFilter.exe` y la carpeta `input` dentro de `entrega`.
4. Comprime la carpeta `entrega` en ZIP y compártela completa. El usuario la descomprime y abre `TextFilter.exe`.

Los documentos agregados desde la interfaz se guardan en la carpeta `input` ubicada junto al ejecutable. Para salir, usa **Cerrar TextFilter** al final de la página. Windows puede mostrar una advertencia de SmartScreen porque el ejecutable no está firmado; se evita de forma profesional firmándolo con un certificado de firma de código.

El ejecutable generado en Windows funciona en Windows de 64 bits. macOS y Linux necesitan sus propias compilaciones; no existe un único ejecutable que funcione en los tres sistemas.

## Entregar a usuarios de macOS sin Python

El usuario final recibe `TextFilter.app` y no necesita Python. Para construirla una sola vez:

1. Copia el proyecto a una Mac con macOS 11 o posterior y Python 3.
2. Haz clic derecho en `construir_mac.command`, elige **Abrir** y confirma. La primera construcción necesita internet para descargar PyInstaller.
3. Al terminar encontrarás `TextFilter-mac.zip` dentro de `entrega-mac`.
4. Comparte ese ZIP. El usuario lo descomprime, mueve `TextFilter.app` a Aplicaciones y la abre.

Los DOCX agregados desde la interfaz se guardan en `Documentos/TextFilter/input` dentro de la cuenta del usuario. Esto permite conservarlos aunque se actualice o se mueva la aplicación.

La compilación debe hacerse en el mismo tipo de procesador que usarán los destinatarios: una Mac Apple Silicon genera la versión para Apple Silicon y una Mac Intel genera la versión Intel. Si necesitas atender ambos tipos, construye y distribuye dos ZIP identificados por arquitectura.

Una aplicación distribuida sin firma puede ser bloqueada por Gatekeeper. Para una prueba privada, el usuario puede hacer clic derecho en la aplicación y elegir **Abrir**. Para distribución general, firma y notariza la aplicación con una cuenta de Apple Developer.

## Interfaz gráfica

Ejecuta desde la carpeta del proyecto:

```bash
python3 app.py
```

Se abrirá una interfaz pequeña en tu navegador. Escribe el código (por ejemplo, `RCP3`) y pulsa **Buscar** o **Enter**. Los textos aparecen debajo con el nombre del documento y puedes seleccionarlos y copiarlos. Lee todos los DOCX de `input` y sus subcarpetas en cada búsqueda.

Usa **+ Agregar DOCX** para seleccionar uno o varios documentos desde la misma interfaz. Se guardan automáticamente en `input` y quedan disponibles para la siguiente búsqueda. Admite hasta 25 MB por archivo y comprueba que sea un DOCX válido. Si ya existe el nombre, conserva ambos archivos agregando un número al nuevo (por ejemplo, `entrevista (1).docx`). La interfaz confirma cada archivo guardado o indica el error correspondiente.

Los archivos guardados aparecen en **Documentos guardados**. Usa **Eliminar** y confirma para borrar definitivamente un DOCX de `input`; después vuelve a realizar la búsqueda para actualizar los resultados.

La interfaz funciona localmente, sin subir documentos a internet. Deja la terminal abierta mientras la utilizas; para detener el programa pulsa `Ctrl+C`. Si el navegador no se abre automáticamente, entra en la dirección que aparece en la terminal. También puedes usar `python3 app.py --no-browser`.

Las búsquedas gráficas muestran los resultados en pantalla. Para guardarlos en un archivo, puedes seguir usando la versión de terminal.

## Versión de terminal

1. Copia tus documentos `.docx` dentro de `input` (también busca en subcarpetas).
2. Desde esta carpeta ejecuta:

   ```bash
   python3 src/text_filter.py
   ```

3. Ingresa el código cuando el programa lo solicite.
4. Consulta las coincidencias en pantalla y en `output/resultados.txt`.

También puedes pasar el código directamente:

```bash
python3 src/text_filter.py ABC123
python3 src/text_filter.py "ABC 123" --input /ruta/documentos --output output/otra_busqueda.txt
```

Cada coincidencia incluye el archivo, la sección XML de Word y el número de párrafo dentro de esa sección (no es un número de página). El archivo de resultados se reemplaza en cada búsqueda; usa `--output` para conservar búsquedas diferentes. Los documentos originales no se modifican.

## Qué se considera una coincidencia

Se extraen fragmentos con fondo de color que terminan con el código ingresado. Se reconocen tanto el resaltador de Word como el sombreado del texto (el formato usado en el documento de ejemplo), de cualquier color. El subrayado por sí solo no cuenta como resaltado.

El código puede estar dentro del fragmento coloreado o inmediatamente después, sin color. Entre el fragmento y el código puede haber espacios o puntuación, pero no otras palabras ni saltos de línea. Se incluye el código en el resultado. También se permite puntuación final: `Texto ABC123,` coincide con `ABC123`.

La búsqueda distingue mayúsculas y minúsculas e ignora espacios exteriores. Dentro del texto coloreado, el código se trata como un sufijo literal: `XABC123` también termina con `ABC123`. Si está fuera del color, se comprueba que el código no continúe: `ABC1234` no coincide con `ABC123`.

Los paréntesis alrededor del código son opcionales. Buscar `RCP3` también encuentra `(RCP3)`, y buscar `(RCP3)` también encuentra `RCP3`.

## Catálogo de búsquedas

La interfaz acepta únicamente las categorías definidas: `CCP`, `DCP`, `RCP`, `FCP`, `LCP` y `FPCP`; sus subcódigos; o el nombre completo de una categoría o subcategoría. No distingue mayúsculas, acentos ni espacios dentro de un código. Por ejemplo, `CCP`, `ccp` y `C C P` seleccionan la misma categoría.

Una categoría completa reúne sus subcategorías: `CCP` busca `CCP1`, `CCP2` y `CCP3`. Una búsqueda por `CCP1` devuelve únicamente esa subcategoría. Escribir `Concepcion docente de la cultura de paz`, incluso sin tilde, equivale a buscar `CCP`.

Se unen las partes consecutivas del mismo fondo aunque cambien de fuente o negrita. Un cambio de fondo, un salto de línea o el final del párrafo separan los fragmentos. Se leen el cuerpo, las tablas, los encabezados, los pies de página y las notas al pie y finales. Se reconoce el fondo directo y el heredado de estilos de párrafo o carácter.

No se detectan colores dentro de imágenes, fondos aplicados a párrafos o celdas completas ni formato condicional de estilos de tabla. No admite `.doc`, documentos cifrados ni archivos que solo se hayan renombrado a `.docx`. Los archivos temporales de Word (`~$...`) se omiten. Si un documento falla, continúa con los demás y registra el error en los resultados.

Ejemplo con el documento incluido en `input`:

```bash
python3 src/text_filter.py RCP3
```

Para ejecutar las pruebas:

```bash
python3 -m unittest discover -s tests -v
```
