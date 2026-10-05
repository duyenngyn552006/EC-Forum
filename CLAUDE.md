# CLAUDE.md — Ngữ cảnh dự án cho Claude Code

## Tổng quan
Diễn đàn quản lý và trao đổi thông tin nội bộ **Khoa Thương mại điện tử - Marketing và Công nghệ số** (Trường Đại học Kinh tế - Đại học Đà Nẵng). Kết hợp mô hình truyền thông nội bộ tổ chức (kiểu Slack/Microsoft Workplace) với mô hình diễn đàn học thuật (kiểu Reddit): vừa là kênh thông báo chính thức tập trung từ Khoa/Trường, vừa là không gian thảo luận mở, nhóm nội bộ cho sinh viên và giảng viên.

Đề tài môn Lập trình Web, nhóm 7, GVHD TS. Đặng Trung Thành. Nguồn yêu cầu đầy đủ: `docs/bao-cao-tien-do-1.pdf` (báo cáo tiến độ 1, cần copy file gốc vào đây).

> ⚠️ File này viết dựa trên khảo sát/mô tả tính năng ở báo cáo tiến độ 1. Phần **Tech stack** là đề xuất dựa trên kinh nghiệm dự án trước (chưa có yêu cầu bắt buộc từ đề bài) — nhóm xác nhận lại trước khi bắt đầu code nếu môn học có ràng buộc công nghệ riêng.

## Tech stack (đề xuất)
- Backend: Django (mô hình MVT, KHÔNG dùng thuật ngữ MVC khi giải thích code)
- Database: SQLite (file `db.sqlite3`, chỉ chạy local để báo cáo/demo), truy cập qua Django ORM
- Cache & tác vụ nền: Redis + Celery (dùng cho: gửi thông báo, rate limiting, backup định kỳ)
- Auth: `django-allauth` — đăng nhập email/password. Xác thực tài khoản qua link email built-in (`ACCOUNT_EMAIL_VERIFICATION = "mandatory"`), khôi phục mật khẩu qua email built-in — KHÔNG tự viết OTP số.
- Bảo mật: `django-ratelimit` (giới hạn tần suất đăng bài/bình luận/báo cáo), `django-simple-captcha` (khi phát hiện hoạt động bất thường), hash mật khẩu bằng Argon2 (`django.contrib.auth.hashers.Argon2PasswordHasher`).
- Lưu trữ tệp: local media (ảnh đính kèm bài viết/thông báo); tài liệu chia sẻ dùng **link Google Drive dán tay** (theo đúng mô tả hệ thống trong báo cáo — KHÔNG tự xây file storage/upload tài liệu lớn).

## Đăng nhập giới hạn theo domain email trường/khoa — bắt buộc, không bỏ qua
Chỉ chấp nhận đăng ký/đăng nhập bằng email đúng domain chính thức của trường/khoa (vd `@dut.udn.vn`, domain thật do nhóm xác nhận). Validate ngay tại bước signup của allauth (custom `clean_email` trong signup form hoặc `ACCOUNT_SIGNUP_FORM_CLASS`), từ chối trước khi tạo tài khoản — không kiểm tra domain sau khi đã tạo.

## Cấu trúc Django app (mỗi app = 1 nhóm chức năng trong báo cáo)
| App | Model chính | Actor liên quan |
|---|---|---|
| `accounts` | User (kế thừa AbstractUser, field `role`) | Cả 4 actor |
| `announcements` | Announcement (thông tin chính thức Trường/Khoa + sự kiện phong trào) | Giáo vụ Khoa, BCH Khoa, User (xem) |
| `forum` | ForumPost, Category, Tag | Giảng viên, Sinh viên |
| `groups` | Group, GroupMembership, GroupPost | Giảng viên/BCN Khoa, BCH Khoa, Sinh viên |
| `interactions` | Comment (generic, threaded), Like (generic), SavedItem (generic) | Tất cả user đăng nhập |
| `notifications` | Notification, NotificationPreference | Tất cả user đăng nhập |
| `moderation` | Report, ModerationLog, AccountAppeal, SensitiveKeyword | Giáo vụ Khoa |
| `dashboard` | (không có model riêng, chỉ tổng hợp số liệu) | Giáo vụ Khoa |
| `search` | SearchHistory | Tất cả user đăng nhập (tìm kiếm/lọc dùng được cả khi chưa đăng nhập, riêng lịch sử chỉ lưu cho user đăng nhập) |

`interactions` dùng GenericForeignKey (theo đúng pattern `content_type` + `object_id`) để 1 model Comment/Like/SavedItem áp dụng chung cho Announcement, ForumPost, GroupPost — tránh lặp lại 3 bộ comment/like riêng cho từng loại nội dung.

