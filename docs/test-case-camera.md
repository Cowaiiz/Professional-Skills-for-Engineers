# Test case camera cho buổi thuyết trình

Trong dashboard Home IoT, cuộn đến **Living room camera**, chọn mục **Camera test case** rồi bấm **Run case**. Chờ dòng **Replay complete**. Mỗi lần chạy sẽ tạo lại cảnh và nhật ký của ca đó. **Reset** đưa khung hình về phòng trống.

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

## Chạy bản có 10 ca

Dừng demo cũ bằng Ctrl+C, giải nén ZIP mới vào một thư mục riêng, và mở PowerShell bên trong **home-iot-monitoring**.

```powershell
$env:TELEGRAM_MODE = 'preview'
py -3.11 -m tools.run_demo --scenario home_showcase
```

Mở địa chỉ PowerShell in ra. Nếu tab cũ còn hiển thị giao diện trước đó, nhấn Ctrl+F5.
