#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1

echo "Preparando el constructor de TextFilter para macOS..."
python3 -m venv .build-venv-mac || {
  echo "No se encontró Python 3. El usuario final no lo necesita; solo se requiere para construir la aplicación."
  read -r -p "Presiona Enter para cerrar."
  exit 1
}

source .build-venv-mac/bin/activate
python -m pip install --upgrade pip || exit 1
python -m pip install -r requirements-build.txt || exit 1

echo "Creando TextFilter.app..."
python -m PyInstaller --noconfirm --clean TextFilter-mac.spec || {
  echo "No se pudo construir TextFilter.app. Revisa los mensajes anteriores."
  read -r -p "Presiona Enter para cerrar."
  exit 1
}

mkdir -p entrega-mac
ditto -c -k --sequesterRsrc --keepParent dist/TextFilter.app entrega-mac/TextFilter-mac.zip

echo
echo "LISTO: entrega-mac/TextFilter-mac.zip"
echo "Comparte ese ZIP con usuarios de Mac que usen el mismo tipo de procesador."
read -r -p "Presiona Enter para cerrar."
