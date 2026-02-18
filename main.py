import json
import os
import queue
import re
import shutil
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from dropbox import Dropbox
from dropbox.files import CommitInfo, UploadSessionCursor, WriteMode
from dropbox.exceptions import ApiError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _to_bool(raw: str, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def log_exception(context: str, exc: Exception) -> None:
    log(f"{context}: {exc}", level="ERROR")
    log(traceback.format_exc().rstrip(), level="ERROR")


@dataclass
class Settings:
    # Trigger mode
    trigger_mode: str  # webhook | poll
    webhook_host: str
    webhook_port: int
    webhook_path: str
    webhook_token: str

    # VOD detection/fallback
    watch_dir: Path
    vod_extensions: Tuple[str, ...]
    poll_interval_sec: int
    stable_for_sec: int
    min_vod_size_mb: int
    processed_state_file: Path
    source_path_rewrite_from: str
    source_path_rewrite_to: str

    # Public upload mode (for Opus videoUrl)
    publish_mode: str  # local_http | dropbox
    public_output_dir: Path
    public_base_url: str
    # Dropbox (when publish_mode=dropbox)
    dropbox_access_token: str
    dropbox_folder: str

    # Opus
    opus_api_base: str
    opus_bearer_token: str
    opus_org_id: Optional[str]
    opus_user_id: Optional[str]
    opus_lang: str
    opus_clip_min_sec: int
    opus_clip_max_sec: int
    opus_layout_aspect_ratio: str
    opus_custom_prompt: str
    opus_brand_template_id: Optional[str]
    opus_source_lang: str
    opus_wait_timeout_sec: int
    opus_poll_interval_sec: int

    # YouTube
    yt_client_secret_file: Path
    yt_token_file: Path
    yt_privacy_status: str
    yt_category_id: str
    yt_title_prefix: str
    yt_default_tags: List[str]

    # Runtime
    run_once: bool
    explicit_vod_file: Optional[Path]

    @staticmethod
    def from_env() -> "Settings":
        load_dotenv()

        watch_dir = Path(os.getenv("WATCH_DIR", "./data/storage/vods")).resolve()
        vod_ext_raw = os.getenv("VOD_EXTENSIONS", ".ts,.mp4,.mkv")
        vod_exts = tuple(
            e if e.startswith(".") else f".{e}"
            for e in [x.strip().lower() for x in vod_ext_raw.split(",") if x.strip()]
        )

        explicit_vod = os.getenv("VOD_FILE")
        yt_tags_raw = os.getenv("YT_DEFAULT_TAGS", "shorts,twitch,clips")
        yt_tags = [t.strip() for t in yt_tags_raw.split(",") if t.strip()]

        webhook_path = os.getenv("WEBHOOK_PATH", "/webhook/livestreamdvr")
        if not webhook_path.startswith("/"):
            webhook_path = "/" + webhook_path

        return Settings(
            trigger_mode=os.getenv("TRIGGER_MODE", "webhook").strip().lower(),
            webhook_host=os.getenv("WEBHOOK_HOST", "127.0.0.1"),
            webhook_port=int(os.getenv("WEBHOOK_PORT", "8090")),
            webhook_path=webhook_path,
            webhook_token=os.getenv("WEBHOOK_TOKEN", "").strip(),
            watch_dir=watch_dir,
            vod_extensions=vod_exts,
            poll_interval_sec=int(os.getenv("POLL_INTERVAL_SEC", "20")),
            stable_for_sec=int(os.getenv("STABLE_FOR_SEC", "120")),
            min_vod_size_mb=int(os.getenv("MIN_VOD_SIZE_MB", "200")),
            processed_state_file=Path(
                os.getenv("PROCESSED_STATE_FILE", "./processed_vods.json")
            ).resolve(),
            source_path_rewrite_from=os.getenv("SOURCE_PATH_REWRITE_FROM", "").strip(),
            source_path_rewrite_to=os.getenv("SOURCE_PATH_REWRITE_TO", "").strip(),
            publish_mode=os.getenv("PUBLISH_MODE", "local_http").strip().lower(),
            public_output_dir=Path(
                os.getenv("PUBLIC_OUTPUT_DIR", "./public_vods")
            ).resolve(),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
            dropbox_access_token=os.getenv("DROPBOX_ACCESS_TOKEN", "").strip(),
            dropbox_folder=os.getenv("DROPBOX_FOLDER", "/twitch_vods").rstrip("/"),
            opus_api_base=os.getenv("OPUS_API_BASE", "https://api.opus.pro"),
            opus_bearer_token=os.getenv("OPUS_BEARER_TOKEN", "").strip(),
            opus_org_id=os.getenv("OPUS_ORG_ID"),
            opus_user_id=os.getenv("OPUS_USER_ID"),
            opus_lang=os.getenv("OPUS_LANG", "en"),
            opus_clip_min_sec=int(os.getenv("OPUS_CLIP_MIN_SEC", "15")),
            opus_clip_max_sec=int(os.getenv("OPUS_CLIP_MAX_SEC", "30")),
            opus_layout_aspect_ratio=os.getenv("OPUS_LAYOUT_ASPECT_RATIO", "portrait"),
            opus_custom_prompt=os.getenv(
                "OPUS_CUSTOM_PROMPT", ""
            ),
            opus_brand_template_id=os.getenv("OPUS_BRAND_TEMPLATE_ID"),
            opus_source_lang=os.getenv("OPUS_SOURCE_LANG", "ru"),
            opus_wait_timeout_sec=int(os.getenv("OPUS_WAIT_TIMEOUT_SEC", "300")),
            opus_poll_interval_sec=int(os.getenv("OPUS_POLL_INTERVAL_SEC", "15")),
            yt_client_secret_file=Path(
                os.getenv("YT_CLIENT_SECRET_FILE", "./youtube_client_secret.json")
            ).resolve(),
            yt_token_file=Path(os.getenv("YT_TOKEN_FILE", "./youtube_token.json")).resolve(),
            yt_privacy_status=os.getenv("YT_PRIVACY_STATUS", "public"),
            yt_category_id=os.getenv("YT_CATEGORY_ID", "22"),
            yt_title_prefix=os.getenv("YT_TITLE_PREFIX", "Short clip"),
            yt_default_tags=yt_tags,
            run_once=_to_bool(os.getenv("RUN_ONCE", "true"), default=True),
            explicit_vod_file=Path(explicit_vod).resolve() if explicit_vod else None,
        )


class OpusClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.s.opus_bearer_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "x-opus-lang": self.s.opus_lang,
        }
        if self.s.opus_org_id:
            headers["x-opus-org-id"] = self.s.opus_org_id
        if self.s.opus_user_id:
            headers["x-opus-user-id"] = self.s.opus_user_id
        return headers

    def create_clip_project(self, video_url: str) -> str:
        log(f"Creating Opus clip project for URL: {video_url}")
        payload: Dict[str, Any] = {
            "videoUrl": video_url,
            "utm": {"source": "twitch_cutter"},
            "importPref": {"sourceLang": self.s.opus_source_lang},
            "curationPref": {
                "model": "Auto",
                "clipDurations": [[self.s.opus_clip_min_sec, self.s.opus_clip_max_sec]],
                "topicKeywords": [],
                "skipSlicing": False,
                "skipCurate": False,
                "genre": "Auto",
                "customPrompt": self.s.opus_custom_prompt,
                "enableAutoHook": True,
            },
            "renderPref": {"layoutAspectRatio": self.s.opus_layout_aspect_ratio},
        }
        if self.s.opus_brand_template_id:
            payload["brandTemplateId"] = self.s.opus_brand_template_id

        url = f"{self.s.opus_api_base.rstrip('/')}/api/clip-projects"
        r = self.session.post(url, headers=self._headers(), json=payload, timeout=90)
        r.raise_for_status()
        body = r.json()
        log("Opus clip project created successfully")
        return self._extract_project_id(body)

    @staticmethod
    def _extract_project_id(body: Dict[str, Any]) -> str:
        candidates: List[Optional[str]] = [
            body.get("projectId"),
            body.get("id"),
            body.get("data", {}).get("projectId") if isinstance(body.get("data"), dict) else None,
            body.get("data", {}).get("id") if isinstance(body.get("data"), dict) else None,
        ]
        for c in candidates:
            if c and isinstance(c, str):
                return c
        raise RuntimeError(f"Cannot find project id in Opus response: {body}")

    def wait_exportable_clips(self, project_id: str) -> List[Dict[str, Any]]:
        url = f"{self.s.opus_api_base.rstrip('/')}/api/exportable-clips"
        started = time.time()
        poll_no = 0
        while True:
            poll_no += 1
            r = self.session.get(
                url,
                headers=self._headers(),
                params={"projectId": project_id},
                timeout=45,
            )
            r.raise_for_status()
            body = r.json()
            clips = body.get("data", [])
            if isinstance(clips, list) and len(clips) > 0:
                log(f"Opus returned {len(clips)} clip(s) on poll #{poll_no}")
                return clips

            elapsed = time.time() - started
            if elapsed > self.s.opus_wait_timeout_sec:
                raise TimeoutError(
                    f"Opus clips are not ready after {self.s.opus_wait_timeout_sec}s"
                )
            log(
                f"Opus clips are not ready yet (poll #{poll_no}, elapsed={int(elapsed)}s). "
                f"Sleeping {self.s.opus_poll_interval_sec}s"
            )
            time.sleep(self.s.opus_poll_interval_sec)


