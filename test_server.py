import http.client
import json
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import server


class ValidationTest(unittest.TestCase):
    def test_youtube_urls(self):
        for url in ["https://www.youtube.com/watch?v=abc", "https://youtu.be/abc", "http://m.youtube.com/watch?v=x"]:
            self.assertTrue(server.is_youtube_url(url), url)
        for url in ["", "ftp://youtube.com/x", "https://evil.com/youtube.com", "https://youtube.com.evil.com/x", "-o /tmp/x"]:
            self.assertFalse(server.is_youtube_url(url), url)

    def test_path_traversal_blocked(self):
        for job_id, name in [("..", "server.py"), ("x", "../server.py"), ("..", "../etc/passwd")]:
            self.assertIsNone(server.resolve_download(job_id, name))


class TranscodeArgsTest(unittest.TestCase):
    def test_quicktime_ready_needs_no_transcode(self):
        self.assertIsNone(server.transcode_args("h264", "aac"))

    def test_vp9_video_is_reencoded_audio_copied(self):
        args = server.transcode_args("vp9", "aac")
        self.assertEqual(args[args.index("-c:v") + 1], "h264_videotoolbox")
        self.assertEqual(args[args.index("-c:a") + 1], "copy")

    def test_opus_audio_is_reencoded_video_copied(self):
        args = server.transcode_args("h264", "opus")
        self.assertEqual(args[args.index("-c:v") + 1], "copy")
        self.assertEqual(args[args.index("-c:a") + 1], "aac")


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="youtube-mp3-test-")
        self.addCleanup(self.temp.cleanup)
        self.downloads = Path(self.temp.name)
        self.files_patch = patch.object(server, "DOWNLOADS", self.downloads)
        self.files_patch.start()
        self.addCleanup(self.files_patch.stop)
        self.command = []

    def download_file(self, command, **_kwargs):
        self.command = command
        folder = Path(command[command.index("-o") + 1]).parent
        suffix = "mp3" if "-x" in command else "mp4"
        output = folder / f"Kiểm tra âm thanh.{suffix}"
        output.write_bytes(b"downloaded media")
        (folder / "thumbnail.jpg").write_bytes(b"sidecar")
        return subprocess.CompletedProcess(command, 0, json.dumps(str(output)), "")

    def test_audio_uses_best_quality_without_browser_cookies(self):
        with patch.object(server.subprocess, "run", side_effect=self.download_file):
            job_id, name = server.run_ytdlp("https://youtu.be/aqz-KE-bpKQ", "audio")
        self.assertNotIn("--cookies-from-browser", self.command)
        self.assertIn("--ignore-config", self.command)
        self.assertEqual(self.command[self.command.index("--audio-quality") + 1], "0")
        self.assertEqual(name, "Kiểm tra âm thanh.mp3")
        self.assertEqual((self.downloads / job_id / name).read_bytes(), b"downloaded media")

    def test_browser_cookies_require_explicit_opt_in_for_audio(self):
        with patch.object(server.subprocess, "run", side_effect=self.download_file):
            server.run_ytdlp("https://youtu.be/aqz-KE-bpKQ", "audio", use_cookies=True)
        self.assertEqual(self.command[self.command.index("--cookies-from-browser") + 1], server.COOKIES_BROWSER)

    def test_existing_video_formats_and_legacy_login_still_work(self):
        for quality in ["best", "720p"]:
            with self.subTest(quality=quality), patch.object(server.subprocess, "run", side_effect=self.download_file), patch.object(server, "make_quicktime_ready") as convert:
                job_id, name = server.run_ytdlp("https://youtu.be/aqz-KE-bpKQ", quality)
                self.assertTrue(name.endswith(".mp4"))
                self.assertIn("--cookies-from-browser", self.command)
                convert.assert_called_once_with(self.downloads / job_id / name)

    def test_failed_jobs_are_removed(self):
        failures = [FileNotFoundError(), subprocess.TimeoutExpired("yt-dlp", 1)]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch.object(server.subprocess, "run", side_effect=failure):
                with self.assertRaises(RuntimeError):
                    server.run_ytdlp("https://youtu.be/aqz-KE-bpKQ", "audio")
                self.assertEqual(list(self.downloads.iterdir()), [])

    def test_invalid_or_external_output_is_rejected_and_cleaned(self):
        outside = self.downloads / "outside.mp3"
        outside.write_bytes(b"existing file")
        for stdout in ["not JSON", json.dumps(str(outside))]:
            with self.subTest(stdout=stdout), patch.object(server.subprocess, "run", return_value=subprocess.CompletedProcess("yt-dlp", 0, stdout, "")):
                with self.assertRaises(RuntimeError):
                    server.run_ytdlp("https://youtu.be/aqz-KE-bpKQ", "audio")
                self.assertEqual(list(self.downloads.iterdir()), [outside])
                self.assertEqual(outside.read_bytes(), b"existing file")

    def test_identical_titles_have_separate_jobs(self):
        with patch.object(server.subprocess, "run", side_effect=self.download_file):
            first = server.run_ytdlp("https://youtu.be/aqz-KE-bpKQ", "audio")
            second = server.run_ytdlp("https://youtu.be/aqz-KE-bpKQ", "audio")
        self.assertNotEqual(first[0], second[0])
        for job_id, name in [first, second]:
            self.assertTrue((self.downloads / job_id / name).is_file())


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="youtube-mp3-http-")
        self.addCleanup(self.temp.cleanup)
        self.downloads = Path(self.temp.name)
        self.files_patch = patch.object(server, "DOWNLOADS", self.downloads)
        self.files_patch.start()
        self.addCleanup(self.files_patch.stop)
        self.httpd = server.ThreadingHTTPServer((server.HOST, 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(server.HOST, self.httpd.server_port, timeout=3)
        request_headers = {"Host": f"{server.HOST}:{server.PORT}", "Content-Type": "application/json"}
        request_headers.update(headers or {})
        try:
            connection.request(method, path, json.dumps(body) if body is not None else None, request_headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_invalid_requests_return_400_without_starting_downloads(self):
        payloads = [[], "hello", {"url": "https://evil.invalid/video", "quality": "audio"}, {"url": "https://youtu.be/abc", "quality": []}, {"url": "https://youtu.be/abc", "quality": "audio", "useCookies": "yes"}]
        with patch.object(server, "run_ytdlp") as download:
            for payload in payloads:
                with self.subTest(payload=payload):
                    self.assertEqual(self.request("POST", "/download", payload)[0], 400)
            download.assert_not_called()

    def test_mp3_response_download_and_cleanup(self):
        job_id, name = "a" * 32, "Âm thanh thử.mp3"
        folder = self.downloads / job_id
        folder.mkdir()
        (folder / name).write_bytes(b"mp3 fixture")
        with patch.object(server, "run_ytdlp", return_value=(job_id, name)) as download:
            status, _, body = self.request("POST", "/download", {"url": "https://youtu.be/abc", "quality": "audio", "useCookies": False})
            self.assertEqual(status, 200)
            download.assert_called_once_with("https://youtu.be/abc", "audio", use_cookies=False)
            href = json.loads(body)["href"]
        status, headers, body = self.request("GET", href)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "audio/mpeg")
        self.assertIn(quote(name), headers["Content-Disposition"])
        self.assertEqual(body, b"mp3 fixture")
        deadline = time.monotonic() + 1
        while folder.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(folder.exists())

    def test_foreign_host_and_cross_origin_form_are_rejected(self):
        self.assertEqual(self.request("GET", "/", headers={"Host": "untrusted.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/download", {}, {"Content-Type": "text/plain"})[0], 404)


if __name__ == "__main__":
    unittest.main()
