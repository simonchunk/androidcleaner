#define MyAppName "The iPhone Guy - Android Cleaner"
#define MyAppVersion "0.18.5"
#define MyAppPublisher "The iPhone Guy"
#define MyAppExeName "AndroidCleaner.exe"

[Setup]
AppId={{BFB9DDB4-493B-4CB7-A2CF-77D8C2472D11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\The iPhone Guy\Android Cleaner
DefaultGroupName=The iPhone Guy
DisableProgramGroupPage=yes
OutputDir=installer-output
OutputBaseFilename=The-iPhone-Guy-Android-Cleaner-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "package\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\The iPhone Guy\Android Cleaner"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Android Cleaner"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Android Cleaner"; Flags: nowait postinstall skipifsilent
