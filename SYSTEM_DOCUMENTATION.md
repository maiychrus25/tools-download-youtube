# YouTube MP3 local

Trạng thái: đã kiểm tra local ngày 2026-11-13. Đây là phần hoàn thiện tool Python/HTML đã có, không phải một dịch vụ public.

## Phạm vi và kiến trúc

- `server.py`: HTTP server chỉ nghe `127.0.0.1:8000`, gọi executable `yt-dlp` bằng danh sách argument, không dùng shell.
- `index.html`: form một cột, mặc định MP3, vẫn có MP4 tốt nhất và MP4 720p, theo màu sáng/tối của hệ điều hành.
- Dùng Python standard library và `yt-dlp`, `ffmpeg`, `ffprobe` đã cài. Không có dependency ứng dụng mới.
- Bản local chạy bằng `python3 server.py`, mở `http://127.0.0.1:8000/`.

## Luồng tải

1. Người dùng dán một URL YouTube, chọn định dạng và bấm tải. Nút và các tùy chọn bị khóa khi đang xử lý.
2. Server kiểm tra Host, Content-Type JSON, body dạng object tối đa 8 KiB, hostname YouTube và định dạng hợp lệ.
3. Mỗi lượt tải có thư mục UUID riêng trong `downloads/`, không ghi đè video hoặc tài liệu hiện có.
4. MP3 lấy `bestaudio/best`, dùng `--extract-audio --audio-format mp3 --audio-quality 0`. Không tải playlist. Chất lượng vẫn phụ thuộc âm thanh gốc.
5. Đọc đường dẫn file cuối từ JSON `after_move:%(filepath)j` của yt-dlp; chỉ chấp nhận file nằm trong đúng thư mục lượt tải. MP3 không đi qua bước chuyển mã video QuickTime.
6. Trình duyệt nhận link file và tự bắt đầu lưu. GET file thành công xóa bản tạm trên server; thiếu công cụ, timeout hoặc lỗi tải cũng dọn thư mục lượt lỗi.

## API và tương thích

`POST /download`, JSON: `url` (string), `quality` (`audio`, `best`, `720p`), `useCookies` (boolean tùy chọn). Trả `{ "name": "...mp3", "href": "/files/<job_id>/<name>" }` hoặc `{ "error": "..." }`.

Form mới luôn gửi `useCookies`, mặc định `false`. Chỉ bật checkbox khi cần dùng phiên đăng nhập Chrome. Với client cũ không gửi trường này, chế độ MP4 vẫn giữ mặc định dùng `chrome:Default`; MP3 mặc định không dùng cookie. `quality` bị bỏ trống vẫn giữ mặc định API cũ là `best`.

Tùy chọn `--ignore-config` tránh cấu hình yt-dlp bên ngoài thay đổi định dạng, nơi lưu hoặc tự chạy lệnh phụ. Tải MP4 và bước H.264/AAC cho QuickTime được giữ lại. Các thư mục khóa học, video cũ và tài liệu của chủ máy nằm ngoài phạm vi chỉnh sửa.

## Giới hạn

- Mỗi request xử lý một video, timeout tối đa 30 phút; không có hàng đợi hoặc tiến độ theo phần trăm.
- YouTube có thể yêu cầu đăng nhập hoặc đổi giao thức. Lỗi upstream được hiện trong form; không tự chuyển sang đọc cookie.
- Một lượt tải đã tạo xong nhưng chưa được trình duyệt lấy file vẫn giữ bản tạm để tải lại. Link hết hiệu lực sau lần nhận file thành công.
- MP4 chuyển mã dùng VideoToolbox của macOS theo hành vi sẵn có; chưa mở rộng sang hệ điều hành khác.

## Kiểm tra và bảo trì

Chạy `make build`, `make test`, `make lint`, `node scripts/check-docs.js`. Build kiểm tra cú pháp Python và dấu tài liệu vì ứng dụng không cần bundler. Lint dùng kiểm tra indentation của Python và cú pháp JavaScript của script kiểm tra tài liệu; browser checks kiểm tra mã JavaScript giao diện.

Khi thay đổi `server.py` hoặc `index.html`, đọc lại luồng tương ứng trong tài liệu và cập nhật dấu SHA-256 `docs-check` bên dưới trong cùng thay đổi. Các test tự động không đọc cookie hoặc cần kết nối YouTube.

## Kết quả kiểm tra local

- 14 test qua, bao gồm các kiểm tra URL/path, MP4/QuickTime cũ và luồng MP3 mới.
- Hai vòng browser check: desktop 1440px, mobile 390px sáng và 320px tối; không cuộn ngang hoặc lỗi JavaScript. Mỗi vòng từ chối 16 request không hợp lệ.
- Browser checks dùng file MP3 và MP4 H.264/AAC nhỏ để kiểm tra tải, lỗi, retry, trạng thái bận và tự dọn file.
- Kiểm tra riêng với YouTube thật: video công khai `aqz-KE-bpKQ` của Blender Foundation tải thành MP3, duration 634.624 giây, một stream audio và không có video. Không dùng cookie trong các kiểm tra.

<!-- docs-check: server.py c9b1de728ed63efea99967edbc09989bb69f18986add7c6cb950542d6cdab20a -->
<!-- docs-check: index.html dba9e0f9bbead91e9f4c798bfc0c7076a09dbbc9cbfd0f7bab1f96ea16bd585b -->
