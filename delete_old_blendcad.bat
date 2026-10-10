@echo off
echo Deleting legacy BlendCAD folder...
rmdir /s /q "C:\Users\brian\.gemini\antigravity-ide\scratch\BlendCAD"
if not exist "C:\Users\brian\.gemini\antigravity-ide\scratch\BlendCAD" (
    echo [SUCCESS] Legacy BlendCAD folder deleted successfully!
) else (
    echo [NOTICE] BlendCAD is still locked by the IDE or an active process.
    echo Please ensure the IDE has switched to ScriptCAD or is closed, then run this again.
)
pause