class YouTubeUploader:
    def __init__(self, settings: Settings):
        self.s = settings
        self.service = self._build_service()

    def _build_service(self):
        creds = None
        if self.s.yt_token_file.exists():
            log(f"Loading existing YouTube token: {self.s.yt_token_file}")
            creds = Credentials.from_authorized_user_file(
                str(self.s.yt_token_file), YOUTUBE_SCOPES
            )
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                log("Refreshing expired YouTube token")
                creds.refresh(GoogleAuthRequest())
            else:
                log(
                    "YouTube token is missing/invalid. Starting OAuth local server flow. "
                    "If running on headless VPS, pre-generate youtube_token.json locally and copy it."
                )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.s.yt_client_secret_file), YOUTUBE_SCOPES
                )
                creds = flow.run_local_server(port=0)
            self.s.yt_token_file.write_text(creds.to_json(), encoding="utf-8")
            log(f"YouTube token saved to: {self.s.yt_token_file}")
        return build("youtube", "v3", credentials=creds)

    def upload(
        self,
        file_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
    ) -> str:
        log(f"Uploading clip to YouTube: {file_path.name}")
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags or self.s.yt_default_tags,
                "categoryId": self.s.yt_category_id,
            },
            "status": {
                "privacyStatus": self.s.yt_privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(str(file_path), chunksize=-1, resumable=True)
        req = self.service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            _, response = req.next_chunk()
        log(f"YouTube upload complete: video_id={response['id']}")
        return response["id"]


def load_processed(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"processed_files": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed_files": []}


def save_processed(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def list_vod_candidates(settings: Settings) -> List[Path]:
    if not settings.watch_dir.exists():
        return []
    files: List[Path] = []
    for p in settings.watch_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in settings.vod_extensions:
            files.append(p)
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def is_file_stable(path: Path, stable_for_sec: int) -> bool:
    size1 = path.stat().st_size
    time.sleep(max(1, stable_for_sec // 3))
    size2 = path.stat().st_size
    return size1 == size2


def wait_for_finished_vod(settings: Settings, processed: Dict[str, Any]) -> Path:
    min_bytes = settings.min_vod_size_mb * 1024 * 1024
    seen = set(processed.get("processed_files", []))
    cycle = 0

    while True:
        cycle += 1
        candidates = list_vod_candidates(settings)
        log(
            f"Poll cycle #{cycle}: found {len(candidates)} candidate file(s) in {settings.watch_dir}"
        )
        for p in candidates:
            key = str(p.resolve())
            if key in seen:
                continue
            if p.stat().st_size < min_bytes:
                continue
            age = time.time() - p.stat().st_mtime
            if age < settings.stable_for_sec:
                continue
            if is_file_stable(p, settings.stable_for_sec):
                log(f"Selected stable VOD for processing: {p}")
                return p
        log(f"No ready VOD yet. Sleeping {settings.poll_interval_sec}s")
        time.sleep(settings.poll_interval_sec)


def publish_vod_local_http(settings: Settings, vod_path: Path) -> str:
    settings.public_output_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{_safe_name(vod_path.name)}"
    dst = settings.public_output_dir / unique_name
    log(f"Publishing VOD via local_http: copy {vod_path} -> {dst}")
    shutil.copy2(vod_path, dst)
    return f"{settings.public_base_url}/{unique_name}"


def _upload_to_dropbox(dbx: Dropbox, local_path: Path, dropbox_path: str) -> None:
    """Upload file to Dropbox, using chunked upload for files > 150MB."""
    chunk_size = 4 * 1024 * 1024  # 4 MB
    file_size = local_path.stat().st_size

    with local_path.open("rb") as f:
        if file_size <= 150 * 1024 * 1024:  # <= 150 MB
            log(f"Uploading to Dropbox in single request: {local_path} -> {dropbox_path}")
            dbx.files_upload(f.read(), dropbox_path, mode=WriteMode.overwrite)
        else:
            log(
                f"Uploading to Dropbox via chunked session: {local_path} -> {dropbox_path}, "
                f"size={file_size} bytes"
            )
            data = f.read(chunk_size)
            result = dbx.files_upload_session_start(data)
            cursor = UploadSessionCursor(session_id=result.session_id, offset=f.tell())
            commit = CommitInfo(path=dropbox_path, mode=WriteMode.overwrite)

            while f.tell() < file_size:
                remaining = file_size - f.tell()
                data = f.read(min(chunk_size, remaining))
                if remaining <= chunk_size:
                    dbx.files_upload_session_finish(data, cursor, commit)
                else:
                    dbx.files_upload_session_append_v2(data, cursor)
                    cursor = UploadSessionCursor(session_id=cursor.session_id, offset=f.tell())


def publish_vod_dropbox(settings: Settings, vod_path: Path) -> str:
    dbx = Dropbox(settings.dropbox_access_token)
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{_safe_name(vod_path.name)}"
    dropbox_path = f"{settings.dropbox_folder}/{unique_name}"

    log(f"Publishing VOD via Dropbox to folder: {settings.dropbox_folder}")
    _upload_to_dropbox(dbx, vod_path, dropbox_path)

    try:
        shared = dbx.sharing_create_shared_link_with_settings(dropbox_path)
        url = shared.url
    except ApiError as e:
        if "shared_link_already_exists" in str(e).lower():
            result = dbx.sharing_list_shared_links(path=dropbox_path, direct_only=True)
            if result.links:
                url = result.links[0].url
            else:
                raise RuntimeError("Shared link exists but could not retrieve it") from e
        else:
            raise

    if "?dl=0" in url:
        url = url.replace("?dl=0", "?dl=1")
    elif "?" not in url:
        url = f"{url}?dl=1"
    log(f"Dropbox public URL prepared: {url}")
    return url


def publish_vod(settings: Settings, vod_path: Path) -> str:
    if settings.publish_mode == "local_http":
        return publish_vod_local_http(settings, vod_path)
    if settings.publish_mode == "dropbox":
        return publish_vod_dropbox(settings, vod_path)
    raise ValueError(
        f"Unsupported publish mode '{settings.publish_mode}'. Use local_http or dropbox."
    )


def download_clips(clips: List[Dict[str, Any]], output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: List[Path] = []
    for idx, clip in enumerate(clips, start=1):
        clip_id = clip.get("id", f"clip_{idx}")
        url = clip.get("uriForPreview")
        if not url:
            log(f"Clip {clip_id} has no uriForPreview, skipping", level="WARNING")
            continue
        target = output_dir / f"{_safe_name(str(clip_id))}.mp4"
        log(f"Downloading clip #{idx}: {url} -> {target}")
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        downloaded.append(target)
    return downloaded


def build_yt_text(clip: Dict[str, Any], settings: Settings, default_idx: int) -> Tuple[str, str]:
    raw_title = (clip.get("title") or "").strip()
    title = raw_title if raw_title else f"{settings.yt_title_prefix} #{default_idx}"
    description_parts = []
    if clip.get("description"):
        description_parts.append(str(clip["description"]).strip())
    if clip.get("hashtags"):
        description_parts.append(str(clip["hashtags"]).strip())
    description = "\n\n".join([p for p in description_parts if p])
    return title, description


def validate_settings(settings: Settings) -> None:
    if settings.explicit_vod_file is None and settings.trigger_mode == "poll" and not settings.watch_dir.exists():
        raise FileNotFoundError(f"WATCH_DIR not found: {settings.watch_dir}")
    if not settings.opus_bearer_token:
        raise ValueError("OPUS_BEARER_TOKEN is required")
    if settings.publish_mode == "local_http" and not settings.public_base_url:
        raise ValueError("PUBLIC_BASE_URL is required for local_http publish mode")
    if settings.publish_mode == "dropbox":
        if not settings.dropbox_access_token:
            raise ValueError("DROPBOX_ACCESS_TOKEN is required for dropbox publish mode")
    if not settings.yt_client_secret_file.exists():
        raise FileNotFoundError(
            f"YT client secrets file not found: {settings.yt_client_secret_file}"
        )
    if settings.trigger_mode not in {"webhook", "poll"}:
        raise ValueError("TRIGGER_MODE must be 'webhook' or 'poll'")


def log_startup_summary(settings: Settings, processed: Dict[str, Any]) -> None:
    log("Starting Twitch Cutter pipeline")
    log(f"Trigger mode: {settings.trigger_mode}")
    log(f"Publish mode: {settings.publish_mode}")
    log(f"Run once: {settings.run_once}")
    log(f"Watch dir: {settings.watch_dir}")
    log(f"Webhook endpoint: http://{settings.webhook_host}:{settings.webhook_port}{settings.webhook_path}")
    log(f"Processed state file: {settings.processed_state_file}")
    log(f"Already processed files: {len(processed.get('processed_files', []))}")
    log(f"YouTube client secret file: {settings.yt_client_secret_file}")
    log(f"YouTube token file: {settings.yt_token_file}")


def run_pipeline_for_vod(settings: Settings, processed: Dict[str, Any], vod_path: Path) -> None:
    log(f"Pipeline started for VOD: {vod_path}")
    if not vod_path.exists():
        raise FileNotFoundError(f"VOD file not found: {vod_path}")
    seen = set(processed.get("processed_files", []))
    if str(vod_path.resolve()) in seen:
        log(f"Skip already processed VOD: {vod_path}", level="WARNING")
        return
    video_url = publish_vod(settings, vod_path)
    log(f"Published VOD URL: {video_url}")

    opus = OpusClient(settings)
    project_id = opus.create_clip_project(video_url)
    log(f"Created Opus project: {project_id}")

    clips = opus.wait_exportable_clips(project_id)
    log(f"Opus clips ready: {len(clips)}")

    clips_dir = Path("./downloads") / project_id
    downloaded_files = download_clips(clips, clips_dir)
    log(f"Downloaded clips: {len(downloaded_files)} -> {clips_dir}")

    log("Starting YouTube uploader initialization")
    uploader = YouTubeUploader(settings)
    log("YouTube uploader initialized")
    for idx, file_path in enumerate(downloaded_files, start=1):
        clip_info = clips[idx - 1] if idx - 1 < len(clips) else {}
        title, description = build_yt_text(clip_info, settings, idx)
        video_id = uploader.upload(file_path, title, description)
        log(f"Uploaded to YouTube: {video_id} ({file_path.name})")

    processed.setdefault("processed_files", [])
    processed["processed_files"].append(str(vod_path.resolve()))
    save_processed(settings.processed_state_file, processed)
    log("Pipeline completed successfully.")


def _rewrite_source_path(settings: Settings, raw_path: str) -> Path:
    rewritten = raw_path
    if settings.source_path_rewrite_from and settings.source_path_rewrite_to:
        if rewritten.startswith(settings.source_path_rewrite_from):
            rewritten = settings.source_path_rewrite_to + rewritten[len(settings.source_path_rewrite_from):]
    return Path(rewritten).resolve()


def _largest_media_in_dir(directory: Path, extensions: Tuple[str, ...]) -> Optional[Path]:
    if not directory.exists():
        return None
    candidates = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_size, reverse=True)[0]


def resolve_vod_from_webhook(settings: Settings, payload: Dict[str, Any], processed: Dict[str, Any]) -> Optional[Path]:
    if payload.get("action") != "end_download":
        action = payload.get("action")
        log(f"Webhook action is not end_download: {action}", level="INFO")
        return None

    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    vod = data.get("vod", {}) if isinstance(data.get("vod"), dict) else {}

    direct_paths: List[str] = []
    for key in ("path_downloaded_vod", "path_playlist"):
        value = vod.get(key)
        if isinstance(value, str) and value.strip():
            direct_paths.append(value.strip())

    for raw in direct_paths:
        p = _rewrite_source_path(settings, raw)
        if p.exists() and p.is_file():
            if p.suffix.lower() in settings.vod_extensions:
                log(f"Resolved VOD from webhook direct path: {p}")
                return p
            if p.suffix.lower() in {".m3u8", ".txt"}:
                cand = _largest_media_in_dir(p.parent, settings.vod_extensions)
                if cand:
                    log(f"Resolved VOD from playlist/text reference: {cand}")
                    return cand

    basename = str(vod.get("basename", "")).strip()
    if basename and settings.watch_dir.exists():
        all_files = list(settings.watch_dir.rglob("*"))
        matching = [
            p for p in all_files
            if p.is_file() and p.suffix.lower() in settings.vod_extensions and basename in p.name
        ]
        if matching:
            unseen = [p for p in matching if str(p.resolve()) not in set(processed.get("processed_files", []))]
            use = unseen if unseen else matching
            chosen = sorted(use, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            log(f"Resolved VOD by basename fallback: {chosen}")
            return chosen

    log("Could not resolve VOD file from webhook payload", level="WARNING")
    return None


class WebhookHandler(BaseHTTPRequestHandler):
    event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
    settings: Optional[Settings] = None

    def _json_response(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if not WebhookHandler.settings:
            self._json_response(500, {"status": "error", "message": "Settings not loaded"})
            return
        s = WebhookHandler.settings

        if self.path != s.webhook_path:
            log(f"Received POST on unexpected path: {self.path}", level="WARNING")
            self._json_response(404, {"status": "error", "message": "Not found"})
            return

        if s.webhook_token:
            got = self.headers.get("X-Webhook-Token", "")
            if got != s.webhook_token:
                log("Webhook token mismatch", level="WARNING")
                self._json_response(401, {"status": "error", "message": "Unauthorized"})
                return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            log("Webhook payload JSON decode failed", level="WARNING")
            self._json_response(400, {"status": "error", "message": "Invalid JSON"})
            return

        action = payload.get("action")
        log(f"Webhook event accepted. action={action}")
        WebhookHandler.event_queue.put(payload)
        self._json_response(200, {"status": "ok"})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[webhook] {fmt % args}")


def start_webhook_server(settings: Settings) -> ThreadingHTTPServer:
    WebhookHandler.settings = settings
    httpd = ThreadingHTTPServer((settings.webhook_host, settings.webhook_port), WebhookHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    log(
        f"Webhook listener started on http://{settings.webhook_host}:{settings.webhook_port}{settings.webhook_path}"
    )
    return httpd


def main() -> None:
    settings = Settings.from_env()
    validate_settings(settings)
    processed = load_processed(settings.processed_state_file)
    log_startup_summary(settings, processed)

    if settings.explicit_vod_file:
        log(f"Explicit VOD_FILE mode enabled: {settings.explicit_vod_file}")
        run_pipeline_for_vod(settings, processed, settings.explicit_vod_file)
        return

    if settings.trigger_mode == "webhook":
        server = start_webhook_server(settings)
        handled = 0
        try:
            while True:
                try:
                    payload = WebhookHandler.event_queue.get(timeout=60)
                except queue.Empty:
                    log(
                        "Still waiting for webhook event (action=end_download). "
                        "No events received in last 60s."
                    )
                    continue
                vod_path = resolve_vod_from_webhook(settings, payload, processed)
                if not vod_path:
                    action = payload.get("action")
                    if action:
                        log(f"Ignored webhook action: {action}")
                    continue
                try:
                    run_pipeline_for_vod(settings, processed, vod_path)
                    handled += 1
                except Exception as exc:
                    log_exception("Pipeline error", exc)
                if settings.run_once and handled >= 1:
                    log("RUN_ONCE=true and one job handled. Exiting.")
                    break
        finally:
            log("Shutting down webhook server")
            server.shutdown()
    else:
        while True:
            try:
                log("Waiting for finished VOD in poll mode")
                vod_path = wait_for_finished_vod(settings, processed)
                run_pipeline_for_vod(settings, processed, vod_path)
            except Exception as exc:
                log_exception("Pipeline error", exc)
            if settings.run_once:
                log("RUN_ONCE=true and poll cycle completed. Exiting.")
                break
            time.sleep(max(10, settings.poll_interval_sec))


if __name__ == "__main__":
    main()
