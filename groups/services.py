import csv
import io

from django.conf import settings
from django.utils import timezone

from accounts.models import User
from config.mixins import ContentStatus
from config.sanitize import sanitize_html
from moderation.services import find_sensitive_keyword, log_action
from moderation.models import ModerationLog
from notifications.models import Notification
from notifications.services import notify

from .models import Group, GroupInvitation, GroupJoinRequest, GroupMembership, GroupPost, GroupPostEditHistory


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


def _validate_school_email_domain(email: str):
    """Mail moi phai dung domain truong/khoa (giong rang buoc luc dang ky o accounts/forms.py)
    - bao loi ro rang thay vi de loi chung chung "khong tim thay tai khoan" khi nguoi dung
    dan nham email ngoai (vd gmail.com) vao danh sach moi hang loat."""
    allowed_domains = [d.lower() for d in getattr(settings, "ALLOWED_SIGNUP_EMAIL_DOMAINS", [])]
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if allowed_domains and domain not in allowed_domains:
        domains_text = ", ".join(f"@{d}" for d in allowed_domains)
        raise ValueError(f"Email không đúng domain trường/khoa ({domains_text}).")


def invite_member(group: Group, email: str, invited_by):
    """Leader/moderator moi 1 nguoi qua email - them thang vao nhom ngay (khong can
    buoc chap nhan/tu choi); GroupInvitation chi con vai tro luu lai nhat ky ai moi ai."""
    email = email.strip()
    _validate_school_email_domain(email)
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        raise ValueError("Không tìm thấy tài khoản với email này.")
    if GroupMembership.objects.filter(group=group, user=user).exists():
        raise ValueError("Người này đã là thành viên của nhóm.")
    invitation = GroupInvitation.objects.create(
        group=group, invited_user=user, invited_by=invited_by,
        status=GroupInvitation.Status.ACCEPTED, responded_at=timezone.now(),
    )
    GroupMembership.objects.create(group=group, user=user, role=GroupMembership.Role.MEMBER)
    notify(
        recipient=user, verb=Notification.Verb.GROUP_INVITATION, actor=invited_by,
        message=f"Bạn đã được thêm vào nhóm '{group.name}'.", content_object=group,
    )
    return invitation


def invite_members_bulk(group: Group, csv_file, invited_by):
    """Moi hang loat tu file CSV (moi dong 1 email o cot dau tien; dong dau co the la
    header "email" se tu dong bo qua). Khong dung lai khi gap dong loi - xu ly het cac
    dong con lai va tra ve bao cao (email da them thanh cong, email bi bo qua kem ly do)."""
    decoded = csv_file.read().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(decoded))
    added, skipped = [], []
    for row in reader:
        if not row:
            continue
        email = row[0].strip()
        if not email or email.lower() == "email":
            continue
        try:
            invite_member(group, email, invited_by)
        except ValueError as exc:
            skipped.append((email, str(exc)))
        else:
            added.append(email)
    return added, skipped


def request_to_join_group(group: Group, user, message: str = ""):
    """User tu xin vao nhom - cho leader/moderator duyet (nguoc chieu voi loi moi)."""
    if GroupMembership.objects.filter(group=group, user=user).exists():
        raise ValueError("Bạn đã là thành viên của nhóm này.")
    if GroupJoinRequest.objects.filter(group=group, user=user, status=GroupJoinRequest.Status.PENDING).exists():
        raise ValueError("Bạn đã gửi yêu cầu tham gia nhóm này, vui lòng chờ xét duyệt.")
    join_request = GroupJoinRequest.objects.create(group=group, user=user, message=message)
    for manager in User.objects.filter(
        group_memberships__group=group,
        group_memberships__role__in=[GroupMembership.Role.LEADER, GroupMembership.Role.MODERATOR],
    ):
        notify(
            recipient=manager, verb=Notification.Verb.GROUP_JOIN_REQUEST, actor=user,
            message=f"{user} xin tham gia nhóm '{group.name}'.", content_object=group,
        )
    return join_request


def approve_join_request(join_request: GroupJoinRequest, reviewer):
    if join_request.status != GroupJoinRequest.Status.PENDING:
        raise ValueError("Yêu cầu này đã được xử lý trước đó.")
    join_request.status = GroupJoinRequest.Status.ACCEPTED
    join_request.reviewed_by = reviewer
    join_request.reviewed_at = timezone.now()
    join_request.save()
    GroupMembership.objects.get_or_create(
        group=join_request.group, user=join_request.user, defaults={"role": GroupMembership.Role.MEMBER}
    )
    notify(
        recipient=join_request.user, verb=Notification.Verb.GROUP_JOIN_APPROVED, actor=reviewer,
        message=f"Yêu cầu tham gia nhóm '{join_request.group.name}' đã được chấp nhận.", content_object=join_request.group,
    )
    return join_request


def reject_join_request(join_request: GroupJoinRequest, reviewer, reason: str):
    if join_request.status != GroupJoinRequest.Status.PENDING:
        raise ValueError("Yêu cầu này đã được xử lý trước đó.")
    if not reason.strip():
        raise ValueError("Phải nhập lý do khi từ chối yêu cầu tham gia nhóm.")
    join_request.status = GroupJoinRequest.Status.REJECTED
    join_request.reviewed_by = reviewer
    join_request.reject_reason = reason
    join_request.reviewed_at = timezone.now()
    join_request.save()
    notify(
        recipient=join_request.user, verb=Notification.Verb.GROUP_JOIN_REJECTED, actor=reviewer,
        message=f"Yêu cầu tham gia nhóm '{join_request.group.name}' bị từ chối: {reason}", content_object=join_request.group,
    )
    return join_request


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


