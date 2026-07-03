from __future__ import annotations

import os
import hashlib
import platform
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

APP_NAME = "Kliptora"
APP_FULL_NAME = "Kliptora Video Downloader"
APP_SLUG = "Kliptora"
APP_ORGANIZATION = "KliptoraTools"
APP_USER_AGENT = "Kliptora/2.3.3"

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
DENO_URL_X64 = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"
DENO_URL_ARM64 = "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-pc-windows-msvc.zip"

VIDEO_QUALITIES: dict[str, int | None] = {
    "En iyi kalite": None,
    "2160p (4K)": 2160,
    "1440p (2K)": 1440,
    "1080p (Full HD)": 1080,
    "720p (HD)": 720,
    "480p": 480,
    "360p": 360,
}

VIDEO_CONTAINERS = ["MP4", "MKV", "WEBM"]
AUDIO_FORMATS = ["MP3", "M4A", "FLAC", "WAV", "OPUS"]
AUDIO_BITRATES = ["320", "256", "192", "128"]
BROWSERS = ["Yok", "Chrome", "Edge", "Firefox", "Brave", "Opera", "Vivaldi"]
SOURCE_MODES = ["Otomatik", "Web sayfası", "Doğrudan medya / HLS / DASH"]

_DIRECT_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts", ".m4v"}
_DIRECT_AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"}
_SITE_LABELS = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "twitter.com": "X / Twitter",
    "x.com": "X / Twitter",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "twitch.tv": "Twitch",
    "reddit.com": "Reddit",
    "vimeo.com": "Vimeo",
    "dailymotion.com": "Dailymotion",
    "soundcloud.com": "SoundCloud",
    "pinterest.com": "Pinterest",
    "kick.com": "Kick",
}


