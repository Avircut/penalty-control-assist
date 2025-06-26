import os
import sys

# Получить путь относительно temp директории (после сборки)
def resource_path(relative_path):
    if hasattr(sys,'_MEIPASS'):
        return os.path.join(sys._MEIPASS,relative_path)
    return os.path.join(os.path.abspath('.'),relative_path)

# После сборки тут будет фактическая директория исполняемого файла. Нужно только для расположения логов и конфига
def get_executable_path(file_name:str=''):
    if getattr(sys,'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), file_name)
    else:
        return os.path.join(os.path.dirname(__file__), file_name)
