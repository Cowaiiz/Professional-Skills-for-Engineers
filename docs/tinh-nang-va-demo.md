# Tính năng

**Home IoT Monitoring & Alert System · CC02 Nhóm 8**

## Những gì sản phẩm có

| Nhóm tính năng | Thao tác hoặc kết quả |
|---|---|
| Theo dõi trong nhà | Xem nhiệt độ, độ ẩm, phản ứng gas theo ADC, cửa, chuyển động và trạng thái kết nối. |
| Cảnh báo theo quy tắc | Nhiệt độ và gas có trạng thái Active và Cleared. Acknowledge ghi đã xem. Cửa và chuyển động được ghi theo sự kiện. |
| Camera mô phỏng | **Person enters** phát lại người đi qua vùng cửa. **Possible fall** cho nhân vật ngã và nằm yên 3 giây trước khi ghi sự kiện nghi ngờ té ngã. **Reset** đặt lại cảnh và nhật ký trên trang. Chọn **Camera test case** để thử mười ca, gồm hai người, ba vị trí té ngã, khuất một phần, đứng lên sớm và phòng trống. |
| Thông báo điện thoại | Ghi một tin cho mỗi lần gas chuyển Active hoặc node chuyển offline. Mặc định là **Preview only**. Có thể bật gửi tới chat Telegram riêng đã liên kết. |
| Xem lại và bàn giao | Lọc cảnh báo, mở Review để xem giá trị kích hoạt và thời gian phục hồi, thêm ghi chú có mốc thời gian lưu trong SQLite. |
| Lịch sử và trình chiếu | Biểu đồ, dòng thời gian, CSV tối đa 300 mẫu gần nhất và nút Present. |

Camera sử dụng nhân vật đồ họa và quan sát do chương trình tạo. Sự kiện nằm yên của nhân vật chỉ minh họa tình huống nghi ngờ té ngã. Phiên bản này chưa đọc video camera thật, chưa chạy AI nhận diện người và không xác nhận tình trạng ngất xỉu. Camera có nhật ký theo phiên trình duyệt. Dữ liệu cảm biến mô phỏng, cảnh báo, thông báo và ghi chú được lưu ở backend.

## Chạy demo trên Windows

Giải nén vào thư mục mới. Dừng bản demo cũ bằng Ctrl+C nếu đang chạy. Mở PowerShell tại thư mục **home-iot-monitoring** có `README.md` và `tools`.

```powershell
py -3.11 -m tools.run_demo --scenario home_showcase
```

Mở http://127.0.0.1:8080/ trong Edge sau khi PowerShell in địa chỉ.

1. **Giới thiệu phòng khách.** Chỉ nhãn **SIMULATED DATA**, các số đo và vùng cửa trong camera.
2. **Chiếu camera.** Bấm **Person enters**, rồi bấm **Possible fall**. Kịch bản té ngã phát sự kiện sau khoảng 5 giây tính từ lúc bấm.
3. **Chiếu cảnh báo và thông báo.** Khoảng giây 20–25, gas và nhiệt độ bật. Mục **Phone notifications** hiện bản xem trước tin gas. Bấm **Acknowledge**.
4. **Chiếu phục hồi.** Khoảng giây 55–60 cảnh báo gas chuyển **Cleared**. Kịch bản dừng gửi telemetry trong chốc lát, nên khoảng giây 75–80 sẽ có thông báo offline, rồi node trở lại online. Mở **Review** hoặc thêm ghi chú nếu còn thời gian.
5. Nếu đã liên kết bot và muốn gửi thật, làm theo [hướng dẫn Telegram](telegram.md) trước buổi demo. Khi chiếu ở chế độ preview, nói rõ đó là bản xem trước trong dashboard.

## Bố cục mã nguồn

- `backend/` lưu số đo, cảnh báo, ghi chú và hàng đợi thông báo. `telegram.py` gửi qua Telegram ở chế độ live.
- `dashboard/` là giao diện web. `camera-demo.js` phát cảnh mô phỏng. `notifications.js` hiển thị trạng thái thông báo.
- `simulator/` tạo dữ liệu và kịch bản demo. `tools/` chứa lệnh mở cả hệ thống, broker demo và công cụ lấy chat ID Telegram.
- `firmware/esp32/` chứa firmware và hướng dẫn nối mạch. Phần cứng vẫn cần kiểm chứng.
- `tests/` có kiểm thử quy tắc, kết nối, SQLite và luồng Telegram với phản hồi giả lập.

Có thể dùng ảnh minh chứng của chính dashboard cho slide về camera và điện thoại. Bộ slide Home IoT có mục lục, ảnh test và ghi chú thuyết trình tiếng Việt. Xem [bảng test camera](test-case-camera.md).
