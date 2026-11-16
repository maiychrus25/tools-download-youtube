"""Local YouTube downloader: serves index.html and wraps yt-dlp. Run: python3 server.py"""
import json
import mimetypes
import shutil
import subprocess
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

HOST, PORT = "127.0.0.1", 8000
ROOT = Path(__file__).resolve().parent
DOWNLOADS = ROOT / "downloads"
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
# Resolution first, then H.264 + AAC at that resolution; make_quicktime_ready() converts the rest. "best" caps at 1080p.
FORMATS = {
    "best": ["-f", "bv*+ba/b", "-S", "res:1080,vcodec:h264,acodec:aac", "--merge-output-format", "mp4"],
    "720p": ["-f", "bv*[height<=720]+ba/b[height<=720]", "-S", "res,vcodec:h264,acodec:aac", "--merge-output-format", "mp4"],
    "audio": ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"],
}
TIMEOUT_SECONDS = 1800
# Used only when browser login is requested; legacy video API calls retain their default.
COOKIES_BROWSER = "chrome:Default"


def is_youtube_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and (parsed.hostname or "") in YOUTUBE_HOSTS


def resolve_download(job_id, name):
    """Return the file path for /files/<job_id>/<name>, or None if outside downloads/."""
    path = (DOWNLOADS / job_id / name).resolve()
    if path.parent.parent != DOWNLOADS.resolve() or not path.is_file():
        return None
    return path


def transcode_args(vcodec, acodec):
    """ffmpeg codec args to make a file QuickTime-playable (H.264 + AAC), or None if it already is."""
    if vcodec in ("h264", "") and acodec in ("aac", ""):
        return None
    # shortcut: h264_videotoolbox is macOS-only; use libx264 if this ever runs elsewhere.
    video = ["-c:v", "copy"] if vcodec == "h264" else ["-c:v", "h264_videotoolbox", "-b:v", "2M", "-pix_fmt", "yuv420p"]
    audio = ["-c:a", "copy"] if acodec == "aac" else ["-c:a", "aac", "-b:a", "128k"]
    return video + audio


def probe_codec(path, stream):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", "stream=codec_name",
                             "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return result.stdout.strip()


def make_quicktime_ready(path):
    args = transcode_args(probe_codec(path, "v:0"), probe_codec(path, "a:0"))
    if args is None:
        return
    tmp = path.with_name(path.stem + ".transcoding.mp4")
    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), *args,
                                 "-movflags", "+faststart", str(tmp)], capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Quá thời gian chuyển mã video")
    if result.returncode != 0:
        raise RuntimeError("Chuyển mã lỗi: " + (result.stderr.strip().splitlines() or ["không rõ"])[-1])
    tmp.replace(path)


def run_ytdlp(url, quality, use_cookies=None):
    job_id = uuid.uuid4().hex
    job_dir = DOWNLOADS / job_id
    job_dir.mkdir(parents=True)
    if use_cookies is None:
        use_cookies = quality != "audio"
    cookies = ["--cookies-from-browser", COOKIES_BROWSER] if use_cookies else []
    cmd = ["yt-dlp", "--ignore-config", "--no-playlist", "--print", "after_move:%(filepath)j", *cookies,
           *FORMATS[quality], "-o", str(job_dir / "%(title)s.%(ext)s"), "--", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        if result.returncode != 0:
            lines = [line for line in result.stderr.splitlines() if line.strip()]
            raise RuntimeError(lines[-1] if lines else "Không tải được video này")
        try:
            output = Path(json.loads(result.stdout.strip()))
        except (ValueError, TypeError) as error:
            raise RuntimeError("Không xác định được file đã tải") from error
        if output.resolve().parent != job_dir.resolve() or not output.is_file() or (quality == "audio" and output.suffix.lower() != ".mp3"):
            raise RuntimeError("File tải về không hợp lệ")
        if quality != "audio":
            make_quicktime_ready(output)
        return job_id, output.name
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        shutil.rmtree(job_dir, ignore_errors=True)
        if isinstance(error, FileNotFoundError):
            raise RuntimeError("Thiếu công cụ tải/chuyển đổi (brew install yt-dlp ffmpeg)") from error
        if isinstance(error, subprocess.TimeoutExpired):
            raise RuntimeError("Quá thời gian tải, vui lòng thử lại") from error
        if isinstance(error, OSError):
            raise RuntimeError(f"Không thể lưu file: {error.strerror}") from error
        raise


class Handler(BaseHTTPRequestHandler):
    def _host_ok(self):
        # Blocks DNS-rebinding: only accept requests addressed to this local server.
        return self.headers.get("Host") in (f"{HOST}:{PORT}", f"localhost:{PORT}")

    def _json(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403)
        path = urlparse(self.path).path
        if path == "/":
            data = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        parts = path.split("/")
        if len(parts) == 4 and parts[1] == "files":
            file_path = resolve_download(parts[2], unquote(parts[3]))
            if file_path:
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(file_path.stat().st_size))
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(file_path.name))
                self.end_headers()
                with file_path.open("rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                # The browser now has its own copy; drop the server copy so files don't pile up.
                shutil.rmtree(file_path.parent, ignore_errors=True)
                return
        self.send_error(404)

    def do_POST(self):
        if not self._host_ok():
            return self.send_error(403)
        # Requiring JSON forces a CORS preflight, which we never answer, so other sites can't trigger downloads.
        if urlparse(self.path).path != "/download" or not self.headers.get("Content-Type", "").startswith("application/json"):
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 8192:
                raise ValueError("Invalid body size")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected an object")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "Dữ liệu không hợp lệ"})
        url, quality = str(body.get("url", "")).strip(), body.get("quality", "best")
        if not is_youtube_url(url):
            return self._json(400, {"error": "URL không phải link YouTube"})
        if not isinstance(quality, str) or quality not in FORMATS:
            return self._json(400, {"error": "Chất lượng không hợp lệ"})
        use_cookies = body.get("useCookies", quality != "audio")
        if not isinstance(use_cookies, bool):
            return self._json(400, {"error": "Tùy chọn đăng nhập không hợp lệ"})
        try:
            job_id, name = run_ytdlp(url, quality, use_cookies=use_cookies)
        except RuntimeError as e:
            return self._json(502, {"error": str(e)})
        self._json(200, {"name": name, "href": f"/files/{job_id}/{quote(name)}"})


if __name__ == "__main__":
    DOWNLOADS.mkdir(exist_ok=True)
    print(f"Mở http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
