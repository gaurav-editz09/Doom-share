#define AppVersion "1.0.0"

[Setup]
AppId={{F4AE7152-B958-4B73-BB3A-E9A15C8AE124}
AppName=Doom Desktop Assistant
AppVersion={#AppVersion}
AppPublisher=Hemadri
DefaultDirName={localappdata}\Programs\Doom
DefaultGroupName=Doom
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Doom-Setup
SetupIconFile=..\logo.ico
UninstallDisplayIcon={app}\Doom.exe
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\Doom\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Doom"; Filename: "{app}\Doom.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Doom"; Filename: "{app}\Doom.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Run]
Filename: "{app}\Doom.exe"; Description: "Launch Doom"; Flags: postinstall nowait skipifsilent