## 4 actor (KHÔNG đơn giản hóa về 2 actor như model cũ)
- **Sinh viên**: vai trò mặc định khi đăng ký. Tạo bài thảo luận, bình luận, tham gia nhóm; **tạo nhóm phải qua duyệt** của Giáo vụ Khoa (khác Giảng viên/BCH — tạo nhóm có hiệu lực ngay).
- **Giảng viên / BCN Khoa**: phản hồi định hướng học thuật, duyệt nhóm thuộc phạm vi phụ trách. Có thể ghim bài trong phạm vi thông tin/thông báo chính thức. (Không xem được dashboard thống kê - chỉ Giáo vụ Khoa mới có quyền này, đã chốt với nhóm.)
- **BCH Khoa**: đăng thông tin sự kiện/hoạt động phong trào **không qua duyệt của BCN Khoa** (thuộc phạm vi BCH tự quản lý), quản lý nhóm BCH/dự án/hoạt động, ghim bài thuộc phạm vi phụ trách.
- **Giáo vụ Khoa (Quản trị viên hệ thống)**: đăng thông tin/thông báo chính thức (không qua duyệt nội bộ nào khác vì nội dung đã phê duyệt từ cấp trên trước khi đưa vào hệ thống), giám sát/kiểm duyệt toàn hệ thống, quản lý tài khoản (khóa/mở khóa), gán/thu hồi vai trò, duyệt yêu cầu tạo nhóm của sinh viên, xử lý báo cáo vi phạm và kháng nghị.

Vai trò lưu ở field `User.role` (choices: `student`, `lecturer`, `bch`, `staff`), KHÔNG tạo model Role riêng. Giáo vụ Khoa dùng `is_staff=True` để vào được Django admin; phân quyền chi tiết theo `role` xử lý ở tầng view/permission, không phải Django permissions/groups thuần túy vì quy tắc nghiệp vụ (ai đăng gì, ai duyệt gì) phức tạp hơn CRUD permission chuẩn.

## Tính năng đặc thù — bắt buộc làm đúng luồng, không đơn giản hóa
1. **Ghim bài có giới hạn số lượng đồng thời mỗi chuyên mục**: khi ghim 1 bài mới mà chuyên mục đã đạt số lượng ghim tối đa (cấu hình được, vd `MAX_PINNED_PER_CATEGORY`), phải từ chối thao tác (báo lỗi rõ ràng) hoặc yêu cầu bỏ ghim bài cũ trước — KHÔNG tự động bỏ ghim bài cũ nhất mà không hỏi.
2. **Bộ lọc từ khóa nhạy cảm tự động (tiền kiểm duyệt)**: khi submit bài viết/bình luận, quét nội dung qua danh sách từ khóa cấm (`SensitiveKeyword`, Giáo vụ Khoa quản lý được qua admin). Nếu phát hiện: KHÔNG đăng thẳng — chuyển bài sang trạng thái `pending_review` và báo người viết biết lý do, đợi Giáo vụ Khoa duyệt thủ công.
3. **Duyệt yêu cầu tạo nhóm của sinh viên**: sinh viên tạo nhóm → `Group.status = pending`. Giáo vụ Khoa duyệt (status → `active`, người đề xuất tự động là `role=leader` trong `GroupMembership`) hoặc từ chối kèm lý do bắt buộc nhập. Giảng viên/BCN Khoa và BCH Khoa tạo nhóm thì có hiệu lực ngay (`status = active`), không qua bước này.
4. **Lịch sử chỉnh sửa nội dung (version history thật, không chỉ `updated_at`)**: mỗi lần sửa Announcement/ForumPost/GroupPost phải lưu 1 bản ghi riêng (người sửa, thời điểm, nội dung/số lần sửa) trong model lịch sử riêng, không ghi đè. Người xem thường chỉ thấy nhãn "Đã chỉnh sửa" + thời gian gần nhất; Giáo vụ Khoa/BCN Khoa/BCH Khoa xem được toàn bộ các phiên bản để đối chiếu khi có khiếu nại.
5. **Nhật ký xử lý vi phạm + cơ chế kháng nghị khi khóa tài khoản**: mọi hành động kiểm duyệt (cảnh báo/ẩn/xóa/khôi phục/khóa tài khoản) phải ghi vào `ModerationLog` (ai, khi nào, hành động gì, lý do). User bị khóa tài khoản gửi được `AccountAppeal` (lý do, thông tin bổ sung); Giáo vụ Khoa xem lịch sử vi phạm trước khi chấp nhận/từ chối kháng nghị, kết quả phải thông báo lại cho user.

