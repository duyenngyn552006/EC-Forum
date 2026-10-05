from django.utils import timezone

from accounts.models import User
from config.mixins import ContentStatus
from config.sanitize import sanitize_html
from moderation.services import find_sensitive_keyword, log_action
from moderation.models import ModerationLog
from notifications.models import Notification
from notifications.services import notify

from .models import Group, GroupMembership, GroupPost, GroupPostEditHistory


def request_create_group(creator, name, description, logo=None, cover_image=None):
    """Sinh vien -> pending, cho duyet. Giang vien/BCN/BCH -> active ngay, la leader luon."""
    if creator.role == User.Role.STUDENT:
        group = Group.objects.create(
            name=name, description=description, created_by=creator, status=Group.Status.PENDING,
            logo=logo, cover_image=cover_image,
        )
    else:
        group = Group.objects.create(
            name=name, description=description, created_by=creator,
            status=Group.Status.ACTIVE, approved_at=timezone.now(),
            logo=logo, cover_image=cover_image,
        )
        GroupMembership.objects.create(group=group, user=creator, role=GroupMembership.Role.LEADER)
    return group


def approve_group(group: Group, staff):
    group.status = Group.Status.ACTIVE
    group.approved_by = staff
    group.approved_at = timezone.now()
    group.reject_reason = ""
    group.save()
    GroupMembership.objects.get_or_create(
        group=group, user=group.created_by, defaults={"role": GroupMembership.Role.LEADER}
    )
    log_action(actor=staff, action=ModerationLog.Action.APPROVE_GROUP, reason="Duyệt yêu cầu tạo nhóm", target_user=group.created_by, content_object=group)
    notify(
        recipient=group.created_by, verb=Notification.Verb.GROUP_APPROVED, actor=staff,
        message=f"Nhóm '{group.name}' đã được duyệt.", content_object=group,
    )
    return group


def reject_group(group: Group, staff, reason: str):
    if not reason.strip():
        raise ValueError("Phải nhập lý do khi từ chối yêu cầu tạo nhóm.")
    group.status = Group.Status.REJECTED
    group.approved_by = staff
    group.approved_at = timezone.now()
    group.reject_reason = reason
    group.save()
    log_action(actor=staff, action=ModerationLog.Action.REJECT_GROUP, reason=reason, target_user=group.created_by, content_object=group)
    notify(
        recipient=group.created_by, verb=Notification.Verb.GROUP_REJECTED, actor=staff,
        message=f"Nhóm '{group.name}' bị từ chối: {reason}", content_object=group,
    )
    return group


def update_group_info(group: Group, name, description, logo=None, cover_image=None):
    group.name = name
    group.description = description
    if logo is False:
        group.logo = None
    elif logo is not None:
        group.logo = logo
    if cover_image is False:
        group.cover_image = None
    elif cover_image is not None:
        group.cover_image = cover_image
    group.save()
    return group


def disable_group(group: Group, staff, reason: str):
    """Giao vu Khoa huy kich hoat 1 nhom DANG hoat dong (khac voi tu choi yeu cau tao
    nhom - group nay da duoc duyet truoc do). Nhom bien mat khoi danh sach cong khai
    nhung du lieu (bai dang, thanh vien) van giu nguyen de co the kich hoat lai."""
    if not reason.strip():
        raise ValueError("Phải nhập lý do khi vô hiệu hóa nhóm.")
    group.status = Group.Status.DISABLED
    group.save(update_fields=["status"])
    log_action(actor=staff, action=ModerationLog.Action.DISABLE_GROUP, reason=reason, target_user=group.created_by, content_object=group)
    notify(
        recipient=group.created_by, verb=Notification.Verb.MODERATION, actor=staff,
        message=f"Nhóm '{group.name}' đã bị vô hiệu hóa. Lý do: {reason}", content_object=group,
    )
    return group


def enable_group(group: Group, staff):
    group.status = Group.Status.ACTIVE
    group.save(update_fields=["status"])
    log_action(actor=staff, action=ModerationLog.Action.ENABLE_GROUP, reason="Kích hoạt lại nhóm", target_user=group.created_by, content_object=group)
    notify(
        recipient=group.created_by, verb=Notification.Verb.MODERATION, actor=staff,
        message=f"Nhóm '{group.name}' đã được kích hoạt lại.", content_object=group,
    )
    return group


def add_member(group: Group, email: str):
    """Moi thanh vien - them thang vao nhom (khong qua buoc 'yeu cau cho duyet' rieng,
    don gian hoa so voi mo ta goc vi CLAUDE.md khong bat buoc luong duyet thanh vien)."""
    try:
        user = User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        raise ValueError("Không tìm thấy tài khoản với email này.")
    if GroupMembership.objects.filter(group=group, user=user).exists():
        raise ValueError("Người này đã là thành viên của nhóm.")
    membership = GroupMembership.objects.create(group=group, user=user, role=GroupMembership.Role.MEMBER)
    notify(
        recipient=user, verb=Notification.Verb.GROUP_APPROVED, actor=None,
        message=f"Bạn đã được thêm vào nhóm '{group.name}'.", content_object=group,
    )
    return membership


def remove_member(group: Group, target_user):
    membership = GroupMembership.objects.filter(group=group, user=target_user).first()
    if not membership:
        raise ValueError("Người này không phải thành viên của nhóm.")
    if membership.role == GroupMembership.Role.LEADER:
        raise ValueError("Không thể xóa trưởng nhóm. Hãy chuyển quyền trưởng nhóm trước.")
    membership.delete()


def change_member_role(group: Group, target_user, new_role: str):
    if new_role not in (GroupMembership.Role.MEMBER, GroupMembership.Role.MODERATOR):
        raise ValueError("Vai trò không hợp lệ.")
    membership = GroupMembership.objects.filter(group=group, user=target_user).first()
    if not membership:
        raise ValueError("Người này không phải thành viên của nhóm.")
    if membership.role == GroupMembership.Role.LEADER:
        raise ValueError("Không thể đổi vai trò của trưởng nhóm qua đây.")
    membership.role = new_role
    membership.save(update_fields=["role"])
    return membership


def leave_group(group: Group, user):
    membership = GroupMembership.objects.filter(group=group, user=user).first()
    if not membership:
        raise ValueError("Bạn không phải thành viên của nhóm.")
    if membership.role == GroupMembership.Role.LEADER:
        raise ValueError("Trưởng nhóm không thể tự rời nhóm. Hãy chuyển quyền trưởng nhóm trước.")
    membership.delete()


def create_group_post(group, author, title, body, featured_image=None):
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    status = ContentStatus.PENDING_REVIEW if keyword else ContentStatus.PUBLISHED
    post = GroupPost.objects.create(
        group=group, author=author, title=title, body=body, status=status, featured_image=featured_image
    )
    if keyword:
        log_action(actor=None, action="warn", reason=f"Tự động chuyển chờ kiểm duyệt do từ khóa: '{keyword.keyword}'", content_object=post)
    return post, keyword


def update_group_post(post: GroupPost, editor, title, body, featured_image=None):
    GroupPostEditHistory.objects.create(post=post, editor=editor, title=post.title, body=post.body)
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    post.title = title
    post.body = body
    if featured_image is False:
        post.featured_image = None
    elif featured_image is not None:
        post.featured_image = featured_image
    post.edit_count += 1
    if keyword:
        post.status = ContentStatus.PENDING_REVIEW
    post.save()
    if keyword:
        log_action(actor=None, action="warn", reason=f"Tự động chuyển chờ kiểm duyệt do từ khóa: '{keyword.keyword}'", content_object=post)
    return post, keyword
