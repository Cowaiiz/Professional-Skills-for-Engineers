# Test case camera cho buổi thuyết trình

Trong dashboard Home IoT, cuộn đến **Living room camera**, chọn **Demo camera**, chọn mục **Camera test case** rồi bấm **Run case**. Chờ dòng **Replay complete**. Mỗi lần chạy sẽ tạo lại cảnh và nhật ký của ca đó. **Reset** đưa khung hình về phòng trống.

| Ca | Tình huống | Kết quả mong đợi và đã quan sát trên Edge |
|---|---|---|
| 01 | Một người đi qua vùng cửa | Một sự kiện vào phòng cho A. |
| 02 | Hai người lần lượt đi qua vùng cửa | Hai sự kiện vào phòng riêng, một cho A và một cho B. |
| 03 | A ngã giữa phòng | Một cảnh báo nghi ngờ té ngã sau ba giây trên sàn. |
| 04 | A ngã gần cửa | Một cảnh báo nghi ngờ té ngã cho A. |
| 05 | A ngã cạnh sofa | Một cảnh báo nghi ngờ té ngã cho A. |
| 06 | Có hai người, chỉ B ngã | Một cảnh báo cho B. A đứng và không bị gán cảnh báo. |
| 07 | Chỉ thấy một phần A ở mép khung | Limited view. Không ghi xác nhận đi vào. |
| 08 | A ngã nhưng một phần cơ thể nằm ngoài khung | Limited view. Không đủ quan sát để phát cảnh báo té ngã. |
| 09 | A xuống sàn rồi đứng lên trước ba giây | Không có cảnh báo té ngã. |
| 10 | Phòng trống | Không có nhân vật hay sự kiện. |
| Kiểm tra Reset | Bấm Reset khi cảnh ngã đang chạy | Dừng cảnh và xóa nhật ký. Hình cũ không tự quay lại. |

## Chọn ca để chiếu

- **Ca 02 và 06** cho thấy vì sao hệ thống mô phỏng phải theo dõi riêng từng người.
- **Ca 08** giải thích giới hạn khi bị khuất. Nếu muốn so sánh cùng vị trí, chiếu ca 05 và ca 08.
- Bấm **Person enters** hoặc **Possible fall** để chạy nhanh ca 01 hoặc 03.

Các cảnh do trình duyệt tạo từ vị trí, dáng người và độ nhìn rõ đã được lập sẵn. A và B là nhãn trong từng cảnh, không phải nhận diện danh tính. Hiện tượng ngất xỉu không thể được xác nhận từ các cảnh mô phỏng. Nhật ký camera và thông báo điện thoại là hai phần riêng. Telegram vẫn chỉ nhận sự kiện gas và node offline khi bật cấu hình gửi thật.

## Xem webcam của bạn

1. Mở địa chỉ HTTPS hoặc localhost trực tiếp trong Edge hoặc Chrome. Bấm **My camera** rồi cấp quyền.
2. Đặt camera cố định nhìn ngang. Cho một người đứng trong khung, thấy đủ vai, hông, đầu gối, bàn chân và phần sàn. Chờ **Fall detection ready**.
3. Chờ đường nối tư thế xuất hiện. Khi quan sát cho thấy tư thế chuyển nhanh từ đứng sang nằm thấp và kéo dài ít nhất ba giây, dashboard hiện **Possible fall**. Nếu bị khuất hoặc có nhiều người, dashboard yêu cầu chỉnh khung để có đủ dữ liệu.
4. Khi tập, dùng video kiểm thử hoặc động tác có kiểm soát. Có thể thử ngồi trên ghế, nằm trên sofa hoặc bước ra khỏi khung để kiểm tra các cảnh khác.
5. Chọn **Demo camera** để dừng webcam. Video và nhật ký té ngã webcam nằm trong phiên trình duyệt.

Phần webcam dùng MediaPipe Pose Landmarker Lite. Quy tắc xử lý điểm khớp đã thử với chuỗi điểm mô phỏng gồm ngã nhanh, ngồi, nằm trên sofa, chuyển tư thế chậm, đứng dậy sớm và mất dữ liệu. Edge qua HTTPS đã tải model và vẽ điểm tư thế từ ảnh mẫu đưa vào webcam ảo. Chưa đo độ chính xác trên ca té ngã thật. Chế độ này đưa tín hiệu để kiểm tra thêm, không xác định tình trạng ngất hoặc chấn thương.

[Tài liệu MediaPipe Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker?tab=Web)

## Chạy bản có 10 ca

Dừng demo cũ bằng Ctrl+C, giải nén ZIP mới vào một thư mục riêng, và mở PowerShell bên trong **home-iot-monitoring**.

```powershell
$env:TELEGRAM_MODE = 'preview'
py -3.11 -m tools.run_demo --scenario home_showcase
```

Mở địa chỉ PowerShell in ra. Nếu tab cũ còn hiển thị giao diện trước đó, nhấn Ctrl+F5.