## Quy ước code
- Đặt tên biến/hàm bằng tiếng Anh, comment ngắn gọn tiếng Việt cho phần nghiệp vụ đặc thù (đặc biệt 5 phần ở mục trên).
- Ưu tiên Class-Based Views cho CRUD chuẩn (bài viết, bình luận, nhóm, thông báo); function-based view cho luồng nghiệp vụ đặc biệt (bộ lọc từ khóa, duyệt yêu cầu tạo nhóm, ghim có giới hạn, kháng nghị).
- Viết test cho: giới hạn số bài ghim/chuyên mục, bộ lọc từ khóa tự động chuyển `pending_review`, luồng duyệt/từ chối tạo nhóm (gán trưởng nhóm đúng người), version history khi sửa bài, rate limiting đăng bài/bình luận.

## Thứ tự xây dựng đề xuất
1. Khởi tạo project Django + cấu hình SQLite, Redis, Celery, allauth (giới hạn domain email)
2. App `accounts`: User + role, hồ sơ cá nhân, thống kê hồ sơ, lịch sử hoạt động, gán/thu hồi vai trò (Giáo vụ Khoa)
3. App `announcements`: thông tin chính thức Trường/Khoa + sự kiện phong trào (bản nháp, đính kèm ảnh, lịch sử chỉnh sửa, ghim có giới hạn)
4. App `forum` + `interactions`: bài viết thảo luận, chuyên mục/thẻ, comment theo luồng, like, save, share
5. App `groups`: tạo nhóm (luồng duyệt khác nhau theo vai trò), thành viên, phân quyền trong nhóm, bài đăng nội bộ
6. App `notifications`: danh sách, đã đọc/chưa đọc, cài đặt loại thông báo muốn nhận
7. App `moderation`: bộ lọc từ khóa tự động, kiểm duyệt bài đăng, xử lý report, khóa/mở tài khoản, nhật ký vi phạm, kháng nghị
8. ✅ Tìm kiếm & lọc toàn văn (cross-cutting, áp dụng cho announcements/forum/groups) — app `search`
9. App `dashboard`: thống kê người dùng/bài viết/tương tác, dashboard tổng quan cho Giáo vụ Khoa/BCN Khoa
10. Bảo mật: rà soát lại rate limiting, CAPTCHA, hash mật khẩu, backup định kỳ trên toàn hệ thống
11. Viết test cho các phần nghiệp vụ đặc thù ở mục "Quy ước code"
12. ✅ Giao diện: dựng template theo wireframe (mục "Thiết kế mockup/wireframe" trong kế hoạch nhóm) —
    wireframe 8 màn hình chính ở `docs/wireframes/`, giao diện thật đã dựng xong khớp bố cục

## Ghi chú phân công nhóm (tham khảo từ báo cáo tiến độ 1)
| Thành viên | Phụ trách module |
|---|---|
| Hồ Thị Thủy Tiên (Trưởng nhóm) | `accounts` (bảo mật, phân quyền), `interactions` |
| Võ Hồ Hà Phương | `announcements`, `notifications` |
| Trần Lê Phương Thanh | `forum`, tìm kiếm & lọc |
| Võ Thị Tuyết Nhung | `groups` |
| Nguyễn Thị Mỹ Duyên | `moderation`, `dashboard` |

## Đã chốt (cập nhật sau khi bắt đầu code)
- Domain email chính thức: `@due.udn.vn` (Trường Đại học Kinh tế - ĐHĐN).
- Số lượng bài ghim tối đa mỗi chuyên mục: `3` (cấu hình qua `MAX_PINNED_PER_CATEGORY`).
- Chỉ chạy local để báo cáo/demo — không cần HTTPS/domain thật/SMTP thật.
- Dashboard thống kê: chỉ Giáo vụ Khoa được xem (không mở cho BCN Khoa/Giảng viên/BCH).
- Tên hệ thống (branding): **EC Forum** — viết tắt ngắn gọn từ "E-Commerce" (khớp logo Khoa sẵn có), dùng xuyên suốt code/giao diện/README thay cho tên gọi "Khoa Forum" lúc khởi tạo dự án.
- Database: đổi từ PostgreSQL sang **SQLite** (file `db.sqlite3`) để đơn giản hóa cài đặt/demo local, không cần cài đặt PostgreSQL server. Không dùng tính năng riêng của Postgres nên việc đổi không ảnh hưởng logic/migration.

## Chưa xác định — cần nhóm chốt trước khi code
- Danh sách từ khóa nhạy cảm khởi tạo cho bộ lọc tự động (bảng `SensitiveKeyword` hiện đang rỗng, cần Giáo vụ Khoa nhập qua trang admin).
