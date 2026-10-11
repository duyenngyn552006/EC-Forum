# EC Forum

Diễn đàn quản lý & trao đổi thông tin nội bộ Khoa Thương mại điện tử - Marketing và Công nghệ số
(Trường Đại học Kinh tế - Đại học Đà Nẵng). Bối cảnh nghiệp vụ đầy đủ (4 actor, 5 tính năng đặc thù,
cấu trúc app...) xem tại [`CLAUDE.md`](CLAUDE.md).

## Cấu trúc

Django project `config/`, 8 app theo đúng bảng trong `CLAUDE.md`:
`accounts`, `announcements`, `forum`, `groups`, `interactions`, `notifications`, `moderation`, `dashboard`.

Model dùng chung (trạng thái kiểm duyệt, ghim) nằm ở `config/mixins.py` (không phải 1 app, chỉ là module
tiện ích để tránh lặp field giữa `forum`, `announcements`, `groups`).

## Cài đặt lần đầu

### 1. Môi trường Python

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Database (SQLite)

Không cần cài đặt gì thêm — Django dùng file `db.sqlite3` tạo tự động ngay trong thư mục gốc dự án
ở bước Migrate bên dưới.

### 3. Biến môi trường

File `.env` đã có sẵn ở gốc dự án (copy mẫu từ `.env.example` nếu cần tạo lại). Các giá trị
**chưa chốt chính thức** (xem thêm mục "Chưa xác định" trong `CLAUDE.md`):

- `ALLOWED_SIGNUP_EMAIL_DOMAINS` — domain email được phép đăng ký (đã chốt `due.udn.vn`).
- `ALLOWED_SIGNUP_EXTRA_EMAILS` — (tùy chọn) danh sách email ngoại lệ được đăng ký/mời vào nhóm dù không đúng domain, phân cách bởi dấu phẩy. Dùng để test gửi mail bằng Gmail cá nhân khi demo; để trống khi không cần.
- `MAX_PINNED_PER_CATEGORY` — số bài ghim tối đa mỗi chuyên mục/phạm vi (đã chốt `3`).

### 4. Migrate

```powershell
python manage.py migrate
python manage.py runserver
```

Truy cập `http://127.0.0.1:8000/`. Lệnh `migrate` tự tạo sẵn dữ liệu mẫu (xem mục "Tài khoản demo" bên dưới)
— không cần chạy `createsuperuser` hay tự đăng ký.

## Tài khoản demo (tạo sẵn qua migration, chạy `migrate` là có)

`python manage.py migrate` tự xóa hết tài khoản cũ và tạo sẵn 8 tài khoản mẫu (2 tài khoản/vai trò),
cùng dữ liệu mẫu cho diễn đàn/nhóm/thông báo. Mật khẩu dùng chung cho cả 8 tài khoản:

```
Test@12345
```

| Email | Vai trò |
|---|---|
| `240101000001@due.udn.vn`, `240101000002@due.udn.vn` | Sinh viên |
| `giangvien1@due.udn.vn`, `giangvien2@due.udn.vn` | Giảng viên/BCN Khoa |
| `bch1@due.udn.vn`, `bch2@due.udn.vn` | BCH Khoa |
| `giaovu1@due.udn.vn`, `giaovu2@due.udn.vn` | Giáo vụ Khoa (`is_staff=True`, vào được `/admin/`) |

> ⚠️ Mật khẩu demo dùng chung, chỉ phục vụ dev/demo local — đổi mật khẩu thật trước khi đưa ra ngoài
> phạm vi nội bộ. Xem chi tiết seed data tại `accounts/migrations/0006_seed_demo_accounts.py`,
> `forum/migrations/0002_seed_demo_data.py`, `groups/migrations/0002_seed_demo_data.py`,
> `announcements/migrations/0003_seed_demo_data.py`.

