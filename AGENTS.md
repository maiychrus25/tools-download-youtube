# Local project notes

- This local Python/HTML tool is not currently a Git checkout. Preserve the operator's media folders and all existing downloads.
- Read `DESIGN.md` before UI changes and `SYSTEM_DOCUMENTATION.md` before changing download behavior.
- Reuse Python's standard library and the installed `yt-dlp`, `ffmpeg`, and `ffprobe` executables. No application package installation is needed.
- Verify changes with `make build`, `make test`, `make lint`, and `node scripts/check-docs.js`.
- Bind only to `127.0.0.1`. Browser cookies are optional and must not be read during automated checks.
- Keep test media, screenshots, logs, and rollback snapshots in an external temporary directory. Do not create experimental files inside this project.