@dataclass(slots=True)
class DownloadJob:
    job_id: str
    url: str
    output_dir: str
    media_type: str = "video"
    quality: str = "En iyi kalite"
    container: str = "MP4"
    audio_format: str = "MP3"
    audio_bitrate: str = "320"
    playlist: bool = False
    playlist_subfolder: bool = True
    subtitles: bool = False
    auto_subtitles: bool = False
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    write_description: bool = False
    live_from_start: bool = False
    source_mode: str = "Otomatik"
    format_fallback: bool = True
    cookie_browser: str = "Yok"
    cookie_profile: str = ""
    cookie_file: str = ""
    proxy: str = ""
    referer: str = ""
    user_agent: str = ""
    concurrent_fragments: int = 4
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_SLUG
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def plugin_dir() -> Path:
    path = app_data_dir() / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_resource(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative


def installation_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def update_config_path() -> Path:
    return installation_dir() / "update_config.json"


def ffmpeg_bin_dir() -> Path:
    path = app_data_dir() / "tools" / "ffmpeg" / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_ffmpeg() -> str | None:
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    local = ffmpeg_bin_dir() / exe
    if local.exists():
        return str(local.parent)
    system = shutil.which("ffmpeg")
    if system:
        return str(Path(system).parent)
    return None


def deno_bin_dir() -> Path:
    path = app_data_dir() / "tools" / "deno" / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def deno_download_url() -> str:
    machine = platform.machine().lower()
    return DENO_URL_ARM64 if machine in {"arm64", "aarch64"} else DENO_URL_X64


def find_deno() -> str | None:
    exe = "deno.exe" if sys.platform == "win32" else "deno"
    local = deno_bin_dir() / exe
    if local.exists():
        return str(local.parent)
    system = shutil.which("deno")
    if system:
        return str(Path(system).parent)
    return None


def activate_tool_paths() -> None:
    paths: list[str] = []
    for finder in (find_deno, find_ffmpeg):
        found = finder()
        if found:
            paths.append(found)
    current = os.environ.get("PATH", "")
    existing = current.split(os.pathsep) if current else []
    merged: list[str] = []
    seen: set[str] = set()
    for value in paths + existing:
        key = os.path.normcase(os.path.abspath(value)) if value else ""
        if value and key not in seen:
            seen.add(key)
            merged.append(value)
    os.environ["PATH"] = os.pathsep.join(merged)

    # yt-dlp discovers extractor/postprocessor plugins from Python paths that
    # contain a ``yt_dlp_plugins`` package. The user-managed folder is kept
    # outside the installation directory so application updates do not erase it.
    plugins = str(plugin_dir())
    if plugins not in sys.path:
        sys.path.insert(0, plugins)


def normalize_url(url: str) -> str:
    value = url.strip()
    try:
        parsed = urlparse(value)
        host = parsed.netloc.lower().split(":", 1)[0].removeprefix("www.")
        path = parsed.path
        if host == "instagram.com" or host.endswith(".instagram.com"):
            if path.startswith("/reels/"):
                path = "/reel/" + path[len("/reels/"):]
            return urlunparse((parsed.scheme or "https", parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
    except Exception:
        pass
    return value


def split_urls(raw: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in raw.replace("\r", "\n").split("\n"):
        value = normalize_url(line.strip().strip('"\''))
        if not value or value in seen:
            continue
        if value.startswith(("http://", "https://")):
            urls.append(value)
            seen.add(value)
    return urls


def classify_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().split(":", 1)[0]
    host = host.removeprefix("www.")
    path = parsed.path.lower()
    suffix = Path(path).suffix.lower()
    site = next((label for domain, label in _SITE_LABELS.items() if host == domain or host.endswith("." + domain)), host or "Bilinmeyen site")

    if path.endswith(".m3u8") or ".m3u8" in path:
        kind, protocol = "HLS yayını", "m3u8"
    elif path.endswith(".mpd") or ".mpd" in path:
        kind, protocol = "DASH yayını", "mpd"
    elif suffix in _DIRECT_VIDEO_EXTS:
        kind, protocol = "Doğrudan video", suffix.lstrip(".")
    elif suffix in _DIRECT_AUDIO_EXTS:
        kind, protocol = "Doğrudan ses", suffix.lstrip(".")
    else:
        kind, protocol = "Web sayfası", "auto"

    return {"host": host, "site": site, "kind": kind, "protocol": protocol, "direct": kind != "Web sayfası"}


def _height_filter(height: int | None) -> str:
    return "" if height is None else f"[height<={height}]"


def _browser_cookie_tuple(browser: str, profile: str) -> tuple[str, ...] | None:
    browser_name = browser.strip().lower()
    if not browser_name or browser_name == "yok":
        return None
    profile_name = profile.strip()
    return (browser_name, profile_name) if profile_name else (browser_name,)


_COOKIE_LOAD_ERROR_TOKENS = (
    "failed to load cookies",
    "failed to load cookie",
    "unable to load cookies",
    "could not load cookies",
    "failed to decrypt with dpapi",
    "could not copy chrome cookie database",
    "cookie database is locked",
    "cookie file does not exist",
    "invalid netscape format cookies file",
)


def is_cookie_load_error(message: str) -> bool:
    lowered = (message or "").lower()
    return any(token in lowered for token in _COOKIE_LOAD_ERROR_TOKENS)


def strip_cookie_options(options: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(options)
    cleaned.pop("cookiesfrombrowser", None)
    cleaned.pop("cookiefile", None)
    return cleaned


def download_temp_dir(job: DownloadJob) -> Path:
    key = hashlib.sha256(normalize_url(job.url).encode("utf-8", errors="ignore")).hexdigest()[:16]
    path = app_data_dir() / "temp" / key
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_ydl_options(job: DownloadJob, ffmpeg_location: str | None = None) -> dict[str, Any]:
    output = Path(job.output_dir).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    temp_output = download_temp_dir(job)

    if job.playlist and job.playlist_subfolder:
        template = "%(playlist_title|Playlist)s/%(playlist_index)03d - %(title).180B [%(id)s].%(ext)s"
    else:
        template = "%(title).180B [%(id)s].%(ext)s"

    fragments = max(1, min(16, int(job.concurrent_fragments or 4)))
    options: dict[str, Any] = {
        "paths": {"home": str(output), "temp": str(temp_output)},
        "outtmpl": {"default": template},
        "noplaylist": not job.playlist,
        "ignoreerrors": job.playlist,
        "continuedl": True,
        "nopart": False,
        "retries": 12,
        "fragment_retries": 12,
        "extractor_retries": 4,
        "file_access_retries": 4,
        "concurrent_fragment_downloads": fragments,
        "socket_timeout": 30,
        "windowsfilenames": sys.platform == "win32",
        "restrictfilenames": False,
        "trim_file_name": 190,
        "overwrites": False,
        "writethumbnail": bool(job.embed_thumbnail and ffmpeg_location),
        "writedescription": bool(job.write_description),
        "writeinfojson": False,
        "quiet": True,
        "ignoreconfig": True,
        "no_warnings": False,
        "check_formats": True,
        "live_from_start": bool(job.live_from_start),
        "hls_use_mpegts": bool(job.live_from_start),
    }

    if job.source_mode == "Doğrudan medya / HLS / DASH":
        options["force_generic_extractor"] = True

    if ffmpeg_location:
        options["ffmpeg_location"] = ffmpeg_location

    proxy = job.proxy.strip()
    if proxy:
        options["proxy"] = proxy

    cookie_file = Path(job.cookie_file).expanduser() if job.cookie_file.strip() else None
    if cookie_file and cookie_file.is_file():
        options["cookiefile"] = str(cookie_file)
    else:
        cookies = _browser_cookie_tuple(job.cookie_browser, job.cookie_profile)
        if cookies:
            options["cookiesfrombrowser"] = cookies

    headers: dict[str, str] = {}
    if job.user_agent.strip():
        headers["User-Agent"] = job.user_agent.strip()
    if job.referer.strip():
        headers["Referer"] = job.referer.strip()
    if headers:
        options["http_headers"] = headers

    postprocessors: list[dict[str, Any]] = []

    if job.media_type == "audio":
        codec = job.audio_format.lower()
        options["format"] = "bestaudio/best"
        pp: dict[str, Any] = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
        if codec in {"mp3", "m4a", "opus"}:
            pp["preferredquality"] = job.audio_bitrate
        postprocessors.append(pp)
        if job.embed_thumbnail and codec in {"mp3", "m4a", "flac", "opus"}:
            postprocessors.append({"key": "EmbedThumbnail"})
    else:
        height = VIDEO_QUALITIES.get(job.quality)
        hf = _height_filter(height)
        container = job.container.lower()
        generic_best = f"bv*{hf}+ba/b{hf}"

        if container == "mp4":
            preferred = (
                f"bv*{hf}[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/"
                f"b{hf}[ext=mp4]"
            )
            options["format"] = f"{preferred}/{generic_best}" if job.format_fallback else preferred
            options["merge_output_format"] = "mp4"
        elif container == "webm":
            preferred = f"bv*{hf}[ext=webm]+ba[ext=webm]/b{hf}[ext=webm]"
            options["format"] = f"{preferred}/{generic_best}" if job.format_fallback else preferred
            options["merge_output_format"] = "webm"
        else:
            options["format"] = generic_best
            options["merge_output_format"] = "mkv"

        if job.embed_thumbnail and container in {"mp4", "mkv"}:
            postprocessors.append({"key": "EmbedThumbnail"})

    if job.embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

    if job.subtitles or job.auto_subtitles:
        options.update(
            {
                "writesubtitles": job.subtitles,
                "writeautomaticsub": job.auto_subtitles,
                "subtitleslangs": ["tr.*", "en.*", "-live_chat"],
                "subtitlesformat": "best",
                "embedsubtitles": job.media_type == "video",
            }
        )
        if job.media_type == "video":
            postprocessors.append({"key": "FFmpegEmbedSubtitle"})

    if postprocessors:
        options["postprocessors"] = postprocessors

    return options


def job_requires_ffmpeg(job: DownloadJob) -> bool:
    # Audio extraction, stream merging, metadata, subtitles and thumbnail embedding
    # all rely on FFmpeg. Blocking early prevents raw .webm/.m4a/.webp files from
    # being scattered into the user's selected output folder.
    if job.media_type == "audio":
        return True
    if job.embed_thumbnail or job.embed_metadata or job.subtitles or job.auto_subtitles:
        return True
    return job.container.upper() in {"MP4", "MKV", "WEBM"}


def friendly_error(message: str) -> str:
    raw = (message or "Bilinmeyen hata").strip()
    lowered = raw.lower()
    hints: list[str] = []

    if "drm" in lowered or "encrypted" in lowered:
        hints.append("Bu içerik DRM ile korunuyor. Kliptora DRM korumasını aşmaz.")
    if is_cookie_load_error(raw):
        hints.append("Çerezler yüklenemedi. Kliptora bu tür hatalarda çerezsiz yeniden dener; özel içerikse Ayarlar'daki çerez seçimini düzelt.")
    if "instagram sent an empty media response" in lowered:
        hints.append("Instagram çözücüsü eski olabilir. Ayarlar > İndirme motorunu güncelle ile nightly sürümü kur; v2.2.2 bu düzeltmeyi ve curl-cffi desteğini paketle birlikte getirir.")
    if any(token in lowered for token in ("sign in", "login required", "authentication", "private video", "members-only")):
        hints.append("İçerik oturum istiyor. Tarayıcı çerezini veya dışa aktarılmış cookies.txt dosyasını kullan.")
    if any(token in lowered for token in ("not a bot", "confirm you’re not a bot", "confirm you're not a bot")):
        hints.append("Site doğrulama istiyor. Tarayıcı çerezlerini seçip Deno ve indirme motorunu güncelle.")
    if "requested format is not available" in lowered or "format is not available" in lowered:
        hints.append("Seçilen kalite/biçim bulunamadı. Kaliteyi 'En iyi kalite' yap veya otomatik biçim yedeğini aç.")
    if any(token in lowered for token in ("unsupported url", "no video formats found", "unable to extract")):
        hints.append("Bağlantıyı doğrudan medya/HLS/DASH modunda dene veya motoru güncelle.")
    if any(token in lowered for token in ("http error 403", "forbidden")):
        hints.append("Site erişimi reddetti. Tarayıcı çerezi, Referer veya farklı bir bağlantı gerekebilir.")
    if any(token in lowered for token in ("http error 429", "too many requests")):
        hints.append("Site çok fazla istek algıladı. Bir süre bekle ve tekrar dene.")
    if "ffmpeg" in lowered and any(token in lowered for token in ("not found", "not installed", "required")):
        hints.append("FFmpeg eksik. Ayarlar → Gerekli araçlar bölümünden FFmpeg'i kur.")
    if any(token in lowered for token in ("geo", "country", "region")) and "available" in lowered:
        hints.append("İçerik bulunduğun bölgede kullanılamıyor olabilir.")
    if any(token in lowered for token in ("timed out", "timeout", "connection reset", "network is unreachable")):
        hints.append("Ağ bağlantısı zaman aşımına uğradı. İnterneti/proxy ayarını kontrol edip tekrar dene.")

    if not hints:
        return raw
    return raw + "\n\nÖneri:\n• " + "\n• ".join(dict.fromkeys(hints))


def sanitize_diagnostic_text(text: str) -> str:
    value = text or ""
    value = re.sub(r"(?i)(authorization:\s*(?:bearer|token)\s+)[^\s]+", r"\1***", value)
    value = re.sub(r"(?i)(github_pat_|ghp_)[A-Za-z0-9_]+", "***TOKEN***", value)
    value = re.sub(r"(?i)([?&](?:token|key|auth|signature|sig)=)[^&\s]+", r"\1***", value)
    value = re.sub(r"(?i)(cookie:\s*)[^\r\n]+", r"\1***", value)
    return value


def human_bytes(value: float | int | None) -> str:
    if not value:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def human_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    value = max(0, int(seconds))
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
