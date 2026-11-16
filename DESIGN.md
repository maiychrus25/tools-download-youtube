---
name: Local YouTube Audio
colors:
  light: { background: "#f6f7f9", surface: "#ffffff", text: "#16181d", muted: "#5b6270", border: "#d5d9e0", accent: "#d92d20", accentText: "#ffffff", success: "#067647", error: "#b42318" }
  dark: { background: "#111318", surface: "#1b1e25", text: "#eceef2", muted: "#a2a9b6", border: "#343a46", accent: "#f04438", accentText: "#111318", success: "#47cd89", error: "#fd853a" }
typography:
  body: { fontFamily: "system-ui, -apple-system, sans-serif", fontSize: "16px", lineHeight: 1.5 }
  heading: { fontSize: "1.375rem", fontWeight: 700 }
  label: { fontSize: "0.875rem" }
spacing: { page: "16px", card: "24px", field: "16px", small: "8px" }
rounded: { card: "12px", control: "8px" }
elevation: { card: "none" }
---

## Overview

Giữ form một cột đã có: nhập link, chọn định dạng, tùy chọn đăng nhập và một nút tải chính. MP3 là lựa chọn mặc định; MP4 vẫn có trong cùng form.

## Components and states

Thẻ nội dung rộng tối đa 520px. Input, select và nút chính dùng cùng chiều cao tối thiểu 44px. Checkbox đăng nhập có nhãn riêng; không bật sẵn. Trạng thái trống, đang xử lý, lỗi và file sẵn sàng dùng chữ rõ nghĩa, không chỉ dùng màu. Tên file hiển thị bằng text node.

## Responsive behavior and accessibility

Theo `prefers-color-scheme` cho toàn trang. Trang co vừa từ 320px, có lề 16px, không cuộn ngang. Label gắn với input; status có `role=status` và `aria-live=polite`; focus dùng viền accent 2px. Nút đang tải bị khóa để tránh gửi lặp. Tránh animation và tài nguyên giao diện bên ngoài.
