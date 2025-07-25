from datetime import datetime

import eel
import pytz
import logging
import os
from path_utils import get_executable_path

def timetz(*args):
    return datetime.now(pytz.timezone('Europe/Moscow')).timetuple()

current_datetime = datetime.now()
current_time = current_datetime.strftime("%d-%m-%Y-%H-%M")

log_filename = f"{current_time}"

def get_log_path(log_level):
    return os.path.join(get_executable_path(), 'logs', f"{log_filename}-{log_level}.log")

logging.Formatter.converter = timetz
logger_format = '%(asctime)s - %(levelname)s - %(message)s'


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

os.makedirs("logs", exist_ok=True)

# if getattr(sys,'frozen', True):
debug_handler = logging.FileHandler(get_log_path('debug'),encoding='utf-8')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(logging.Formatter(logger_format))
debug_handler.encoding = 'utf-8'
logger.addHandler(debug_handler)

info_handler = logging.FileHandler(get_log_path('info'),encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_formatter = logging.Formatter(logger_format)
info_formatter.converter = timetz
info_handler.setFormatter(info_formatter)
info_handler.encoding='utf-8'

logger.addHandler(info_handler)

@eel.expose
def open_history():
    os.startfile(get_log_path('info'),'open')
