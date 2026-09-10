import re
from pathlib import Path

def bump_version():
    project_root = Path(__file__).resolve().parents[1]
    server_file = project_root / 'src' / 'web' / 'server.py'
    
    if not server_file.exists():
        print(f"Không tìm thấy file: {server_file}")
        return

    content = server_file.read_text(encoding='utf-8')
    
    # Tìm dòng chứa app = FastAPI(..., version="x.y.z")
    pattern = r'(version=")(\d+\.\d+\.)(\d+)(")'
    
    def replacer(match):
        prefix = match.group(1)
        major_minor = match.group(2)
        patch = int(match.group(3))
        suffix = match.group(4)
        new_patch = patch + 1
        new_version = f"{major_minor}{new_patch}"
        print(f"Đã cập nhật phiên bản lên: {new_version}")
        return f"{prefix}{new_version}{suffix}"
        
    new_content, count = re.subn(pattern, replacer, content)
    
    if count > 0:
        server_file.write_text(new_content, encoding='utf-8')
        print("Cập nhật thành công! Nhớ restart lại server để áp dụng version mới.")
    else:
        print("Không tìm thấy chuỗi version hợp lệ trong server.py.")

if __name__ == "__main__":
    bump_version()
