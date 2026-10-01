#!/usr/bin/env python
import os
import sys


def principal():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agromonitor.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    principal()
