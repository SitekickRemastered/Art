@echo off
setlocal enabledelayedexpansion

set "sourceDir=%CD%"
set "destinationDir=%sourceDir%\Processed"

mkdir "%destinationDir%" 2>nul

for /D %%i in (*_chip_*) do (
    set "folderName=%%i"
    set "fileNumber=!folderName:~-4!"
    set "newFileName=chip_!fileNumber!_icon.png"
    
    ren "!sourceDir!\!folderName!\1.png" "!newFileName!"
    copy /Y "!sourceDir!\!folderName!\!newFileName!" "!destinationDir!\"
)

echo Task completed.
pause
