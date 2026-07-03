# Kliptora v2.3.5 Windows Build

Bu sürümde FFmpeg ve Deno kurulum paketine doğrudan eklenir. Kullanıcı ilk açılışta ek araç indirmek zorunda kalmaz. Ayarlardaki düğmeler yalnızca kontrol / onarım amacıyla kalır ve uygulamayı kapatmaz.

## Kurulum EXE'si oluşturma

1. Bu paketin içeriğini GitHub reposunun köküne yükle.
2. `.github/workflows/build-release.yml` dosyasının doğru konumda olduğundan emin ol.
3. GitHub'da **Actions → Build Kliptora v2.3.5 Setup → Run workflow** seç.
4. İşlem tamamlanınca **Artifacts → Kliptora-v2.3.5-Windows** paketini indir.

Çıktı:
- `Kliptora-Setup-v2.3.5.exe`
- `Kliptora-Setup-v2.3.5.sha256.txt`

Workflow FFmpeg ve ffprobe dosyalarını BtbN'in LGPL Windows buildinden indirir,
uygulamaya paketler, ardından hem açık uygulama klasörünü hem Setup.exe'yi
Microsoft Defender ile tarar.
