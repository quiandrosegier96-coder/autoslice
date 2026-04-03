; AutoSlice Windows Installer
; Inno Setup 6 script
; Requires the dist/ folder to be built first (run build.ps1)

#define AppName "AutoSlice"
#define AppVersion "1.3.39"
#define AppPublisher "AutoSlice"
#define AppURL "http://localhost:3000"
#define AppExeName "AutoSlice.exe"

[Setup]
AppId={{8A4E2C1B-3F7D-4E9A-B2C5-6D8F0A1E4B9C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=
OutputDir=..\dist\installer
OutputBaseFilename=AutoSliceSetup_{#AppVersion}
; Compress well — the bundle is large
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Require admin so we can write to Program Files
PrivilegesRequired=admin
; 64-bit
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "dutch";   MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon";  Description: "Start Menu shortcut";     GroupDescription: "{cm:AdditionalIcons}"
Name: "startupentry";   Description: "Start AutoSlice when Windows starts"; GroupDescription: "Startup"; Flags: unchecked

[Files]
; Launcher executable
Source: "..\dist\AutoSlice.exe";           DestDir: "{app}";          Flags: ignoreversion

; Backend (PyInstaller folder bundle)
Source: "..\dist\autoslice_backend\*";     DestDir: "{app}\backend";  Flags: ignoreversion recursesubdirs createallsubdirs

; Frontend (Next.js standalone)
Source: "..\dist\frontend\*";              DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs

; Portable Node.js
Source: "..\dist\node\*";                  DestDir: "{app}\node";     Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";                 Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";       Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";         Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";           Filename: "{app}\{#AppExeName}"; Tasks: startupentry

[Run]
; Launch after install
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Make sure both processes are stopped before uninstall
Filename: "taskkill"; Parameters: "/F /IM autoslice_backend.exe"; Flags: runhidden; RunOnceId: "KillBackend"
Filename: "taskkill"; Parameters: "/F /IM node.exe /FI ""WINDOWTITLE eq AutoSlice*"""; Flags: runhidden; RunOnceId: "KillFrontend"
Filename: "taskkill"; Parameters: "/F /IM AutoSlice.exe"; Flags: runhidden; RunOnceId: "KillLauncher"
