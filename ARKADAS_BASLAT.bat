@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title NetOps Asistan - Baslatici

echo ============================================================
echo    NETOPS ASISTAN  -  Baslatici
echo ============================================================
echo.
echo  Bu dosya, kaynak (.py) dosyalarini calistirmak icindir.
echo  Python ve gerekli paketler yoksa once onlari kurar.
echo.

rem ---------- 1) Python kurulu mu? ----------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY where python3 >nul 2>&1 && set "PY=python3"
if not defined PY goto :nopython

echo [OK] Python bulundu.
%PY% --version
echo.

rem ---------- 2) Gerekli paketler var mi? ----------
echo Paketler kontrol ediliyor...
%PY% -c "import customtkinter, PIL, pygame, requests, flask, psutil, websockets" >nul 2>&1
if not errorlevel 1 goto :run

echo.
echo [BILGI] Gerekli paketlerden bazilari eksik.
echo.
echo   DIKKAT: Bu islem 2-3 GB indirme yapar ve
echo           birkac dakika (bazen 10+ dk) surebilir.
echo.
choice /c EH /n /m "Paketleri simdi kurmak istiyor musunuz? (E=Evet  H=Hayir) "
if errorlevel 2 goto :run
echo.
echo Paketler kuruluyor, lutfen bekleyin...
echo.
%PY% -m pip install --upgrade pip setuptools wheel
%PY% -m pip install -r requirements_live.txt
if errorlevel 1 (
  echo.
  echo [UYARI] Paket kurulumunda hata olustu.
  echo         Yukaridaki kirmizi mesajlari not alin.
  echo.
)
echo Paket kurulumu bitti.
echo.

:run
echo ============================================================
echo    NetOps baslatiliyor...
echo.
echo    ONEMLI: Bu pencereyi KAPATMAYIN.
echo    Program normalde hatasini gizler; bu pencere
echo    sayesinde hata olursa burada gorunecek.
echo ============================================================
echo.

rem Hatalarin gorunmesi icin: konsolu kapatma
set "NETOPS_KEEP_CONSOLE=1"

%PY% "asistan beta.py"

echo.
echo ============================================================
echo    NetOps kapandi.  Cikis kodu: %ERRORLEVEL%
echo.
echo    Yukarida bir hata mesaji varsa, o mesaji kopyalayip
echo    gelistiriciye gonderin. Sorun bu olmadan bulunamaz.
echo ============================================================
echo.
pause
exit /b 0

:nopython
echo ============================================================
echo  [HATA] Bu bilgisayarda Python bulunamadi.
echo ============================================================
echo.
echo  Kaynak (.py) dosyalari tek basina CALISMAZ - bunlar
echo  program degil, programin kaynak kodudur. Calismalari
echo  icin Python ve ~24 adet kutuphane gerekir.
echo.
echo  Cozum:
echo    1) https://www.python.org/downloads/ adresine gidin
echo    2) Python 3.12 veya 3.13 surumunu indirip kurun
echo       (3.14 ONERILMEZ - bazi paketlerin hazir derlemesi yok)
echo    3) Kurulum ekraninda "Add python.exe to PATH"
echo       kutusunu MUTLAKA isaretleyin
echo    4) Bilgisayari yeniden baslatin
echo    5) Bu dosyayi tekrar calistirin
echo.
echo  ALTERNATIF (daha kolay):
echo    Python kurmak yerine hazir paketi kullanin:
echo      dist\NetOps.exe   veya   Output\Netops Setup.exe
echo    Bu dosyalar Python gerektirmez, her sey icindedir.
echo.
pause
exit /b 1
