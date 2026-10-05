#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _force_utf8_console():
    # Console Windows mac dinh dung code page ANSI (vd cp1252), khong encode duoc
    # tieng Viet co dau -> crash UnicodeEncodeError khi runserver in log/email ra
    # console. Ep stdout/stderr sang UTF-8 de tranh loi nay tren moi may Windows.
    if sys.platform == "win32":
        for stream_name in ("stdout", "stderr"):
            stream = getattr(sys, stream_name)
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")


def main():
    """Run administrative tasks."""
    _force_utf8_console()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
