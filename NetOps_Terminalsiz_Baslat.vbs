Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = appDir & "\asistan_beta.pyw"

pythonw = shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python313\pythonw.exe"
If Not fso.FileExists(pythonw) Then
    pythonw = shell.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python314\pythonw.exe"
End If
If Not fso.FileExists(pythonw) Then
    pythonw = "pythonw.exe"
End If

shell.CurrentDirectory = appDir
shell.Run """" & pythonw & """ """ & scriptPath & """", 0, False
