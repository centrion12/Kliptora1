from __future__ import annotations

import logging
import shutil
import tempfile
import urllib.request
from urllib.parse import parse_qs, urlparse
import zipfile
from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from .core import (
    APP_USER_AGENT,
    FFMPEG_URL,
    DownloadJob,
    activate_tool_paths,
    build_ydl_options,
    classify_url,
    deno_bin_dir,
    deno_download_url,
    ffmpeg_bin_dir,
    find_ffmpeg,
    friendly_error,
    download_temp_dir,
    job_requires_ffmpeg,
    is_cookie_load_error,
    normalize_url,
    strip_cookie_options,
)


class CancelledByUser(Exception):
    pass


class QtYDLLogger:
    def __init__(self, signal: Signal) -> None:
        self.signal = signal

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug]"):
            return
        self.signal.emit(msg)

    def info(self, msg: str) -> None:
        self.signal.emit(msg)

    def warning(self, msg: str) -> None:
        self.signal.emit(f"Uyarı: {msg}")

    def error(self, msg: str) -> None:
        self.signal.emit(f"Hata: {msg}")


class AnalyzeWorker(QObject):
    success = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        url: str,
        cookie_browser: str = "Yok",
        proxy: str = "",
        *,
        cookie_profile: str = "",
        cookie_file: str = "",
        referer: str = "",
        user_agent: str = "",
        source_mode: str = "Otomatik",
    ) -> None:
        super().__init__()
        self.url = url
        self.cookie_browser = cookie_browser
        self.proxy = proxy
        self.cookie_profile = cookie_profile
        self.cookie_file = cookie_file
        self.referer = referer
        self.user_agent = user_agent
        self.source_mode = source_mode

    def _base_options(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "ignoreconfig": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": False,
            "extract_flat": False,
            "ignoreerrors": False,
            "socket_timeout": 25,
            "playlistend": 100,
        }
        if self.source_mode == "Doğrudan medya / HLS / DASH":
            opts["force_generic_extractor"] = True
        if self.proxy.strip():
            opts["proxy"] = self.proxy.strip()
        cookie_path = Path(self.cookie_file).expanduser() if self.cookie_file.strip() else None
        if cookie_path and cookie_path.is_file():
            opts["cookiefile"] = str(cookie_path)
        else:
            browser = self.cookie_browser.strip().lower()
            if browser and browser != "yok":
                profile = self.cookie_profile.strip()
                opts["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)
        headers: dict[str, str] = {}
        if self.user_agent.strip():
            headers["User-Agent"] = self.user_agent.strip()
        if self.referer.strip():
            headers["Referer"] = self.referer.strip()
        if headers:
            opts["http_headers"] = headers
        return opts

    @staticmethod
    def _looks_like_playlist(url: str) -> bool:
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            path = parsed.path.lower()
            host = parsed.netloc.lower()
            if "youtube.com" in host or "youtu.be" in host:
                return bool(query.get("list")) or "/playlist" in path
            return any(token in path for token in ("/playlist", "/playlists/", "/sets/", "/album/"))
        except Exception:
            return False

    @staticmethod
    def _entry_is_usable(entry: dict[str, Any]) -> bool:
        title = str(entry.get("title") or "").strip().lower()
        availability = str(entry.get("availability") or "").strip().lower()
        if not entry.get("id") and not entry.get("url") and not entry.get("webpage_url"):
            return False
        if title in {"[private video]", "[deleted video]", "private video", "deleted video"}:
            return False
        if availability in {"private", "premium_only", "subscriber_only", "needs_auth"}:
            return False
        return True

    @staticmethod
    def _entry_url(entry: dict[str, Any], root_info: dict[str, Any]) -> str:
        for key in ("webpage_url", "original_url", "url"):
            value = str(entry.get(key) or "").strip()
            if value.startswith(("http://", "https://")):
                return value
        entry_id = str(entry.get("id") or "").strip()
        extractor = str(entry.get("extractor_key") or entry.get("extractor") or root_info.get("extractor_key") or "").lower()
        if entry_id and "youtube" in extractor:
            return f"https://www.youtube.com/watch?v={entry_id}"
        return ""

    def _extract(self, yt_dlp: Any, url: str, opts: dict[str, Any]) -> dict[str, Any]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise RuntimeError("Video bilgisi alınamadı.")
        return info

    @Slot()
    def run(self) -> None:
        try:
            activate_tool_paths()
            import yt_dlp

            url = normalize_url(self.url)
            opts = self._base_options()
            playlist_hint = self._looks_like_playlist(url)
            if playlist_hint:
                # Analyze the playlist itself without resolving every item. This prevents
                # one deleted, region-blocked or rights-blocked video from aborting the
                # entire playlist analysis.
                opts["extract_flat"] = "in_playlist"
                opts["ignoreerrors"] = True

            try:
                root_info = self._extract(yt_dlp, url, opts)
            except Exception as first_exc:
                first_message = str(first_exc)
                lowered = first_message.lower()
                retry_opts = dict(opts)
                retried = False

                # Invalid/locked browser cookies or a broken cookies.txt must not
                # block public media. Retry once with every cookie source removed.
                if is_cookie_load_error(first_message) and (
                    "cookiesfrombrowser" in retry_opts or "cookiefile" in retry_opts
                ):
                    retry_opts = strip_cookie_options(retry_opts)
                    retried = True

                # Instagram sometimes returns an empty media response only for one
                # authentication path. Try the public route as a safe fallback.
                if "instagram.com" in url.lower() and "instagram sent an empty media response" in lowered:
                    if "cookiesfrombrowser" in retry_opts:
                        retry_opts.pop("cookiesfrombrowser", None)
                        retried = True

                if retried:
                    try:
                        root_info = self._extract(yt_dlp, url, retry_opts)
                    except Exception as retry_exc:
                        raise RuntimeError(str(retry_exc)) from retry_exc
                else:
                    raise

            playlist_count = 0
            playlist_skipped = 0
            info = root_info
            entries = root_info.get("entries") if isinstance(root_info, dict) else None
            if entries is not None:
                materialized = [entry for entry in entries if isinstance(entry, dict)]
                reported_count = root_info.get("playlist_count") or root_info.get("n_entries")
                playlist_count = int(reported_count or len(materialized))
                usable = [entry for entry in materialized if self._entry_is_usable(entry)]
                playlist_skipped = max(0, len(materialized) - len(usable))
                info = usable[0] if usable else (materialized[0] if materialized else root_info)

                # Resolve a few usable entries only for preview/format information.
                # Failures are intentionally swallowed so the playlist remains usable.
                detail_opts = self._base_options()
                detail_opts.update({"noplaylist": True, "extract_flat": False, "ignoreerrors": False})
                for candidate in usable[:8]:
                    candidate_url = self._entry_url(candidate, root_info)
                    if not candidate_url:
                        continue
                    try:
                        resolved = self._extract(yt_dlp, candidate_url, detail_opts)
                        if resolved:
                            info = resolved
                            break
                    except Exception:
                        playlist_skipped += 1
                        continue

            formats = [fmt for fmt in (info.get("formats") or []) if isinstance(fmt, dict)]
            heights = sorted({int(fmt["height"]) for fmt in formats if isinstance(fmt.get("height"), (int, float))})
            protocols = sorted({str(fmt.get("protocol") or "") for fmt in formats if fmt.get("protocol")})
            subtitle_languages = sorted(set((info.get("subtitles") or {}).keys()) | set((info.get("automatic_captions") or {}).keys()))

            thumbnail_url = info.get("thumbnail") or ""
            thumbnail_bytes = b""
            if thumbnail_url:
                try:
                    request = urllib.request.Request(
                        thumbnail_url,
                        headers={"User-Agent": self.user_agent.strip() or "Mozilla/5.0"},
                    )
                    with urllib.request.urlopen(request, timeout=10) as response:
                        thumbnail_bytes = response.read(5 * 1024 * 1024)
                except Exception:
                    thumbnail_bytes = b""

            classified = classify_url(url)
            extractor = str(info.get("extractor_key") or info.get("extractor") or "Generic")
            payload = {
                "title": (root_info.get("title") if playlist_count else info.get("title")) or info.get("title") or "Başlık bulunamadı",
                "uploader": root_info.get("uploader") or root_info.get("channel") or info.get("uploader") or info.get("channel") or "—",
                "duration": info.get("duration"),
                "thumbnail": thumbnail_url,
                "thumbnail_bytes": thumbnail_bytes,
                "webpage_url": info.get("webpage_url") or url,
                "view_count": info.get("view_count"),
                "is_live": bool(info.get("is_live") or info.get("live_status") == "is_live"),
                "live_status": info.get("live_status") or "",
                "extractor": extractor,
                "site": classified["site"],
                "source_kind": classified["kind"],
                "protocols": protocols,
                "format_count": len(formats),
                "heights": heights,
                "playlist_count": playlist_count,
                "playlist_skipped": playlist_skipped,
                "subtitle_languages": subtitle_languages,
                "ext": info.get("ext") or "",
            }
            self.success.emit(payload)
        except Exception as exc:
            self.error.emit(friendly_error(str(exc)))
        finally:
            self.finished.emit()


class DownloadWorker(QObject):
    progress = Signal(str, dict)
    status = Signal(str, str)
    log = Signal(str)
    job_finished = Signal(str, bool, str)
    all_finished = Signal()

    def __init__(self, jobs: list[DownloadJob]) -> None:
        super().__init__()
        self.jobs = jobs
        self._cancel = Event()
        self._current_job_id = ""

    @Slot()
    def cancel(self) -> None:
        self._cancel.set()

    def _progress_hook(self, data: dict[str, Any]) -> None:
        if self._cancel.is_set():
            raise CancelledByUser("Kullanıcı indirmeyi durdurdu.")

        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100.0) if total else 0.0
            info = data.get("info_dict") or {}
            self.progress.emit(
                self._current_job_id,
                {
                    "percent": max(0.0, min(100.0, percent)),
                    "speed": data.get("speed"),
                    "eta": data.get("eta"),
                    "downloaded": downloaded,
                    "total": total,
                    "title": info.get("title") or "",
                    "playlist_index": info.get("playlist_index"),
                    "playlist_count": info.get("playlist_count"),
                },
            )
        elif status == "finished":
            self.status.emit(self._current_job_id, "Dönüştürülüyor / birleştiriliyor")
            self.progress.emit(self._current_job_id, {"percent": 100.0, "speed": None, "eta": 0})

    def _post_hook(self, data: dict[str, Any]) -> None:
        if self._cancel.is_set():
            raise CancelledByUser("Kullanıcı indirmeyi durdurdu.")
        pp_status = data.get("status")
        pp_name = data.get("postprocessor") or "Medya"
        if pp_status == "started":
            self.status.emit(self._current_job_id, f"İşleniyor: {pp_name}")

    def _download_with_options(self, yt_dlp: Any, job: DownloadJob, opts: dict[str, Any]) -> int:
        opts["progress_hooks"] = [self._progress_hook]
        opts["postprocessor_hooks"] = [self._post_hook]
        opts["logger"] = QtYDLLogger(self.log)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return int(ydl.download([normalize_url(job.url)]) or 0)

    def _cleanup_temp_after_success(self, job: DownloadJob) -> None:
        try:
            temp_dir = download_temp_dir(job)
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _should_generic_retry(self, message: str, job: DownloadJob) -> bool:
        if job.source_mode != "Otomatik":
            return False
        lowered = message.lower()
        return any(
            token in lowered
            for token in (
                "unsupported url",
                "unable to extract",
                "no video formats found",
                "requested format is not available",
                "instagram sent an empty media response",
            )
        )

    @Slot()
    def run(self) -> None:
        try:
            activate_tool_paths()
            import yt_dlp

            ffmpeg_location = find_ffmpeg()
            for job in self.jobs:
                if self._cancel.is_set():
                    self.job_finished.emit(job.job_id, False, "Durduruldu")
                    continue

                self._current_job_id = job.job_id
                if job_requires_ffmpeg(job) and not ffmpeg_location:
                    message = (
                        "FFmpeg bulunamadı. Ham WEBM/M4A ve kapak dosyaları bırakmamak için indirme başlatılmadı. "
                        "Ayarlar → Gerekli araçlar → FFmpeg'i yeniden kur bölümünden FFmpeg'i kurup tekrar dene."
                    )
                    self.status.emit(job.job_id, "FFmpeg gerekli")
                    self.job_finished.emit(job.job_id, False, message)
                    continue
                self.status.emit(job.job_id, "Kaynak tanınıyor")
                try:
                    opts = build_ydl_options(job, ffmpeg_location)
                    code = self._download_with_options(yt_dlp, job, opts)
                    if code == 0:
                        self._cleanup_temp_after_success(job)
                        self.job_finished.emit(job.job_id, True, "Tamamlandı")
                    else:
                        self.job_finished.emit(job.job_id, False, f"yt-dlp çıkış kodu: {code}")
                except CancelledByUser:
                    self.job_finished.emit(job.job_id, False, "Durduruldu")
                except Exception as first_exc:
                    first_message = str(first_exc)
                    lowered = first_message.lower()

                    # Browser cookie import on Chromium can fail because of DPAPI
                    # or a locked cookie database. Retry once without importing
                    # browser cookies so public media can still download.
                    if not self._cancel.is_set() and is_cookie_load_error(first_message):
                        try:
                            self.status.emit(job.job_id, "Çerezler yüklenemedi; çerezsiz yeniden deneniyor")
                            retry_opts = strip_cookie_options(build_ydl_options(job, ffmpeg_location))
                            code = self._download_with_options(yt_dlp, job, retry_opts)
                            if code == 0:
                                self._cleanup_temp_after_success(job)
                                self.job_finished.emit(job.job_id, True, "Tamamlandı (çerezsiz yedek)")
                                continue
                            raise RuntimeError(f"Çerezsiz yedek çıkış kodu: {code}")
                        except CancelledByUser:
                            self.job_finished.emit(job.job_id, False, "Durduruldu")
                            continue
                        except Exception as retry_exc:
                            first_message = f"{first_message}\n\nÇerezsiz yedek: {retry_exc}"

                    if self._should_generic_retry(first_message, job) and not self._cancel.is_set():
                        try:
                            self.status.emit(job.job_id, "Genel medya çözücüsü deneniyor")
                            self.log.emit("İlk yöntem başarısız oldu; genel medya çözücüsüne geçiliyor.")
                            retry_opts = build_ydl_options(job, ffmpeg_location)
                            retry_opts["force_generic_extractor"] = True
                            retry_opts["format"] = "bestvideo*+bestaudio/best" if job.media_type == "video" else "bestaudio/best"
                            code = self._download_with_options(yt_dlp, job, retry_opts)
                            if code == 0:
                                self._cleanup_temp_after_success(job)
                                self.job_finished.emit(job.job_id, True, "Tamamlandı (genel çözücü)")
                                continue
                            raise RuntimeError(f"Genel çözücü çıkış kodu: {code}")
                        except CancelledByUser:
                            self.job_finished.emit(job.job_id, False, "Durduruldu")
                            continue
                        except Exception as retry_exc:
                            first_message = f"{first_message}\n\nGenel çözücü: {retry_exc}"
                    logging.exception("İndirme hatası")
                    self.job_finished.emit(job.job_id, False, friendly_error(first_message))
        finally:
            self.all_finished.emit()


