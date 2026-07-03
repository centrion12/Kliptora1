#define MyAppName "Kliptora"
#define MyAppVersion "2.3.3"
#define MyAppPublisher "Kliptora Tools"
#define MyAppExeName "Kliptora.exe"

[Setup]
AppId={{73CE6BD2-F20C-4EA4-A065-6D7D5E4960EA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Kliptora
DefaultGroupName=Kliptora
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=Kliptora-Setup-v{#MyAppVersion}
SetupIconFile=..\Kliptora\assets\app.ico
UninstallDisplayIcon={app}\Kliptora.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek kısayollar:"; Flags: checkedonce

[Files]
Source: "..\Kliptora\dist\Kliptora\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Kliptora"; Filename: "{app}\Kliptora.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Kliptora.exe"
Name: "{autodesktop}\Kliptora"; Filename: "{app}\Kliptora.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Kliptora.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Kliptora.exe"; Description: "Kliptora'yı başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
