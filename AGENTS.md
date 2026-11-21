# Quy tắc dự án (Project Rules)

## Quy trình cập nhật phiên bản khi thay đổi Mobile
Mỗi khi có bất kỳ thay đổi nào liên quan đến Mobile (`app_fall/` hoặc `src/web/mobile/`):

1. **Nâng phiên bản (Version Bump)**:
   - File `app_fall/pubspec.yaml`: Tăng `version` và `build number` (ví dụ: `1.0.10+11` -> `1.0.11+12`).
   - File `src/web/server.py`: Cập nhật `version` trong `FastAPI(..., version="x.y.z")` đồng bộ với `pubspec.yaml`.

2. **Cập nhật Git (Commit, Tag & Push)**:
   - Commit code và thay đổi version với format: `Release vx.y.z: <Mô tả tóm tắt tính năng/thay đổi>`.
   - Tạo Git Tag: `git tag -a vx.y.z -m "Release vx.y.z"`.
   - Push commit lên branch đang làm việc: `git push origin <branch>`.
   - Push tag lên remote: `git push origin vx.y.z` (kích hoạt GitHub Actions CI/CD tự động đóng gói ứng dụng).
