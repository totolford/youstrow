; Installeur YouStrow — compiler avec : ISCC installer\youstrow.iss  (ou .\build.ps1)
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{6C1F6E0B-2B7A-4C59-9A4E-5D0B7B1E9F11}
AppName=YouStrow
AppVersion={#AppVersion}
AppPublisher=YouStrow
AppPublisherURL=https://github.com/totolford/youstrow
DefaultDirName={autopf}\YouStrow
DefaultGroupName=YouStrow
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=YouStrow-Setup-{#AppVersion}
SetupIconFile=..\assets\youstrow.ico
UninstallDisplayIcon={app}\YouStrow.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
ChangesAssociations=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "Associer les fichiers de show (.ysshow) à YouStrow"; GroupDescription: "Fichiers :"

[Files]
Source: "..\dist\YouStrow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\YouStrow"; Filename: "{app}\YouStrow.exe"
Name: "{group}\{cm:UninstallProgram,YouStrow}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\YouStrow"; Filename: "{app}\YouStrow.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.ysshow"; ValueType: string; ValueName: ""; ValueData: "YouStrow.Show"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\YouStrow.Show"; ValueType: string; ValueName: ""; ValueData: "Show YouStrow"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\YouStrow.Show\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\YouStrow.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\YouStrow.Show\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\YouStrow.exe"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\YouStrow.exe"; Description: "{cm:LaunchProgram,YouStrow}"; Flags: nowait postinstall skipifsilent

; Les données utilisateur (%APPDATA%\YouStrow : réglages, MIDI) sont VOLONTAIREMENT conservées à la désinstallation.
