"""Interfaz web local, servida únicamente en este equipo."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import io
import os
from pathlib import Path
from pathlib import PurePosixPath
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit
import webbrowser
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from .categories import catalog_options, resolve_query
from .text_filter import ROOT, extract_matches

MAX_UPLOAD = 25 * 1024 * 1024


def document_paths(folder):
    """Devuelve únicamente DOCX normales contenidos en input."""
    folder = ROOT / "input" if folder is None else Path(folder)
    if not folder.exists():
        return []
    return sorted(path for path in folder.rglob("*") if path.is_file()
                  and not path.is_symlink() and path.suffix.lower() == ".docx"
                  and not path.name.startswith("~$"))


def list_documents(folder=None):
    folder = ROOT / "input" if folder is None else Path(folder)
    return [{"name": path.relative_to(folder).as_posix(), "size": path.stat().st_size}
            for path in document_paths(folder)]


def delete_document(name, folder=None):
    folder = ROOT / "input" if folder is None else Path(folder)
    if not isinstance(name, str) or not name or len(name.encode("utf-8")) > 500 or "\\" in name:
        raise ValueError("El nombre del documento no es válido.")
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("El nombre del documento no es válido.")
    candidate = folder.joinpath(*relative.parts)
    if candidate.suffix.lower() != ".docx" or candidate.name.startswith(("~$", ".")):
        raise ValueError("Solo se pueden eliminar documentos DOCX de input.")
    try:
        root = folder.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError("El documento ya no existe.") from exc
    if not resolved.is_relative_to(root) or not candidate.is_file() or candidate.is_symlink():
        raise ValueError("El documento no pertenece a input.")
    candidate.unlink()
    return relative.as_posix()


def save_document(name, content, folder=None):
    folder = ROOT / "input" if folder is None else Path(folder)
    if (not isinstance(name, str) or not name or len(name.encode('utf-8')) > 200
            or any(char in name for char in '/\\') or any(ord(char) < 32 for char in name)
            or name.startswith(('~$', '.')) or Path(name).suffix.lower() != '.docx'):
        raise ValueError("Selecciona un archivo DOCX con un nombre válido.")
    if not content or len(content) > MAX_UPLOAD:
        raise ValueError("Cada archivo debe pesar entre 1 byte y 25 MB.")
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("El documento es demasiado grande al descomprimirlo.")
            root = ET.fromstring(archive.read('word/document.xml'))
            if root.tag != '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document':
                raise ValueError("El archivo no contiene un documento Word válido.")
            if archive.testzip() is not None:
                raise ValueError("El documento está dañado.")
    except (BadZipFile, KeyError, ET.ParseError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("El archivo no es un DOCX válido o está protegido con contraseña.") from exc
    folder.mkdir(parents=True, exist_ok=True)
    # Reservar un nombre sin reemplazar archivos y publicar la carga completa.
    descriptor, temporary_name = tempfile.mkstemp(dir=folder, prefix='.upload-', suffix='.tmp')
    temp_path = Path(temporary_name)
    candidate = folder / name
    try:
        with os.fdopen(descriptor, 'wb') as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        number = 1
        while True:
            try:
                candidate.touch(exist_ok=False)
                break
            except FileExistsError:
                candidate = folder / f"{Path(name).stem} ({number}).docx"
                number += 1
        os.replace(temp_path, candidate)
    except Exception:
        candidate.unlink(missing_ok=True)
        raise
    finally:
        temp_path.unlink(missing_ok=True)
    return candidate.name


def search_documents(code, folder=None):
    folder = ROOT / "input" if folder is None else Path(folder)
    selection = resolve_query(code)
    if not folder.is_dir():
        raise ValueError("No existe la carpeta input. Créala y coloca allí tus documentos DOCX.")
    files = document_paths(folder)
    results, errors = [], []
    for path in files:
        try:
            found = {}
            for selected_code in selection["codes"]:
                for part, paragraph, text in extract_matches(path, selected_code):
                    found[(part, paragraph, text)] = {"file": path.relative_to(folder).as_posix(),
                                                      "text": text, "code": selected_code}
            for key in sorted(found, key=lambda item: (item[0], item[1], item[2])):
                results.append(found[key])
        except (BadZipFile, ET.ParseError, OSError, KeyError, ValueError, RuntimeError, NotImplementedError):
            relative = path.relative_to(folder).as_posix()
            errors.append(f"No se pudo leer {relative}. Comprueba que sea un DOCX válido y sin contraseña.")
    return {"code": selection["query"], "label": selection["label"],
            "codes": selection["codes"], "documents": len(files),
            "results": results, "errors": errors}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status, data):
        self.respond(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        route = urlsplit(self.path)
        if route.path == "/api/documents":
            try:
                self.json_response(200, {"documents": list_documents()})
            except OSError:
                self.json_response(500, {"error": "No se pudo leer la lista de documentos."})
            return
        if route.path == "/api/catalog":
            self.json_response(200, {"options": catalog_options()})
            return
        if route.path != "/":
            self.send_error(404)
            return
        self.respond(200, Path(__file__).with_name("index.html").read_bytes(), "text/html; charset=utf-8")

    def valid_origin(self):
        origin = self.headers.get("Origin")
        return not origin or origin == f"http://127.0.0.1:{self.server.server_port}"

    def do_DELETE(self):
        route = urlsplit(self.path)
        if route.path != "/api/documents":
            self.send_error(404)
            return
        if not self.valid_origin():
            self.json_response(403, {"error": "Abre la interfaz desde su dirección local."})
            return
        try:
            name = parse_qs(route.query).get("name", [""])[0]
            deleted = delete_document(name)
        except FileNotFoundError as exc:
            self.json_response(404, {"error": str(exc)})
            return
        except ValueError as exc:
            self.json_response(400, {"error": str(exc)})
            return
        except OSError:
            self.json_response(500, {"error": "No se pudo eliminar el documento."})
            return
        self.json_response(200, {"file": deleted})

    def do_POST(self):
        route = urlsplit(self.path)
        if route.path not in {"/api/search", "/api/upload", "/api/shutdown"}:
            self.send_error(404)
            return
        # Solo la página local puede enviar búsquedas desde un navegador.
        if not self.valid_origin():
            self.json_response(403, {"error": "Abre la interfaz desde su dirección local."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if route.path == "/api/shutdown":
                if length:
                    self.rfile.read(length)
                self.json_response(200, {"message": "TextFilter cerrado."})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if route.path == "/api/upload":
                if not 0 < length <= MAX_UPLOAD:
                    raise ValueError("Cada archivo debe pesar entre 1 byte y 25 MB.")
                if self.headers.get_content_type() != 'application/octet-stream':
                    raise ValueError("El formato de la carga no es válido.")
                name = parse_qs(route.query).get('name', [''])[0]
                content = self.rfile.read(length)
                if len(content) != length:
                    raise ValueError("La carga del archivo quedó incompleta. Inténtalo de nuevo.")
                saved = save_document(name, content)
                self.json_response(201, {"file": saved})
                return
            if not 0 < length <= 4096:
                raise ValueError("La solicitud de búsqueda no es válida.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("La solicitud de búsqueda no es válida.")
            data = search_documents(payload.get("code"))
        except (ValueError, UnicodeError) as exc:
            self.json_response(400, {"error": str(exc)})
            return
        except OSError:
            self.json_response(500, {"error": "No se pudo acceder a los documentos de input."})
            return
        self.json_response(200, data)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Interfaz gráfica local de TextFilter")
    parser.add_argument("--no-browser", action="store_true", help="No abrir automáticamente el navegador")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"TextFilter está disponible en {url}", flush=True)
        print("Para cerrar el programa usa el botón de la interfaz o presiona Ctrl+C.", flush=True)
        if not args.no_browser:
            threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nTextFilter cerrado.")
