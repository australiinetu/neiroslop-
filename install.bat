@echo off
chcp 65001 >nul
echo Устанавливаю pygame-ce...
python -m pip install --upgrade pygame-ce
if errorlevel 1 (
    echo.
    echo Не получилось. Проверь, что Python установлен и добавлен в PATH ^(см. ГАЙД.txt^).
) else (
    echo.
    echo Готово! Теперь запускай игру через start.bat
)
pause
