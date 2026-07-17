# CatKey

Bộ gõ tiếng Việt miễn phí, mã nguồn mở, với giao diện giống EVKey.

- **Giao diện (UI/UX):** Python + PySide6
- **Lõi (chuyển đổi + hook bàn phím toàn hệ thống):** C
- **Kiểu gõ:** Telex và VNI (theo từ, đặt dấu đúng vị trí, hỗ trợ đầy đủ
  chữ hoa: Ê, Ô, Ơ, Ă, Đ, ...)
- **Ngôn ngữ:** English / Tiếng Việt (chuyển đổi ngay trong ứng dụng)

> English: see [`../README.md`](../README.md).

---

## Vì sao phải kiểm chứng bản build trước khi tin dùng

**Chỉ chạy những bản CatKey mà bạn có thể kiểm chứng.** Đây là khuyến nghị
của cộng đồng (không phải điều khoản giấy phép — CatKey dùng GPLv3, cho phép
mọi hình thức phân phối kể cả thương mại): chúng tôi khuyến cáo không phát
hành bản nhị phân bị làm rối (obfuscated) hoặc bị nén/đóng gói (packed), và
mong bản build có thể được kiểm chứng độc lập trước khi chia sẻ.

Lý do: UniKey là bộ gõ tiếng Việt nổi tiếng nhất. Trang **chính thức**
là **unikey.org**. Một trang khác, **unikey.vn**, *không* phải là dự án
chính thức và đã bị phản ánh là phát hành các bản UniKey kèm theo phần
mềm không mong muốn / có thể chứa mã độc, và **không có chữ ký số hợp
lệ**. Vì bộ gõ nhìn thấy mọi phím bạn nhấn, một bản bị chỉnh sửa là cực
kỳ nguy hiểm.

Khuyến nghị của CatKey: bản chia sẻ nên đến từ mã nguồn đã công bố, build
lại được (reproducible), kèm mã băm (checksum), và tốt nhất là được ít
nhất một bên độc lập build lại để đối chiếu trước khi cho tải về. Nếu một
bản CatKey bị đóng gói/nén, không có chữ ký, hoặc bạn không đối chiếu được
mã băm với bản build từ mã nguồn — **đừng chạy nó.**

---

## Bắt đầu nhanh (từ mã nguồn)

Yêu cầu: Python 3.11+, trình biên dịch C (MSVC hoặc GCC/Clang).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install PySide6-Essentials pynput
python run_ui.py
```

Lõi C (`catkey_core.dll` / `libcatkey_core.so`) sẽ được tự động build
trong lần chạy đầu tiên nếu có trình biên dịch.

## Tính năng

- Gõ tiếng Việt trên toàn hệ thống (Notepad, trình duyệt, chat, ...).
- Biểu tượng khay: nhấp trái để bật/tắt tiếng Việt; nhấp đúp để mở cài đặt.
- Phím tắt bật/tắt toàn cục (mặc định `Ctrl+Shift`).
- Phát hiện xung đột với bộ gõ khác (UniKey/EVKey/OpenKey/...).
- Chống chạy nhiều bản (tránh gõ bị nhân đôi).

## Tạo bản phân phối

```powershell
.\build.ps1 -Tool pyinstaller
.\build.ps1 -Tool nuitka -OneFile
```

```bash
./build.sh --tool pyinstaller
./build.sh --tool nuitka --onefile
```

Nếu định chia sẻ bản build cho người khác, hãy tuân theo yêu cầu kiểm
chứng trong [`../LICENSE`](../LICENSE).

## Giấy phép

CatKey được cấp phép theo **Giấy phép Công cộng GNU phiên bản 3 (GPLv3)**
hoặc phiên bản mới hơn. Xem [`../LICENSE`](../LICENSE).

**Tại sao là GPLv3:** CatKey chứa mã đảo ngược từ EVKey, vốn dựa trên
**UniKey**. UniKey phát hành dưới GPL, nên CatKey — với tư cách là tác phẩm
phái sinh — cũng phải dùng GPL. (Xem ghi chú trong `LICENSE`.) Điều này
cũng có nghĩa mã nguồn CatKey luôn phải công khai; hãy giữ bản build có thể
tái tạo và đi kèm mã nguồn khi chia sẻ.

**Bản sửa đổi (điều khoản bổ sung theo GPLv3 §7):** nếu bạn phân phối bản
sửa đổi, bạn phải đổi tên, đổi logo/biểu tượng và đánh dấu rõ là khác với
bản gốc. Bạn không được dùng tên hay logo "CatKey" hoặc "BlackCatOfficial"
để gắn nhãn/quảng bá bản sửa đổi hay sản phẩm phái sinh khi chưa được cho
phép bằng văn bản. Xem [`../LICENSE`](../LICENSE).
