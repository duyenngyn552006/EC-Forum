from django.db import migrations

# (ten chuyen muc, [(tieu de, noi dung, [ten tag]), ...]) - du lieu demo de moi chuyen muc
# co it nhat 3 bai viet va moi bai viet moi gan nhieu tag (bai viet mang tag, KHONG PHAI
# chuyen muc mang tag - 2 khai niem khac nhau trong schema).
POSTS_BY_CATEGORY = {
    "Thảo luận chung": [
        ("Góp ý cải thiện không gian tự học của Khoa", "Mọi người thấy khu tự học tầng 3 hơi thiếu ổ cắm điện, có nên góp ý với Khoa không?", ["Hỏi đáp", "Sự kiện"]),
    ],
    "Học tập": [
        ("Kinh nghiệm học tốt môn Nguyên lý Marketing", "Mình xin chia sẻ cách ôn tập môn này hiệu quả qua các kỳ trước, hy vọng giúp ích cho các bạn.", ["Kinh nghiệm học tập", "Hỏi đáp"]),
        ("Lịch thi học kỳ này có thay đổi không nhỉ", "Nghe nói lịch thi cuối kỳ có điều chỉnh, bạn nào có thông tin chính xác cho mình xin với.", ["Hỏi đáp"]),
        ("Chia sẻ phương pháp ghi chú hiệu quả khi học online", "Mình dùng phương pháp Cornell note-taking thấy khá hiệu quả, chia sẻ lại cho mọi người tham khảo.", ["Kinh nghiệm học tập", "Chia sẻ tài liệu"]),
    ],
    "Hỏi đáp": [
        ("Đăng ký học phần trễ có bị phạt không", "Mình lỡ quên đăng ký học phần đúng hạn, có cách nào xin đăng ký bổ sung không ạ?", ["Hỏi đáp"]),
        ("Thủ tục xin bảo lưu kết quả học tập như thế nào", "Bạn nào đã làm thủ tục bảo lưu rồi chỉ giúp mình quy trình với, cảm ơn nhiều.", ["Hỏi đáp", "Kinh nghiệm học tập"]),
    ],
    "Chia sẻ tài liệu": [
        ("Tổng hợp đề cương ôn tập môn Hành vi người tiêu dùng", "Mình tổng hợp đề cương ôn tập từ các kỳ trước, để link Google Drive bên dưới nhé.", ["Chia sẻ tài liệu", "Kinh nghiệm học tập"]),
        ("Slide bài giảng môn Thương mại điện tử căn bản", "Chia sẻ slide bài giảng đầy đủ các chương, các bạn vào link Google Drive để tải về.", ["Chia sẻ tài liệu"]),
        ("Tài liệu ôn thi môn Nguyên lý kế toán", "Tổng hợp công thức và bài tập mẫu môn Nguyên lý kế toán, hy vọng giúp ích mùa thi này.", ["Chia sẻ tài liệu", "Hỏi đáp"]),
    ],
    "Việc làm - Thực tập": [
        ("Tuyển thực tập sinh Marketing tại công ty X", "Công ty X đang tuyển thực tập sinh mảng Digital Marketing, bạn nào quan tâm liên hệ mình nhé.", ["Thực tập - Việc làm", "Sự kiện"]),
        ("Kinh nghiệm phỏng vấn vị trí Digital Marketing", "Mình vừa phỏng vấn xong, chia sẻ lại câu hỏi thường gặp cho các bạn chuẩn bị.", ["Thực tập - Việc làm", "Kinh nghiệm học tập"]),
        ("Cơ hội việc làm part-time cho sinh viên năm 3", "Có vài vị trí part-time phù hợp sinh viên năm 3 trở lên, ai cần thông tin inbox mình.", ["Thực tập - Việc làm"]),
    ],
    "Góc giải trí": [
        ("Giao lưu bóng đá giữa các lớp trong Khoa", "Khoa mình tổ chức giao lưu bóng đá cuối tháng này, lớp nào tham gia đăng ký giúp mình nhé.", ["Sự kiện"]),
        ("Ai có ảnh kỷ yếu khóa trước xin chia sẻ", "Mình đang làm video kỷ niệm, bạn nào còn giữ ảnh kỷ yếu khóa trước cho mình xin với.", ["Sự kiện", "Hỏi đáp"]),
        ("Góc than thở mùa thi", "Mùa thi đến rồi, vào đây than thở cho nhẹ lòng rồi quay lại học tiếp nào mọi người ơi.", ["Hỏi đáp"]),
    ],
}

AUTHOR_EMAILS = [
    "240101000001@due.udn.vn",
    "240101000002@due.udn.vn",
    "giangvien1@due.udn.vn",
    "giangvien2@due.udn.vn",
]


def seed_more_posts(apps, schema_editor):
    Category = apps.get_model("forum", "Category")
    Tag = apps.get_model("forum", "Tag")
    ForumPost = apps.get_model("forum", "ForumPost")
    User = apps.get_model("accounts", "User")

    authors = [u for u in (User.objects.filter(email=e).first() for e in AUTHOR_EMAILS) if u]
    if not authors:
        return

    author_index = 0
    for category_name, posts in POSTS_BY_CATEGORY.items():
        category = Category.objects.filter(name=category_name).first()
        if not category:
            continue
        existing_count = ForumPost.objects.filter(category=category).count()
        needed = max(0, 3 - existing_count)
        for title, body, tag_names in posts[:needed]:
            if ForumPost.objects.filter(category=category, title=title).exists():
                continue
            author = authors[author_index % len(authors)]
            author_index += 1
            post = ForumPost.objects.create(
                author=author, category=category, title=title, body=body, status="published",
            )
            for tag_name in tag_names:
                tag = Tag.objects.filter(name=tag_name).first()
                if tag:
                    post.tags.add(tag)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("forum", "0007_forumpost_view_count"),
    ]

    operations = [
        migrations.RunPython(seed_more_posts, noop),
    ]
