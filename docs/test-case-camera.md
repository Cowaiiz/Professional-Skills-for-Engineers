# Kiểm thử camera cho buổi thuyết trình

## Xem webcam của bạn

1. Mở địa chỉ HTTPS hoặc localhost trực tiếp trong Edge hoặc Chrome. Chọn **My camera**, bấm nút khởi động và cấp quyền.
2. Đặt camera cố định và cho một người xuất hiện từ trước khi chuyển động, với vai và hông nhìn rõ. Chân và sàn giúp bộ nhận diện có thêm thông tin. Người trong khung có thể bắt đầu ở tư thế đứng hoặc ngồi.
3. Bộ nhận diện kiểm tra tốc độ hạ của vai và hông, sau đó theo dõi xem thân người có tiếp tục nằm thấp và nghiêng. Hộp chuyển **tím** với nhãn **Fall Detected** khi đủ bằng chứng. Nhãn xanh dương **Walking** và xanh lá **Sitting** là ước lượng từ tư thế và chuyển động. Mất dấu kéo dài hoặc có nhiều người làm hệ thống đặt lại lần kiểm tra.
4. Khi tập, dùng video kiểm thử hoặc động tác có kiểm soát. Có thể thử ngồi trên ghế, nằm trên sofa hoặc bước ra khỏi khung để kiểm tra các cảnh khác.
5. Dùng nút dừng hoặc chọn **Dataset video** để dừng webcam. Video và nhật ký té ngã webcam nằm trong phiên trình duyệt.

Phần webcam dùng MediaPipe Pose Landmarker Lite để phân tích tư thế và tính hộp quanh các điểm nhìn thấy trong trình duyệt. Quy tắc đã được kiểm tra với chuỗi điểm mô phỏng gồm ngã nhanh, ngồi, nằm trên sofa, chuyển tư thế chậm, đứng dậy sớm và mất dữ liệu. **Possible fall** là tín hiệu để kiểm tra thêm.

[Tài liệu MediaPipe Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker?tab=Web)

## Trình chiếu bằng clip GMDCSA-24

1. Mở **Dataset video** và chọn clip từ thư viện GMDCSA-24 v2.1. Dùng **Subject 1 / ADL / 13** cho cảnh đi rồi ngồi và **Subject 4 / Fall / 07** cho cảnh ngã.
2. Phát từ đầu để bộ nhận diện quan sát chuyển động trước khi ngã. Kéo thanh thời gian sẽ đặt lại lần nhận diện.
3. Clip đi rồi ngồi có hộp xanh dương **Walking** rồi chuyển xanh lá **Sitting**. Clip ngã chuyển sang hộp tím **Fall Detected** và ghi thời điểm **Possible fall** theo thời gian trong clip.

Hai clip trên có sẵn trong bản Git và ZIP ở mục **Suggested clips**. Để xem đủ 160 clip, trỏ backend tới thư mục dataset trên máy chạy backend. Xem [cách cấu hình](../README.md#host-the-gmdcsa-24-clip-library). Bạn cũng có thể mở MP4 cục bộ bằng bộ chọn tệp. Cả hai cách đều phân tích video trong trình duyệt. Nhãn dataset chỉ phục vụ đối chiếu kết quả kiểm thử.

[Nguồn phát hành GMDCSA-24 v2.1](https://doi.org/10.5281/zenodo.13354453)

### Kết quả trên toàn bộ 160 clip

Ngày 16/11/2026, MediaPipe Lite trích điểm khớp trên 160 clip GMDCSA-24 v2.1 trong Edge trên Windows, lấy mẫu 10 khung hình/giây. Hai quy tắc được so sánh trên cùng chuỗi điểm khớp. Thư mục và CSV gốc cung cấp nhãn đối chiếu. Một clip được tính là có cảnh báo nếu quy tắc ghi ít nhất một sự kiện.

| Nhóm | Ngã bản cũ | Ngã bản mới | Báo nhầm bản cũ | Báo nhầm bản mới |
|---|---:|---:|---:|---:|
| Subject 1–3, dùng để chỉnh luật mới | 11/62 | 42/62 | 0/61 | 0/61 |
| Subject 4, giữ riêng để kiểm tra luật mới | 0/17 | 4/17 | 0/20 | 2/20 |
| **Tổng** | **11/79 (13,9%)** | **46/79 (58,2%)** | **0/81** | **2/81** |

Trong 68 ca bản cũ bỏ sót, có 32 clip thiếu tư thế đứng đủ lâu, 21 clip qua bước đó nhưng không đủ điều kiện chuyển sang kiểm tra, và 15 clip bắt đầu kiểm tra nhưng thiếu bằng chứng để cảnh báo. Bản mới dùng chuyển động hạ của vai và hông so với các khung hình trước đó. Nó xác nhận sau ít nhất 0,8 giây từ khi phát hiện tư thế thấp và cần bằng chứng hợp lệ trong khoảng đó. Với các ca phát hiện có mốc đọc được, độ trễ trung vị giảm từ 3,9 xuống 1,5 giây. Hai cảnh báo nhầm đến từ clip chống đẩy. Nhóm giữ riêng vẫn bỏ sót 13/17 ca ngã. Các số liệu là thử nghiệm trên bốn người trong bộ dữ liệu.

## Chạy trên Windows

Dừng demo cũ bằng Ctrl+C, giải nén ZIP mới vào một thư mục riêng, và mở PowerShell bên trong **home-iot-monitoring**.

```powershell
$env:TELEGRAM_MODE = 'preview'
py -3.11 -m tools.run_demo --scenario home_showcase
```

Mở địa chỉ PowerShell in ra. Nếu tab cũ còn hiển thị giao diện trước đó, nhấn Ctrl+F5.
