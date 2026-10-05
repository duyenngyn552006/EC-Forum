from django.contrib import admin

from .models import Notification, NotificationPreference

admin.site.register(Notification)
admin.site.register(NotificationPreference)
