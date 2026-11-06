@echo off
setlocal
cd /d "%~dp0"
title Espectrometro AS7341 - Criar executavel
color 0D

echo ======================================================
echo   ESPECTROMETRO DIDATICO AS7341 - CRIAR EXE
echo ======================================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
 echo ERRO: Python nao foi encontrado.
 echo Instale o Python no Windows e marque Add Python to PATH.
 pause
 exit /b 1
)

echo Instalando dependencias e PyInstaller...
python -m pip install pyserial matplotlib numpy scipy pyinstaller pillow
if errorlevel 1 (
 echo FALHA: confira a internet e o Python neste computador.
 pause
 exit /b 1
)

echo.
echo Criando executavel Windows com icone...
python -m PyInstaller --noconfirm --clean Espectrometro_AS7341.spec
if errorlevel 1 (
 echo FALHA: o executavel nao foi gerado.
 pause
 exit /b 1
)

echo.
echo ======================================================
echo   CONCLUIDO
echo ======================================================
echo Copie o arquivo da pasta dist:
echo dist\Espectrometro_AS7341.exe
echo.
pause
endlocal
