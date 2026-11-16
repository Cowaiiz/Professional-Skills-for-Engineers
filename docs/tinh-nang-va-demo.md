# Tính năng

**Home IoT Monitoring & Alert System · CC02 Nhóm 8**

## Những gì sản phẩm có

| Nhóm tính năng | Thao tác hoặc kết quả |
|---|---|
| Theo dõi trong nhà | Xem nhiệt độ, độ ẩm, phản ứng gas theo ADC, cửa, chuyển động và trạng thái kết nối. |
| Cảnh báo theo quy tắc | Nhiệt độ và gas có trạng thái Active và Cleared. Acknowledge ghi đã xem. Cửa và chuyển động được ghi theo sự kiện. |
| Camera | **My camera** dùng webcam. **Dataset video** phát clip GMDCSA-24 từ thư viện hoặc tệp video trên máy. Hộp màu thể hiện đi, ngồi và nghi ngờ ngã. |
| Thông báo điện thoại | Ghi một tin cho mỗi lần gas chuyển Active hoặc node chuyển offline. Mặc định là **Preview only**. Có thể bật gửi tới chat Telegram riêng đã liên kết. |
| Xem lại và bàn giao | Lọc cảnh báo, mở Review để xem giá trị kích hoạt và thời gian phục hồi, thêm ghi chú có mốc thời gian lưu trong SQLite. |
| Lịch sử số đo | Bấm một thẻ số đo hoặc **View details** để mở biểu đồ và bảng dữ liệu gần đây. Có thể tải CSV và cuộn xem cảnh báo cũ. |

Camera dùng MediaPipe và quy tắc chuyển động vai, hông trong trình duyệt. Nhật ký camera nằm trong phiên đang mở. Backend lưu dữ liệu cảm biến, cảnh báo và ghi chú.

## Chạy demo trên Windows

Giải nén vào thư mục mới. Dừng bản demo cũ bằng Ctrl+C nếu đang chạy. Mở PowerShell tại thư mục **home-iot-monitoring** có `README.md` và `tools`.

```powershell
py -3.11 -m tools.run_demo --scenario home_showcase
```

Mở http://127.0.0.1:8080/ trong Edge sau khi PowerShell in địa chỉ.

1. **Giới thiệu phòng khách.** Chỉ nhãn **SIMULATED DATA** và các số đo.
2. **Chiếu camera.** Chọn **Dataset video** rồi phát Subject 4 / Fall / 07 để thấy hộp tím cảnh báo. Xem [cách cấu hình thư viện](../README.md#host-the-gmdcsa-24-clip-library).
3. **Chiếu cảnh báo và thông báo.** Khoảng giây 20–25, gas và nhiệt độ bật. Mục **Phone notifications** hiện bản xem trước tin gas. Bấm **Acknowledge**.
4. **Chiếu phục hồi.** Khoảng giây 55–60 cảnh báo gas chuyển **Cleared**. Kịch bản dừng gửi telemetry trong chốc lát, nên khoảng giây 75–80 sẽ có thông báo offline, rồi node trở lại online. Mở **Review** hoặc thêm ghi chú nếu còn thời gian.
5. Nếu đã liên kết bot và muốn gửi thật, làm theo [hướng dẫn Telegram](telegram.md) trước buổi demo. Khi chiếu ở chế độ preview, nói rõ đó là bản xem trước trong dashboard.

## Bố cục mã nguồn

- `backend/` lưu số đo, cảnh báo, ghi chú và hàng đợi thông báo. `telegram.py` gửi qua Telegram ở chế độ live.
- `dashboard/` là giao diện web. `camera-demo.js` điều khiển hai nguồn video. `notifications.js` hiển thị trạng thái thông báo.
- `simulator/` tạo dữ liệu và kịch bản demo. `tools/` chứa lệnh mở cả hệ thống, broker demo và công cụ lấy chat ID Telegram.
- `firmware/esp32/` chứa firmware và hướng dẫn nối mạch. Phần cứng vẫn cần kiểm chứng.
- `tests/` có kiểm thử quy tắc, kết nối, SQLite và luồng Telegram với phản hồi giả lập.

Xem [hướng dẫn và kết quả kiểm thử camera](test-case-camera.md).