Đăng nhập bằng `giaovu1@due.udn.vn` / `Test@12345` để vào `/admin/` quản lý toàn hệ thống (thêm
`Category` diễn đàn, gán/đổi vai trò tài khoản...). Riêng **từ khóa nhạy cảm** có trang quản lý
riêng ngay trong giao diện EC Forum (menu **Quản trị → Từ khóa nhạy cảm**, hoặc `/moderation/keywords/`)
— không cần vào `/admin/` nữa, tuy bảng vẫn còn đăng ký ở Django Admin song song.

## Redis / Celery

Máy dev hiện **chưa cài Redis**, nên mặc định:

- `CELERY_TASK_ALWAYS_EAGER=True` — các tác vụ nền (gửi thông báo hàng loạt khi đăng thông báo chính thức...)
  chạy đồng bộ ngay trong request, không cần Celery worker.
- `USE_REDIS_CACHE=False` — cache/rate-limit dùng bộ nhớ trong tiến trình (`LocMemCache`) thay vì Redis.

Khi triển khai thật hoặc cần chạy nền/rate-limit chia sẻ giữa nhiều tiến trình: cài Redis, set
`USE_REDIS_CACHE=True`, `CELERY_TASK_ALWAYS_EAGER=False`, rồi chạy thêm:

```powershell
celery -A config worker -l info -P solo
celery -A config beat -l info
```

## Gửi email

Các luồng của `django-allauth` cần gửi email: **xác thực email khi đăng ký**, **khôi phục mật khẩu**.
Có 3 cách, chọn bằng các biến `EMAIL_*` trong `.env`:

| Cách | Mail đi đâu | Khi nào dùng |
|---|---|---|
| In ra terminal (`console`) | Không gửi, in nội dung + link vào terminal đang chạy `runserver` | Code/demo offline, nhanh nhất |
| Mailtrap | Hộp thư ảo trên mailtrap.io, **không** tới hộp thư thật | Kiểm tra nội dung mail an toàn |
| **Gmail SMTP** | **Hộp thư thật** của người nhận | Test đúng như khi chạy thật, cũng là cấu hình đang dùng trên server PythonAnywhere |

### Kết nối Mailtrap

