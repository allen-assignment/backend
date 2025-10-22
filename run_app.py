import os
import sys

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dish_order_backend.settings")
    execute_from_command_line([sys.argv[0], "runserver", "0.0.0.0:8000"])