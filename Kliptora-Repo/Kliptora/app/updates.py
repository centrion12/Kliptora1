from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import socket
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from .core import APP_FULL_NAME, APP_SLUG, APP_USER_AGENT
from .version import APP_VERSION

GITHUB_API = "https://api.github.com"


def _ssl_context() -> ssl.SSLContext:
    """Create a TLS context that also works in the embedded Windows runtime."""
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _urlopen(request: urllib.request.Request, timeout: int):
    return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())


def version_key(value: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", value)[:4]]
    return tuple((numbers + [0, 0, 0, 0])[:4])


def is_newer(remote: str, current: str = APP_VERSION) -> bool:
    return version_key(remote) > version_key(current)


def _request(
    url: str,
    *,
    token: str = "",
    method: str = "GET",
    data: bytes | None = None,
    content_type: str = "application/json",
    accept: str = "application/vnd.github+json",
) -> urllib.request.Request:
    headers = {
        "Accept": accept,
        "User-Agent": APP_USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = content_type
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def _read_json(request: urllib.request.Request, timeout: int = 12) -> dict[str, Any]:
    try:
        with _urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("message", body)
        except Exception:
            message = body
        raise RuntimeError(f"GitHub hatası ({exc.code}): {message}") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"GitHub bağlantısı zaman aşımına uğradı veya kurulamadı: {reason}") from exc
    except ssl.SSLError as exc:
        raise RuntimeError(f"GitHub güvenli bağlantısı kurulamadı: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub geçersiz bir yanıt döndürdü.") from exc


def repository_info(owner: str, repo: str, token: str = "") -> dict[str, Any]:
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        raise ValueError("GitHub kullanıcı/organizasyon ve depo adını gir.")
    url = f"{GITHUB_API}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return _read_json(_request(url, token=token))


def latest_release(owner: str, repo: str, token: str = "") -> dict[str, Any]:
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        raise ValueError("Güncelleme deposu henüz ayarlanmamış.")
    url = f"{GITHUB_API}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/releases/latest"
    try:
        return _read_json(_request(url, token=token), timeout=12)
    except RuntimeError as exc:
        if "GitHub hatası (404)" in str(exc):
            raise RuntimeError("Henüz yayınlanmış bir GitHub Release yok. Yönetici bölümünden ilk sürümü yayınla.") from exc
        raise


def _asset_name(asset: dict[str, Any]) -> str:
    return str(asset.get("name") or "")


def select_update_assets(release: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    assets = release.get("assets") or []
    zips = [a for a in assets if _asset_name(a).lower().endswith(".zip")]
    preferred = [a for a in zips if APP_SLUG.lower() in _asset_name(a).lower()]
    zip_asset = (preferred or zips or [None])[0]
    sha_asset = None
    if zip_asset:
        zip_name = _asset_name(zip_asset)
        candidates = {
            f"{zip_name}.sha256".lower(),
            str(Path(zip_name).with_suffix(".sha256")).lower(),
        }
        sha_asset = next((a for a in assets if _asset_name(a).lower() in candidates), None)
    return zip_asset, sha_asset


def _create_release(owner: str, repo: str, token: str, version: str, title: str, body: str, prerelease: bool) -> dict[str, Any]:
    normalized = version.strip().lstrip("v")
    if not normalized:
        raise ValueError("Sürüm numarası boş olamaz.")
    tag = f"v{normalized}"
    payload = json.dumps(
        {
            "tag_name": tag,
            "name": title.strip() or f"{APP_FULL_NAME} {tag}",
            "body": body,
            "draft": True,
            "prerelease": bool(prerelease),
            "generate_release_notes": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    url = f"{GITHUB_API}/repos/{urllib.parse.quote(owner.strip())}/{urllib.parse.quote(repo.strip())}/releases"
    try:
        return _read_json(_request(url, token=token, method="POST", data=payload))
    except RuntimeError as exc:
        if "422" not in str(exc):
            raise
        by_tag = f"{GITHUB_API}/repos/{urllib.parse.quote(owner.strip())}/{urllib.parse.quote(repo.strip())}/releases/tags/{urllib.parse.quote(tag)}"
        return _read_json(_request(by_tag, token=token))


def _update_release(release: dict[str, Any], token: str, *, title: str, body: str, draft: bool, prerelease: bool) -> dict[str, Any]:
    url = str(release.get("url") or "")
    if not url:
        raise RuntimeError("Sürüm güncelleme adresi alınamadı.")
    payload = json.dumps(
        {
            "name": title,
            "body": body,
            "draft": bool(draft),
            "prerelease": bool(prerelease),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    return _read_json(_request(url, token=token, method="PATCH", data=payload))


def upload_release_asset(release: dict[str, Any], token: str, asset_path: Path) -> dict[str, Any]:
    if not asset_path.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {asset_path}")
    upload_url = str(release.get("upload_url") or "").split("{")[0]
    if not upload_url:
        raise RuntimeError("GitHub yükleme adresi alınamadı.")

    asset_name = asset_path.name
    for asset in release.get("assets") or []:
        if _asset_name(asset) == asset_name and asset.get("url"):
            try:
                with _urlopen(_request(str(asset["url"]), token=token, method="DELETE"), timeout=45):
                    pass
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise

    query = urllib.parse.urlencode({"name": asset_name})
    data = asset_path.read_bytes()
    content_type = mimetypes.guess_type(asset_name)[0] or "application/octet-stream"
    return _read_json(
        _request(f"{upload_url}?{query}", token=token, method="POST", data=data, content_type=content_type),
        timeout=300,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256_file(path: Path) -> Path:
    checksum = sha256_file(path)
    output = path.with_name(path.name + ".sha256")
    output.write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
    return output


def build_update_package(
    source_dir: Path,
    output_zip: Path,
    *,
    version: str,
    owner: str,
    repo: str,
) -> tuple[Path, Path]:
    """Build a small, safe in-place update package.

    Application code/assets and the explicit yt-dlp engine dependency set are archived.
    The rest of the embedded Python runtime, installer, uninstaller, running
    executables, caches and user data are deliberately excluded. This keeps package creation fast and avoids
    touching files that Windows may have locked while Kliptora is running.
    """
    source_dir = source_dir.expanduser().resolve()
    output_zip = output_zip.expanduser().resolve()

    if not (source_dir / "main.py").is_file() or not (source_dir / "app" / "main_window.py").is_file():
        raise ValueError(f"Seçilen klasör {APP_FULL_NAME} uygulama kökü değil.")

    normalized_version = version.strip().lstrip("v")
    if version_key(normalized_version) <= (0, 0, 0, 0):
        raise ValueError("Geçerli bir sürüm numarası gir.")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.suffix.lower() != ".zip":
        output_zip = output_zip.with_suffix(".zip")

    # Explicit allow-list: never walk the full embedded runtime/install tree.
    included: list[Path] = []
    for relative in ("main.py", "updater_qt.pyw"):
        candidate = source_dir / relative
        if candidate.is_file():
            included.append(candidate)

    for folder_name in ("app", "assets"):
        folder = source_dir / folder_name
        if not folder.is_dir():
            continue
        for candidate in folder.rglob("*"):
            if not candidate.is_file():
                continue
            if "__pycache__" in candidate.parts or candidate.suffix.lower() in {".pyc", ".pyo"}:
                continue
            if folder_name == "app" and candidate.suffix.lower() not in {".py", ".json"}:
                continue
            included.append(candidate)

    # Engine bundles are part of the update package. Site fixes (especially
    # Instagram/YouTube) often require a newer yt-dlp plus optional request
    # handlers such as curl-cffi. Only the explicit engine dependency set is
    # included; PySide, pip and the rest of the embedded runtime stay out.
    site_packages = source_dir / "runtime" / "Lib" / "site-packages"
    engine_prefixes = (
        "yt_dlp", "yt_dlp_ejs", "curl_cffi", "certifi", "cffi",
        "pycparser", "rich", "pygments", "markdown_it", "mdurl",
        "_cffi_backend",
    )
    if site_packages.is_dir():
        for child in site_packages.iterdir():
            if not child.name.startswith(engine_prefixes):
                continue
            if child.is_file():
                included.append(child)
                continue
            for candidate in child.rglob("*"):
                if candidate.is_file() and "__pycache__" not in candidate.parts and candidate.suffix.lower() not in {".pyc", ".pyo"}:
                    included.append(candidate)

    if not included:
        raise RuntimeError("Paketlenecek uygulama dosyası bulunamadı.")

    generated_version = f'APP_VERSION = "{normalized_version}"\n'.encode("utf-8")
    generated_config = json.dumps(
        {"owner": owner.strip(), "repo": repo.strip(), "channel": "stable"},
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    manifest = json.dumps(
        {
            "app": APP_SLUG,
            "version": normalized_version,
            "package_type": "incremental",
            "file_count": len(included),
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    root_name = APP_SLUG
    temp_zip = output_zip.with_name(f".{output_zip.name}.{next(tempfile._get_candidate_names())}.tmp")
    try:
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for candidate in sorted(set(included)):
                rel = candidate.relative_to(source_dir)
                rel_posix = rel.as_posix()
                if rel_posix in {"app/version.py", "update_config.json"}:
                    continue
                archive.write(candidate, Path(root_name) / rel)
            archive.writestr(str(Path(root_name) / "app" / "version.py"), generated_version)
            archive.writestr(str(Path(root_name) / "update_config.json"), generated_config)
            archive.writestr(str(Path(root_name) / "update_manifest.json"), manifest)

        if not zipfile.is_zipfile(temp_zip):
            raise RuntimeError("Oluşturulan güncelleme ZIP dosyası doğrulanamadı.")
        temp_zip.replace(output_zip)
    finally:
        temp_zip.unlink(missing_ok=True)

    checksum_path = write_sha256_file(output_zip)
    return output_zip, checksum_path


class RepositoryTestWorker(QObject):
    success = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(self, owner: str, repo: str, token: str) -> None:
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.token = token

    @Slot()
    def run(self) -> None:
        try:
            self.success.emit(repository_info(self.owner, self.repo, self.token))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class UpdateCheckWorker(QObject):
    success = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(self, owner: str, repo: str, token: str = "") -> None:
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.token = token

    @Slot()
    def run(self) -> None:
        try:
            # Public repositories do not need a token. Trying without the saved
            # admin token first also avoids expired/revoked token failures.
            try:
                release = latest_release(self.owner, self.repo, "")
            except Exception as public_error:
                if not self.token.strip():
                    raise
                try:
                    release = latest_release(self.owner, self.repo, self.token)
                except Exception:
                    raise public_error

            zip_asset, sha_asset = select_update_assets(release)
            remote_version = str(release.get("tag_name") or release.get("name") or "0").lstrip("v")
            payload = {
                "version": remote_version,
                "name": str(release.get("name") or "Yeni sürüm"),
                "body": str(release.get("body") or ""),
                "url": str((zip_asset or {}).get("browser_download_url") or ""),
                "asset_name": str((zip_asset or {}).get("name") or ""),
                "sha_url": str((sha_asset or {}).get("browser_download_url") or ""),
                "html_url": str(release.get("html_url") or ""),
                "newer": is_newer(remote_version),
            }
            if payload["newer"] and not payload["url"]:
                raise RuntimeError("Yeni sürüm bulundu ancak Release içinde indirilebilir ZIP dosyası yok.")
            self.success.emit(payload)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class UpdateDownloadWorker(QObject):
    progress = Signal(int, str)
    success = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, url: str, target: Path, sha_url: str = "", token: str = "") -> None:
        super().__init__()
        self.url = url
        self.target = target
        self.sha_url = sha_url
        self.token = token

    def _download_text(self, url: str) -> str:
        with _urlopen(_request(url, token=self.token, accept="application/octet-stream"), timeout=60) as response:
            return response.read().decode("utf-8", errors="replace")

    @Slot()
    def run(self) -> None:
        try:
            if not self.url:
                raise RuntimeError("Sürümde indirilebilir ZIP paketi yok.")
            self.target.parent.mkdir(parents=True, exist_ok=True)
            request = _request(self.url, token=self.token, accept="application/octet-stream")
            with _urlopen(request, timeout=60) as response, self.target.open("wb") as out:
                total = int(response.headers.get("Content-Length", "0") or 0)
                received = 0
                while True:
                    chunk = response.read(1024 * 512)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    percent = int(received / total * 90) if total else 45
                    self.progress.emit(min(percent, 90), "Güncelleme indiriliyor")

            if not zipfile.is_zipfile(self.target):
                raise RuntimeError("İndirilen güncelleme geçerli bir ZIP paketi değil.")

            if self.sha_url:
                self.progress.emit(94, "Dosya bütünlüğü doğrulanıyor")
                text = self._download_text(self.sha_url)
                expected = re.search(r"\b[a-fA-F0-9]{64}\b", text)
                if not expected:
                    raise RuntimeError("SHA-256 doğrulama dosyası okunamadı.")
                actual = sha256_file(self.target)
                if actual.lower() != expected.group(0).lower():
                    raise RuntimeError("Güncelleme dosyasının SHA-256 doğrulaması başarısız.")

            self.progress.emit(100, "Güncelleme hazır")
            self.success.emit(str(self.target))
        except Exception as exc:
            try:
                self.target.unlink(missing_ok=True)
            except Exception:
                pass
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class PackageBuildWorker(QObject):
    progress = Signal(int, str)
    success = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(self, source_dir: str, output_zip: str, version: str, owner: str, repo: str) -> None:
        super().__init__()
        self.source_dir = Path(source_dir)
        self.output_zip = Path(output_zip)
        self.version = version
        self.owner = owner
        self.repo = repo

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit(10, "Dosyalar hazırlanıyor")
            zip_path, checksum_path = build_update_package(
                self.source_dir,
                self.output_zip,
                version=self.version,
                owner=self.owner,
                repo=self.repo,
            )
            self.progress.emit(100, "Paket hazır")
            self.success.emit({"zip": str(zip_path), "sha256": str(checksum_path)})
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class PublishReleaseWorker(QObject):
    progress = Signal(int, str)
    success = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        owner: str,
        repo: str,
        token: str,
        version: str,
        title: str,
        body: str,
        asset_path: str,
        checksum_path: str,
        draft: bool,
        prerelease: bool,
    ) -> None:
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.token = token
        self.version = version
        self.title = title
        self.body = body
        self.asset_path = Path(asset_path)
        self.checksum_path = Path(checksum_path)
        self.draft = draft
        self.prerelease = prerelease

    @Slot()
    def run(self) -> None:
        try:
            if not self.token.strip():
                raise ValueError("GitHub erişim anahtarı boş.")
            repository_info(self.owner, self.repo, self.token)
            self.progress.emit(15, "Taslak sürüm oluşturuluyor")
            release = _create_release(
                self.owner,
                self.repo,
                self.token,
                self.version,
                self.title,
                self.body,
                self.prerelease,
            )
            self.progress.emit(48, "ZIP paketi yükleniyor")
            zip_asset = upload_release_asset(release, self.token, self.asset_path)
            self.progress.emit(72, "SHA-256 dosyası yükleniyor")
            sha_asset = upload_release_asset(release, self.token, self.checksum_path)
            self.progress.emit(88, "Sürüm sonlandırılıyor")
            final_release = _update_release(
                release,
                self.token,
                title=self.title.strip() or f"{APP_FULL_NAME} v{self.version.strip().lstrip('v')}",
                body=self.body,
                draft=self.draft,
                prerelease=self.prerelease,
            )
            self.progress.emit(100, "Güncelleme yayınlandı" if not self.draft else "Taslak kaydedildi")
            self.success.emit({"release": final_release, "zip_asset": zip_asset, "sha_asset": sha_asset})
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()