class FfmpegInstallWorker(QObject):
    progress = Signal(int, str)
    success = Signal(str)
    error = Signal(str)
    finished = Signal()

    @Slot()
    def run(self) -> None:
        try:
            target = ffmpeg_bin_dir()
            with tempfile.TemporaryDirectory(prefix="kliptora_ffmpeg_") as tmp:
                zip_path = Path(tmp) / "ffmpeg.zip"
                request = urllib.request.Request(FFMPEG_URL, headers={"User-Agent": APP_USER_AGENT})
                with urllib.request.urlopen(request, timeout=60) as response, zip_path.open("wb") as out:
                    total = int(response.headers.get("Content-Length", "0") or 0)
                    received = 0
                    while True:
                        chunk = response.read(1024 * 512)
                        if not chunk:
                            break
                        out.write(chunk)
                        received += len(chunk)
                        percent = int(received / total * 75) if total else 35
                        self.progress.emit(min(percent, 75), "FFmpeg indiriliyor")

                self.progress.emit(80, "Arşiv açılıyor")
                with zipfile.ZipFile(zip_path) as archive:
                    members = archive.namelist()
                    wanted = {}
                    for filename in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
                        match = next((m for m in members if m.lower().endswith(f"/bin/{filename}")), None)
                        if match:
                            wanted[filename] = match
                    if "ffmpeg.exe" not in wanted:
                        raise RuntimeError("Arşivde ffmpeg.exe bulunamadı.")
                    for filename, member in wanted.items():
                        with archive.open(member) as src, (target / filename).open("wb") as dst:
                            shutil.copyfileobj(src, dst)

                self.progress.emit(100, "FFmpeg hazır")
                self.success.emit(str(target))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class DenoInstallWorker(QObject):
    progress = Signal(int, str)
    success = Signal(str)
    error = Signal(str)
    finished = Signal()

    @Slot()
    def run(self) -> None:
        try:
            target = deno_bin_dir()
            with tempfile.TemporaryDirectory(prefix="kliptora_deno_") as tmp:
                zip_path = Path(tmp) / "deno.zip"
                request = urllib.request.Request(
                    deno_download_url(),
                    headers={"User-Agent": APP_USER_AGENT},
                )
                with urllib.request.urlopen(request, timeout=60) as response, zip_path.open("wb") as out:
                    total = int(response.headers.get("Content-Length", "0") or 0)
                    received = 0
                    while True:
                        chunk = response.read(1024 * 512)
                        if not chunk:
                            break
                        out.write(chunk)
                        received += len(chunk)
                        percent = int(received / total * 85) if total else 45
                        self.progress.emit(min(percent, 85), "Deno indiriliyor")

                self.progress.emit(90, "Deno kuruluyor")
                with zipfile.ZipFile(zip_path) as archive:
                    member = next((m for m in archive.namelist() if m.lower().endswith("deno.exe")), None)
                    if not member:
                        raise RuntimeError("Arşivde deno.exe bulunamadı.")
                    with archive.open(member) as src, (target / "deno.exe").open("wb") as dst:
                        shutil.copyfileobj(src, dst)

                activate_tool_paths()
                self.progress.emit(100, "Deno hazır")
                self.success.emit(str(target))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

class EngineUpdateWorker(QObject):
    progress = Signal(int, str)
    success = Signal(str)
    error = Signal(str)
    finished = Signal()

    @Slot()
    def run(self) -> None:
        import os
        import subprocess
        import sys

        try:
            self.progress.emit(15, "Paket yöneticisi hazırlanıyor")
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = 0x08000000
            command = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--upgrade",
                "--pre",
                "yt-dlp[default,curl-cffi]",
                "yt-dlp-ejs",
            ]
            self.progress.emit(35, "İndirme motorunun nightly sürümü kuruluyor")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                startupinfo=startupinfo,
                timeout=600,
            )
            if result.returncode != 0:
                tail = "\n".join(result.stdout.splitlines()[-18:])
                raise RuntimeError(tail or f"pip çıkış kodu: {result.returncode}")
            self.progress.emit(100, "Nightly indirme motoru hazır")
            self.success.emit("yt-dlp nightly, curl-cffi ve yt-dlp-ejs güncellendi. Instagram düzeltmesi etkin.")
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()
