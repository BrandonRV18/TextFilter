"""Busca fragmentos resaltados en DOCX sin dependencias externas."""

import argparse
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile


def application_root():
    """Carpeta persistente para documentos y resultados."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return Path.home() / "Documents" / "TextFilter"
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# En Windows vive junto al .exe; en macOS, fuera del paquete .app.
ROOT = application_root()
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def normalize_code(code):
    """Convierte CODE y (CODE) en el mismo valor de búsqueda."""
    if not isinstance(code, str):
        raise ValueError("El código no es válido.")
    code = code.strip()
    wrapped = re.fullmatch(r"\(\s*([^()]*)\s*\)", code)
    if wrapped:
        code = wrapped.group(1).strip()
    if not code:
        raise ValueError("El código no puede estar vacío.")
    if len(code) > 200:
        raise ValueError("El código debe tener como máximo 200 caracteres.")
    return code


def background(properties):
    """Lee resaltador y sombreado por separado para respetar su herencia."""
    values = {}
    if properties is None:
        return values
    highlight = properties.find("w:highlight", NS)
    if highlight is not None:
        color = highlight.get(W + "val", "none").lower()
        values["highlight"] = None if color in {"none", "auto"} else color
    shading = properties.find("w:shd", NS)
    if shading is not None:
        color = shading.get(W + "fill", "auto").lower()
        theme = shading.get(W + "themeFill")
        if shading.get(W + "val") == "nil":
            color = None
        elif theme:
            color = "theme:" + theme
        elif color in {"auto", "none"}:
            color = None
        values["shading"] = color
    return values


class Styles:
    def __init__(self, xml=None):
        self.styles = {}
        self.default_paragraph = None
        self.default_background = {}
        if xml is None:
            return
        root = ET.fromstring(xml)
        self.default_background = background(root.find("w:docDefaults/w:rPrDefault/w:rPr", NS))
        for style in root.findall("w:style", NS):
            identifier = style.get(W + "styleId")
            self.styles[identifier] = style
            if style.get(W + "type") == "paragraph" and style.get(W + "default") in {"1", "true", "on"}:
                self.default_paragraph = identifier

    def resolve(self, identifier, seen=None):
        seen = set() if seen is None else seen
        if identifier in seen or identifier not in self.styles:
            return {}
        seen.add(identifier)
        style = self.styles[identifier]
        base = style.find("w:basedOn", NS)
        values = self.resolve(base.get(W + "val"), seen) if base is not None else {}
        values.update(background(style.find("w:rPr", NS)))
        return values

    def run_background(self, paragraph, run):
        values = self.default_background.copy()
        paragraph_style = paragraph.find("w:pPr/w:pStyle", NS)
        identifier = paragraph_style.get(W + "val") if paragraph_style is not None else self.default_paragraph
        run_style = run.find("w:rPr/w:rStyle", NS)
        for style_id in (identifier, run_style.get(W + "val") if run_style is not None else None):
            values.update(self.resolve(style_id))
        values.update(background(run.find("w:rPr", NS)))
        return values.get("highlight") or values.get("shading")


def paragraph_segments(paragraph, styles):
    """Agrupa texto por fondo; conserva texto vecino para leer códigos sin color."""
    segments = []

    def runs(element):
        for child in element:
            if child.tag == W + "r":
                yield child
            elif child.tag not in {W + "p", W + "del"}:
                yield from runs(child)

    for run in runs(paragraph):
        color = styles.run_background(paragraph, run)
        for element in run:
            if element.tag in {W + "br", W + "cr"}:
                segments.append((None, "\n"))
                continue
            if element.tag == W + "t":
                text = element.text or ""
            elif element.tag == W + "tab":
                text = "\t"
            elif element.tag == W + "noBreakHyphen":
                text = "\u2011"
            elif element.tag == W + "softHyphen":
                text = "\u00ad"
            else:
                continue
            if not text:
                continue
            if segments and segments[-1][0] == color and "\n" not in segments[-1][1]:
                segments[-1] = (color, segments[-1][1] + text)
            else:
                segments.append((color, text))
    return segments


def matching_fragments(paragraph, styles, code):
    segments = paragraph_segments(paragraph, styles)
    # CODE y (CODE) son equivalentes; también se permite puntuación cercana.
    literal = re.escape(code)
    formatted = rf"(?:\(\s*{literal}\s*\)|{literal})"
    following = rf"(?:\(\s*{literal}\s*\)(?!\w)|{literal}(?![\w)]))"
    trailing_code = re.compile(formatted + r"[\s.,;:!?…]*$")
    following_code = re.compile(r"^[ \t.,;:!?…]*" + following + r"[ \t.,;:!?…]*")
    for index, (color, text) in enumerate(segments):
        if color is None or not text.strip():
            continue
        if trailing_code.search(text):
            yield text.strip()
        elif index + 1 < len(segments):
            next_color, next_text = segments[index + 1]
            match = following_code.match(next_text) if next_color is None else None
            if match:
                yield (text + match.group()).strip()


def extract_matches(path, code):
    code = normalize_code(code)
    matches = []
    with ZipFile(path) as archive:
        names = archive.namelist()
        if "word/document.xml" not in names:
            raise ValueError("No contiene el documento principal de Word")
        styles = Styles(archive.read("word/styles.xml") if "word/styles.xml" in names else None)
        parts = ["word/document.xml"] + sorted(
            name for name in names
            if re.fullmatch(r"word/(?:header\d+|footer\d+|footnotes|endnotes)\.xml", name)
        )
        for part in parts:
            root = ET.fromstring(archive.read(part))
            for number, paragraph in enumerate(root.iter(W + "p"), 1):
                for text in matching_fragments(paragraph, styles, code):
                    matches.append((part, number, text))
    return matches


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extrae textos resaltados que terminan con un código.")
    parser.add_argument("codigo", nargs="?", help="Código final (distingue mayúsculas y minúsculas)")
    parser.add_argument("--input", type=Path, default=ROOT / "input", help="Carpeta de documentos DOCX")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "resultados.txt", help="Archivo de resultados")
    args = parser.parse_args(argv)
    try:
        code = normalize_code(args.codigo if args.codigo is not None else input("Ingrese el código a buscar: "))
    except (EOFError, KeyboardInterrupt):
        print("\nBúsqueda cancelada.", file=sys.stderr)
        return 1
    except ValueError as exc:
        parser.error(str(exc))
    if not args.input.is_dir():
        parser.error(f"No existe la carpeta de entrada: {args.input}")
    files = sorted(path for path in args.input.rglob("*") if path.is_file() and path.suffix.lower() == ".docx" and not path.name.startswith("~$"))
    if not files:
        print(f"No se encontraron documentos DOCX en {args.input}.")
        return 1
    lines = [f"Código buscado: {code}", f"Documentos encontrados: {len(files)}", ""]
    total = 0
    errors = []
    for path in files:
        try:
            matches = extract_matches(path, code)
        except (BadZipFile, ET.ParseError, OSError, KeyError, ValueError, RuntimeError, NotImplementedError) as exc:
            errors.append(f"{path.relative_to(args.input)}: {exc}")
            continue
        for part, number, text in matches:
            total += 1
            lines.extend([f"[{total}] {path.relative_to(args.input)} | {part} | párrafo {number}", text, ""])
    lines.append(f"Total de coincidencias: {total}")
    if errors:
        lines.extend(["", "Documentos que no se pudieron leer:", *errors])
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"No se pudieron guardar los resultados: {exc}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    print(f"\nResultados guardados en: {args.output.resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
