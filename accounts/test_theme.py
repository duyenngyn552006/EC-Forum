"""Test khung che do sang/toi o base.html (phan hien thi; logic chuyen doi chay bang JS phia trinh duyet)."""
from django.test import TestCase
from django.urls import reverse


class ThemeToggleTests(TestCase):
    def test_theme_is_set_before_render_and_toggle_present(self):
        response = self.client.get(reverse("home"))
        html = response.content.decode()
        # Script dat data-theme phai nam trong <head>, truoc CSS -> khong nhay trang khi tai trang o che do toi
        head = html[: html.index("</head>")]
        self.assertIn("localStorage.getItem('ecforum-theme')", head)
        self.assertLess(head.index("setAttribute('data-theme'"), head.index("<style>"))
        self.assertContains(response, 'id="themeToggle"')
        self.assertContains(response, 'aria-pressed="false"')
        self.assertContains(response, 'html[data-theme="dark"] body')
