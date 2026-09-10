# Logic phát hiện té ngã

## Mục tiêu

Hệ thống không cảnh báo chỉ vì thấy người đang nằm. Cảnh báo chỉ được tạo khi có chuỗi dấu hiệu:

1. Có chuyển động giống té ngã: thân người đổi tư thế nhanh, hông rơi nhanh, hoặc trước đó đang đứng/ngồi thẳng.
2. Sau chuyển động đó, người nằm ngang và đầu thấp gần mức hông.
3. Trạng thái nằm kéo dài quá `alert_after_seconds`, mặc định 10 giây.

Với logic này, người nằm ngủ sẵn trên giường/sàn sẽ được gán `lying`, không tạo cảnh báo nếu không có chuyển động giống té ngã trước đó.

Nếu cần demo nhanh tính năng cảnh báo trong phòng lab, có thể dùng:

```powershell
python -m src.core.app --source 0 --alert-on-long-lying
```

Chế độ này sẽ cảnh báo khi người nằm lâu hơn `alert_after_seconds` dù không có chuyển động giống té ngã. Nó hữu ích để test pipeline cảnh báo, nhưng không nên dùng làm kết quả chính khi đánh giá khả năng phân biệt nằm ngủ với té ngã.

## Các trạng thái

- `normal`: bình thường.
- `lying`: đang nằm nhưng chưa có dấu hiệu té ngã.
- `possible_fall`: có dấu hiệu bất thường ngắn hạn.
- `fallen`: đã xác nhận có chuỗi té ngã, đang đếm thời gian nằm.
- `alert`: đã té và nằm lâu hơn ngưỡng cảnh báo.

## Hỗ trợ nhiều nhóm người

Project không tự động đoán một người là người già, trẻ nhỏ, phụ nữ có thai hay người khuyết tật từ camera. Việc đó không ổn định và dễ sai. Thay vào đó, hệ thống có `profile` do người vận hành chọn trong `configs/default.yaml`:

- `default`
- `elderly`
- `child`
- `pregnant`
- `disabled`

Profile nhạy hơn sẽ giảm một số ngưỡng về tốc độ rơi, tốc độ đổi góc và số frame tối thiểu. Cách này phù hợp giai đoạn đầu của đề tài vì có thể demo và giải thích được.

## Bước tiếp theo để làm NCKH tốt hơn

- Thu thập video riêng cho từng nhóm đối tượng.
- Gán nhãn các đoạn: `normal`, `sleeping`, `sitting`, `lying`, `fall`.
- So sánh logic ngưỡng với model chuỗi thời gian như LSTM/GRU/Transformer trên landmark.
- Báo cáo Precision, Recall, F1-score riêng cho từng nhóm.
