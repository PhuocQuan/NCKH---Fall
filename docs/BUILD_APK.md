# Huong dan build APK Android

App APK dung **Capacitor** — goi web mobile (`mobile/web`) thanh ung dung Android.

## Yeu cau

1. **Node.js** 18+ (`node --version`)
2. **Android Studio** (co Android SDK)
3. Laptop chay server Python khi dung app:
   ```powershell
   python -m src.api_server --host 0.0.0.0 --port 8000
   ```

## Buoc 1 — Cai dependency

```powershell
cd D:\NCKH\NCKH---Fall\mobile\android-app
npm install
```

## Buoc 2 — Dong bo web vao Android

```powershell
npm run cap:sync
```

Lenh nay copy `mobile/web` -> `www/` va cap nhat project Android.

## Buoc 3 — Mo Android Studio

```powershell
npm run cap:open
```

Trong Android Studio:
1. Doi Gradle sync xong
2. **Build > Build Bundle(s) / APK(s) > Build APK(s)**
3. APK nam tai:
   `mobile/android-app/android/app/build/outputs/apk/debug/app-debug.apk`

## Buoc 4 — Cai APK len dien thoai

1. Copy `app-debug.apk` sang dien thoai (USB / Zalo / Drive)
2. Bat **Cho phep cai app khong ro nguon**
3. Cai va mo app **NCKH Fall Detection**

## Buoc 5 — Cau hinh lan dau

1. Laptop va dien thoai **cung WiFi** (hoac dung hotspot / Tailscale)
2. Chay server tren laptop
3. Trong app: tab **Cai dat**
4. Nhap **Dia chi server**: `http://10.128.90.194:8000` (thay bang IP laptop)
5. Bam **Luu & ket noi server**
6. Tab **Giam sat** -> **Start**

## Build APK release (nop bao cao / chia se)

Trong Android Studio:
- **Build > Generate Signed Bundle / APK**
- Tao keystore moi (luu mat khau!)
- Chon APK release

## Sua web roi build lai APK

```powershell
# Sua file trong mobile/web/
cd D:\NCKH\NCKH---Fall\mobile\android-app
npm run cap:sync
npm run cap:open
# Build APK lai trong Android Studio
```

## Loi thuong gap

| Loi | Cach xu ly |
|-----|------------|
| Khong ket noi server | Kiem tra IP, firewall, cung WiFi |
| Khung camera den | Bam Start; tat desktop_app |
| `cleartext not permitted` | Da cau hinh trong `network_security_config.xml` |
| Gradle loi | Mo Android Studio, File > Sync Project |

## Cau truc thu muc

```text
mobile/
  web/              # Web app (HTML/CSS/JS)
  android-app/
    www/              # Ban copy tu web (tu dong)
    android/          # Project Android (sau cap add android)
    package.json
```
