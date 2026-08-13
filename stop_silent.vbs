Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "taskkill /F /IM pythonw.exe", 0, True
MsgBox "Sapphire Bot dan Web Dashboard berhasil dimatikan!", 64, "Sapphire Bot Control"
