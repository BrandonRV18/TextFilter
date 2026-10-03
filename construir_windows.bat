@echo off
setlocal
cd /d "%~dp0"

echo Preparando el constructor de TextFilter...
py -3 -m venv .build-venv
if errorlevel 1 goto :python_error

call .build-venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :build_error
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :build_error

echo Creando TextFilter.exe...
python -m PyInstaller --noconfirm --clean TextFilter.spec
if errorlevel 1 goto :build_error

if not exist entrega mkdir entrega
copy /y dist\TextFilter.exe entrega\TextFilter.exe >nul
if not exist entrega\input mkdir entrega\input

echo.
echo LISTO: la aplicacion esta en entrega\TextFilter.exe
echo Entrega la carpeta "entrega" completa al usuario.
pause
exit /b 0

:python_error
echo.
echo No se encontro Python para construir el ejecutable.
echo El usuario final no lo necesita; solo se requiere en la PC que lo construye.
pause
exit /b 1

:build_error
echo.
echo No se pudo construir TextFilter.exe. Revisa los mensajes anteriores.
pause
exit /b 1