def transfer_leadership(group: Group, new_leader_user):
    """Chuyen quyen truong nhom cho 1 thanh vien khac - truong nhom cu xuong lam pho
    nhom (moderator), dam bao nhom luon co dung 1 truong nhom (nguoi tao nhom ban dau
    hoac nguoi ke nhiem), khong bao gio "mo coi" khong ai duyet bai viet cho duyet."""
    new_membership = GroupMembership.objects.filter(group=group, user=new_leader_user).first()
    if not new_membership:
        raise ValueError("Người được chỉ định phải là thành viên của nhóm.")
    if new_membership.role == GroupMembership.Role.LEADER:
        raise ValueError("Người này đã là trưởng nhóm.")
    old_leader_membership = group.memberships.filter(role=GroupMembership.Role.LEADER).first()
    if old_leader_membership:
        old_leader_membership.role = GroupMembership.Role.MODERATOR
        old_leader_membership.save(update_fields=["role"])
    new_membership.role = GroupMembership.Role.LEADER
    new_membership.save(update_fields=["role"])
    notify(
        recipient=new_leader_user, verb=Notification.Verb.GROUP_LEADERSHIP_TRANSFERRED,
        actor=old_leader_membership.user if old_leader_membership else None,
        message=f"Bạn đã trở thành trưởng nhóm '{group.name}'.", content_object=group,
    )
    return new_membership


def leave_group(group: Group, user):
    membership = GroupMembership.objects.filter(group=group, user=user).first()
    if not membership:
        raise ValueError("Bạn không phải thành viên của nhóm.")
    if membership.role == GroupMembership.Role.LEADER:
        # Nhom luon phai co nguoi lam truong nhom: neu co pho nhom thi tu dong len thay,
        # neu khong co pho nhom nao thi bat buoc phai chi dinh truoc (qua transfer_leadership)
        # - khong cho roi nhom khi chua co nguoi ke nhiem.
        successor = (
            group.memberships.filter(role=GroupMembership.Role.MODERATOR).order_by("joined_at").first()
        )
        if not successor:
            raise ValueError(
                "Bạn là trưởng nhóm duy nhất. Hãy chỉ định một thành viên khác làm trưởng nhóm trước khi rời nhóm."
            )
        transfer_leadership(group, successor.user)
    membership.delete()


def create_group_post(group, author, title, body, featured_image=None):
    """MOI bai viet trong nhom deu phai cho truong/pho nhom duyet (khac ForumPost/
    Announcement - chi cho duyet khi dinh tu khoa nhay cam). Van quet tu khoa de hien
    note do rieng cho truong/pho nhom biet bai nao dang nghi vi pham."""
    body = sanitize_html(body)
    keyword = find_sensitive_keyword(title, body)
    post = GroupPost.objects.create(
        group=group, author=author, title=title, body=body,
        status=ContentStatus.PENDING_REVIEW, featured_image=featured_image,
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
    post.status = ContentStatus.PENDING_REVIEW
    post.save()
    if keyword:
        log_action(actor=None, action="warn", reason=f"Tự động chuyển chờ kiểm duyệt do từ khóa: '{keyword.keyword}'", content_object=post)
    return post, keyword


def get_sensitive_keyword_note(post: GroupPost):
    """Kiem tra lai tren noi dung hien tai cua bai viet xem co dinh tu khoa nhay cam nao
    khong - hien thi note do cho truong/pho nhom biet ngay ten tu khoa, khong can doan mo."""
    keyword = find_sensitive_keyword(post.title, post.body)
    return keyword.keyword if keyword else ""


def approve_group_post(post: GroupPost, reviewer):
    """Truong nhom/pho nhom duyet bai viet cho kiem duyet trong NHOM CUA HO - khong qua
    Giao vu Khoa (pham vi noi bo nhom, khac voi ForumPost/Announcement)."""
    post.status = ContentStatus.PUBLISHED
    post.save(update_fields=["status"])
    log_action(actor=reviewer, action=ModerationLog.Action.APPROVE_CONTENT, reason="Duyệt bài viết nhóm chờ kiểm duyệt", content_object=post)
    notify(
        recipient=post.author, verb=Notification.Verb.MODERATION, actor=reviewer,
        message="Bài viết của bạn trong nhóm đã được duyệt và đăng.", content_object=post,
    )
    return post


def reject_group_post(post: GroupPost, reviewer, reason: str):
    if not reason.strip():
        raise ValueError("Phải nhập lý do khi từ chối bài viết.")
    post.status = ContentStatus.REMOVED
    post.save(update_fields=["status"])
    log_action(actor=reviewer, action=ModerationLog.Action.REJECT_CONTENT, reason=reason, content_object=post)
    notify(
        recipient=post.author, verb=Notification.Verb.MODERATION, actor=reviewer,
        message=f"Bài viết của bạn trong nhóm đã bị từ chối. Lý do: {reason}", content_object=post,
    )
    return post