Máy dev có thể dùng [Mailtrap](https://mailtrap.io) (Email Testing sandbox, có gói miễn phí) — email được "gửi" vào
1 hộp thư ảo riêng để xem nội dung/bấm link, **không bao giờ bay vào hộp thư thật** dù địa chỉ nhận là email
sinh viên/giảng viên thật.

### Cách lấy thông tin kết nối

1. Đăng ký tài khoản miễn phí tại [mailtrap.io](https://mailtrap.io).
2. Vào **Email Testing** → chọn (hoặc tạo) 1 **Inbox**.
3. Mở tab **SMTP Settings** trong inbox đó → chọn mục **Django** (hoặc bất kỳ, chỉ cần lấy đúng
   Username/Password) → copy 2 giá trị **Username** và **Password**.

### Cách khai vào `.env`

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=sandbox.smtp.mailtrap.io
EMAIL_PORT=2525
EMAIL_HOST_USER=<Username lấy từ Mailtrap>
EMAIL_HOST_PASSWORD=<Password lấy từ Mailtrap>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=EC Forum <no-reply@due.udn.vn>
```

Khởi động lại `runserver` sau khi sửa `.env` (biến môi trường chỉ đọc lúc Django khởi động).

### Cách kiểm tra đã kết nối đúng

1. Vào trang đăng ký (`/accounts/signup/`), tạo tài khoản mới bằng email `@due.udn.vn` bất kỳ.
2. Mở lại Mailtrap → inbox vừa cấu hình → sẽ thấy 1 email mới với tiêu đề xác thực tài khoản
   (nội dung lấy từ [`templates/account/email/email_confirmation_message.txt`](templates/account/email/email_confirmation_message.txt)).
3. Bấm link xác thực ngay trong email đó (Mailtrap cho xem/bấm link như hộp thư thật) → tài khoản được kích hoạt.

Nếu không thấy email nào xuất hiện: kiểm tra lại `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` trong `.env` có đúng
với Mailtrap không, và chắc chắn đã khởi động lại `runserver`.

### Gửi email thật (Gmail SMTP) khi chạy local

Mail sẽ tới **hộp thư thật** của người nhận, gửi từ 1 tài khoản Gmail cá nhân (Gmail free gửi được khoảng 500 mail/ngày).

**Bước 1 — Tạo App Password cho Gmail dùng để gửi.** Không dùng mật khẩu Gmail thật.

1. Đăng nhập đúng tài khoản Gmail sẽ dùng để gửi.
2. Bật **Xác minh 2 bước** tại <https://myaccount.google.com/security> (bắt buộc — chưa bật thì trang ở bước 3 báo **404**).
3. Mở <https://myaccount.google.com/apppasswords> (chú ý có chữ **s** ở cuối), đặt tên ứng dụng `EC Forum` → **Tạo**.
4. Google hiện 16 ký tự dạng `abcd efgh ijkl mnop` (chỉ hiện **1 lần**). Bỏ hết dấu cách → `abcdefghijklmnop`.

**Bước 2 — Khai vào `.env`** (thay cho các dòng `EMAIL_*` cũ, mỗi biến chỉ 1 dòng):

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tencuaban@gmail.com
EMAIL_HOST_PASSWORD=abcdefghijklmnop
DEFAULT_FROM_EMAIL=EC Forum <tencuaban@gmail.com>
```

- `EMAIL_HOST_PASSWORD` là đúng 16 chữ cái của App Password: **không dấu cách, không dấu nháy, không `< >`**.
- `EMAIL_HOST_USER` và `DEFAULT_FROM_EMAIL` phải là **cùng** tài khoản Gmail đã tạo App Password.
- Muốn tự nhận mail bằng Gmail cá nhân khi đăng ký thử (form đăng ký chỉ nhận `@due.udn.vn`), thêm email đó vào
  danh sách ngoại lệ: `ALLOWED_SIGNUP_EXTRA_EMAILS=tencuaban@gmail.com`.
- Không commit `.env` lên git (đã có trong `.gitignore`), không gửi App Password qua chat/nhóm.

**Bước 3 — Khởi động lại `runserver`** (Ctrl+C rồi chạy lại). Django chỉ đọc `.env` lúc khởi động.

**Bước 4 — Gửi thử:**

```powershell
python manage.py shell
```

```python
from django.conf import settings as s
p = s.EMAIL_HOST_PASSWORD
print(s.EMAIL_BACKEND, s.EMAIL_HOST, s.EMAIL_PORT, s.EMAIL_HOST_USER, "| do dai mat khau:", len(p))  # phai la 16
from django.core.mail import send_mail
send_mail("Test EC Forum", "Mail thử từ máy local", None, ["tencuaban@gmail.com"])  # tra ve 1 la da gui
```

Trả về `1` và hộp thư nhận được mail (xem cả **Spam**) là xong. Sau đó đăng ký / quên mật khẩu trên web sẽ gửi mail thật.

**Lỗi thường gặp**

| Hiện tượng | Nguyên nhân | Cách sửa |
|---|---|---|
| Nội dung mail in ra terminal thay vì gửi đi | `.env` vẫn còn `EMAIL_BACKEND=...console...` (hoặc có 2 dòng `EMAIL_BACKEND`, dòng sau thắng), hoặc chưa khởi động lại `runserver` | Giữ đúng 1 dòng `smtp.EmailBackend`, khởi động lại |
| `SMTPServerDisconnected: Connection unexpectedly closed` lúc đăng nhập SMTP | Mật khẩu bị dán sai — thường là còn `< >`/dấu nháy/dấu cách (độ dài khác 16) | Sửa `EMAIL_HOST_PASSWORD` thành đúng 16 chữ cái |
| `SMTPAuthenticationError (535) Username and Password not accepted` | App Password sai, đã bị xóa, hoặc `EMAIL_HOST_USER` khác tài khoản tạo App Password | Tạo App Password mới cho đúng tài khoản |
| Trang apppasswords báo 404 | Chưa bật Xác minh 2 bước, hoặc đang đăng nhập nhầm tài khoản Google khác | Bật 2 bước / đổi tài khoản rồi mở lại |
| `TimeoutError` / không kết nối được | Mạng chặn cổng 587 (mạng trường, công ty) | Thử cổng 465: `EMAIL_PORT=465`, `EMAIL_USE_TLS=False`, `EMAIL_USE_SSL=True` |
| Gửi được nhưng không thấy mail | Bị lọc vào Spam; mail trường `@due.udn.vn` có thể bị giữ/chậm vài phút | Xem Spam / "Tất cả thư"; thử gửi tới Gmail trước |
| Link trong mail đúng nhưng dòng cuối mail ghi `127.0.0.1:8000` | Tên miền của Site trong DB (bảng `django_site`) | Ở local là bình thường. Trên server sửa 1 lần trong `python manage.py shell` (hoặc trang admin → Sites) thành domain thật |

> Allauth giới hạn gửi lại mail xác thực (khoảng 1 lần / 3 phút cho cùng 1 email) — bấm "gửi lại" liên tục sẽ không có thêm mail.

### Không muốn cài Mailtrap, chỉ cần xem email ngay trên terminal

Đổi `EMAIL_BACKEND` trong `.env` thành:

```ini
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Email sẽ in thẳng ra terminal đang chạy `runserver` (kể cả link xác thực) thay vì gửi qua Mailtrap —
tiện lúc demo offline không có mạng, nhưng không có giao diện hộp thư để xem như Mailtrap.

## Trình soạn thảo rich text (CKEditor 5)

Nội dung dài (`ForumPost.body`, `Announcement.body`, `GroupPost.body`) dùng `django-ckeditor-5` thay vì
ô textarea thường — có định dạng đậm/nghiêng, tiêu đề, danh sách, chèn ảnh/link. Bình luận (`Comment`)
vẫn giữ plain text cho nhẹ.

Nội dung trả về là HTML nên **luôn lọc qua `config/sanitize.py` (dùng `bleach`) trước khi lưu DB** —
chỉ cho phép một danh sách thẻ/attribute an toàn, tự động loại bỏ `<script>`, `onerror`... để chặn XSS
kể cả khi có người cố gửi thẳng HTML độc hại qua request (bỏ qua giao diện editor).

## Trạng thái hiện tại

Đã có: models, admin, service layer cho 5 tính năng đặc thù (ghim giới hạn, lọc từ khóa tự động, duyệt
tạo nhóm, lịch sử chỉnh sửa, nhật ký kiểm duyệt + kháng nghị), views (CBV cho CRUD chuẩn, FBV cho luồng
nghiệp vụ đặc biệt), rate limiting cho đăng bài/bình luận, hash mật khẩu Argon2, giới hạn domain email
khi đăng ký (tách riêng Họ/Tên/Lớp), avatar + ảnh bìa ở trang hồ sơ, template tối giản đủ chạy, dữ liệu
demo qua migration, tìm kiếm & lọc toàn hệ thống (app `search`, xem mục bên dưới).

Chưa làm: backup định kỳ qua Celery beat (task chưa viết).

## Tìm kiếm & lọc thông tin (app `search`)

Ô tìm kiếm ở header (mọi trang) và trang `/search/` gộp kết quả từ cả 3 loại nội dung
(`Announcement`, `ForumPost`, `GroupPost`), lọc được theo loại nội dung, danh mục (diễn đàn),
tác giả/người đăng, lớp và khoảng thời gian đăng. Người dùng thường chỉ thấy nội dung đã đăng
công khai (`status=published`); riêng Giáo vụ Khoa thấy cả nội dung đang chờ kiểm duyệt/đã ẩn để
phục vụ giám sát. Tìm kiếm dùng `icontains` đơn giản trên tiêu đề/nội dung (không phải full-text
search chuyên dụng — dự án dùng SQLite cho demo local nên không cần over-engineer phần này).

Lịch sử tìm kiếm (`SearchHistory`) chỉ lưu cho user đã đăng nhập, tối đa 10 từ khóa gần nhất/người,
dùng làm nguồn gợi ý khi gõ lại vào ô tìm kiếm ở header (dropdown JS thuần, không cần gọi API riêng).
