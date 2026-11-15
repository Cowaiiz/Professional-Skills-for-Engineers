# Liên kết điện thoại qua Telegram

Telegram gửi tới **tài khoản Telegram đã mở cuộc trò chuyện với bot**, thông qua mã chat riêng. Số điện thoại dùng để đăng nhập Telegram. Dự án không gửi SMS.

## Chế độ xem trước tại chỗ

Mặc định `TELEGRAM_MODE=preview`. Mỗi lần cảnh báo gas mới bật hoặc node chuyển offline, backend tạo một mẫu tin trong **Phone notifications**. Tin xem trước không đi ra Internet. Để tắt tạo thông báo, đặt `TELEGRAM_MODE=off` trước khi chạy.

## Bật gửi thật

1. Tạo bot riêng bằng [@BotFather](https://t.me/BotFather). Mở bot trên điện thoại và bấm **Start**. Nếu bot đang phục vụ một ứng dụng khác qua webhook, hãy dùng bot riêng cho dự án.
2. Trong PowerShell, ở thư mục `home-iot-monitoring`, nhập token vào ô nhắc. Chỉ dùng token của bạn.

```powershell
$telegramSecret = Read-Host 'Bot token' -AsSecureString
$env:TELEGRAM_BOT_TOKEN = [System.Net.NetworkCredential]::new('', $telegramSecret).Password
py -3.11 -m tools.telegram_chat
```

3. Nhập chat ID của tài khoản đã mở bot rồi bật gửi thật. Chỉ bật tùy chọn gửi dữ liệu mô phỏng khi muốn nhận tin demo trên điện thoại. Backend cần Internet.

```powershell
$env:TELEGRAM_CHAT_ID = Read-Host 'Private chat ID'
$env:TELEGRAM_MODE = 'live'
$env:TELEGRAM_ALLOW_SIMULATED = '1'
py -3.11 -m tools.run_demo --scenario home_showcase
```

Dừng bản đang chạy trước khi đổi cài đặt. Để chỉ gửi cảnh báo từ ESP32, bỏ `TELEGRAM_ALLOW_SIMULATED` rồi khởi động lại backend. Khi kết thúc buổi demo, đóng PowerShell hoặc xóa các biến Telegram khỏi phiên hiện tại. Token và chat ID được đọc từ môi trường của backend. Dashboard không hiển thị các giá trị này.

**Accepted by Telegram** nghĩa là Telegram đã tiếp nhận yêu cầu. Nó không xác nhận người dùng đã đọc tin. Nếu kết quả gửi không xác định, bản ghi giữ trạng thái tương ứng để tránh tự gửi trùng. Các tin xem trước cũ không chuyển thành tin thật khi đổi chế độ. Camera mô phỏng có nhật ký riêng, còn hai sự kiện gửi Telegram là **gas cao** và **node offline**.

[Tài liệu Telegram Bot API](https://core.telegram.org/bots/api#sendmessage) · [Tạo bot với BotFather](https://core.telegram.org/bots/features#botfather)
