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

## Gửi email (kết nối Mailtrap)

Các luồng của `django-allauth` cần gửi email thật: **xác thực email khi đăng ký**, **khôi phục mật khẩu**.
Máy dev dùng [Mailtrap](https://mailtrap.io) (Email Testing sandbox, có gói miễn phí) — email được "gửi" vào
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

### Không muốn cài Mailtrap, chỉ cần xem email ngay trên terminal

Đổi `EMAIL_BACKEND` trong `.env` thành:

```ini
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Email sẽ in thẳng ra terminal đang chạy `runserver` (kể cả link xác thực) thay vì gửi qua Mailtrap —
tiện lúc demo offline không có mạng, nhưng không có giao diện hộp thư để xem như Mailtrap.

## Giao diện 100% tiếng Việt (kể cả luồng của allauth)

`django-allauth` và `django-simple-captcha` không có sẵn bản dịch tiếng Việt, nên toàn bộ trang
đăng ký/đăng nhập/quên mật khẩu/xác thực email đã được:

1. Ghi đè bằng template tiếng Việt riêng trong [`templates/account/`](templates/account/) (nội dung
   trang, tiêu đề, nút bấm) và [`templates/account/email/`](templates/account/email/) (nội dung email
   gửi đi thật, ví dụ email xác thực/khôi phục mật khẩu).
2. Bổ sung bản dịch cho các chuỗi còn lại (nhãn field, thông báo lỗi, menu...) tại
   [`locale/vi/LC_MESSAGES/django.po`](locale/vi/LC_MESSAGES/django.po).

Máy dev **không có sẵn GNU gettext** (`msgfmt`) nên không dùng được `python manage.py compilemessages`.
Nếu sửa file `.po`, biên dịch lại bằng `polib` (cài 1 lần: `pip install polib`):

```powershell
python -c "import polib; po = polib.pofile('locale/vi/LC_MESSAGES/django.po'); po.save_as_mofile('locale/vi/LC_MESSAGES/django.mo')"
```

Rồi khởi động lại `runserver` (StatReloader tự nhận thay đổi `.mo` và restart, nhưng nếu không thấy
đổi thì tắt bật lại thủ công).

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
demo qua migration, tìm kiếm & lọc toàn hệ thống (app `search`, xem mục bên dưới), wireframe 8 màn hình
chính tại [`docs/wireframes/`](docs/wireframes/).

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
