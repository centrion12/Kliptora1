# Kliptora v2.3.3 — Windows installer build

Bu depo GitHub Actions üzerindeki gerçek bir Windows runner'da Kliptora'yı derler.

## Manuel derleme

- Python 3.12 x64
- Inno Setup 6

PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build.ps1
```

Çıktı:

```text
release\Kliptora-Setup-v2.3.3.exe
```

## GitHub Actions

Actions > Build clean Windows installer > Run workflow.
İş tamamlandıktan sonra Artifacts bölümünden `Kliptora-v2.3.3-Windows` indirilir.

Derleme PyInstaller one-folder modunda, UPX olmadan yapılır. Kurulum Inno Setup ile üretilir.
Workflow kaynakları derler, bağımlılıkları içe aktarır, SHA-256 üretir ve mümkünse Microsoft Defender özel taraması çalıştırır.
