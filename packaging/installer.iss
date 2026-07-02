; Inno Setup script — builds a per-user installer wrapping the PyInstaller onedir.
;
; Prerequisites:
;   1. Build the app first:  .\packaging\build.ps1   (produces dist\NexShieldVeil\)
;   2. Install Inno Setup (https://jrsoftware.org/isinfo.php)
;   3. Compile:  iscc packaging\installer.iss
;
; Output: packaging\Output\NexShieldVeil-Setup.exe
; PrivilegesRequired=lowest -> installs into the user profile, no admin needed, so
; anyone can install and run it.

#define MyAppName "NexShieldVeil"
#define MyAppVersion "0.3.0"
#define MyAppExe "NexShieldVeil.exe"

[Setup]
AppId={{B7E5B0F2-9C3A-4B7E-9A1C-NEXSHIELDVEIL01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=NexShieldVeil
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename={#MyAppName}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "..\dist\NexShieldVeil\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent
