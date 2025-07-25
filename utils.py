import traceback

import mss
import pythoncom
import win32com.client

from cfg_utils import save_config, cfg
from log_settings import logger

import cv2
import eel
from tkinter import Tk, filedialog, messagebox
import os
import numpy as np
import screeninfo
import win32gui

from game_controller import game
import pandas as pd

from type_declarations import CellState


# Функция для перевода изображение в бинарный вид (черно-белый)
def thresholding(img, value_1, value_2):
    """
    Parameters:
        img(numpy.ndarray): image of a part of the table
        value_1(int): threshold value
        value_2(int): the maximum value that is assigned
        to pixel values that exceed the threshold value
    Returns: binary_img(numpy.ndarray)
    """
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary_img = cv2.threshold(img, value_1, value_2, cv2.THRESH_BINARY)
    return binary_img

# Функция конвертирует дефолтные контуры cv2 в более удобный формат, а также удаляет внутренние границы
def convert_contours_to_bboxes(contours, min_height, min_width, max_height, max_width):
    """
    convert contours to bboxes, also remove all small bounding boxes
    Parameters:
        contours (tuple): each individual contour is a numpy array
         of (x, y) coordinates of boundary points of the object
        contours(list of tuples of int): bounding boxes suits
        and values (J, K etc.) in [x, y, w, h] format
    Returns:
        cards_bboxes(list of lists of int): bounding boxes suits
        and values (J, K etc.) in [x_0, y_0, x_1, y_1] format
    """
    bboxes = [cv2.boundingRect(contour) for contour in contours]
    cards_bboxes = []
    for i in range(0, len(bboxes)):
        x, y, w, h = bboxes[i][0], bboxes[i][1], \
            bboxes[i][2], bboxes[i][3]
        if max_height >= h >= min_height and max_width >= w >= min_width:
            contour_coordinates = [x - 1, y - 1, x + w + 1, y + h + 1]
            cards_bboxes.append(contour_coordinates)
    return cards_bboxes

# Сортирует распознанные границы в указанном порядке
def sort_bboxes(bounding_boxes, method: str):
    """
    Parameters:
         bounding_boxes(list of lists of int): bounding_boxes in [x_0, y_0, x_1, y_1] format
         method(int): the method of sorting bounding boxes.
         It can be left-to-right, bottom-to-top or top-to-bottom
    Returns:
        bounding_boxes (list of tuple of int): sorted bounding boxes.
        Each bounding box presented in [x_0, y_0, x_1, y_1] format
    """

    methods = ['left-to-right', 'bottom-to-top', 'top-to-bottom']
    if method not in methods:
        raise ValueError("Invalid method. Expected one of: %s" % methods)

    else:

        if method == 'left-to-right':
            bounding_boxes.sort(key=lambda tup: tup[0])

        elif method == 'bottom-to-top':
            bounding_boxes.sort(key=lambda tup: tup[1], reverse=True)

        elif method == 'top-to-bottom':
            bounding_boxes.sort(key=lambda tup: tup[1], reverse=False)
        return bounding_boxes


# Определение типа ячейки идет посредством сравнения одного пикселя внутри с цветовыми диапазонами
def cell_check(color: tuple[int, int, int]):
    """
    :param color: BGR color representation
    :return: CellState
    """
    # 150 100 100
    # 100 120 100
    if color[2] > 210 and color[1] <= 90 and color[0] < 80:
        return CellState.FAIL
    elif color[2] <= 55 and color[1] > 120 and color[0] < 110:
        return CellState.SUCCESS
    return None


# Очистка таблицы от данных по прошлому матчу (и смена команд местами для следующего матча)
def clear_table():
    teams = get_teams()
    # Отдельно храним teams и данные пенальти, чтобы не перебивать score столбец(чтобы не удалять формулу оттуда и в крайнем случае можно было вручную заполнять таблицу)
    team_data = {'TEAM': teams}
    data = {}
    for i in range(1, 6):
        data[f"PEN{i}"] = ['', '']
    team_df = pd.DataFrame(team_data)
    df = pd.DataFrame.from_dict(data, orient='index')
    df = df.transpose()
    with pd.ExcelWriter(game.file_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        sheet_name = 'STATS'
        team_df.to_excel(writer, sheet_name=sheet_name, startrow=0, index=False, startcol=1)
        df.to_excel(writer, sheet_name=sheet_name, startrow=0, index=False, startcol=3)
    refresh_table()

# По массиву клеток определение результата игрока
def calculate_score(cells: list[CellState]):
    cur_score = 0
    for cell in cells:
        if cell == CellState.SUCCESS: cur_score += 1
    return cur_score

# Получение игроков и их команд из таблицы. Данные берутся из столбца HOMEAWAY (1 столбец) 2 и 3 строки
def extract_teams():
    file = pd.read_excel(game.file_path, usecols='A', skiprows=1, nrows=2, header=None)
    file_content = file.to_numpy()
    teams = file_content.flatten()
    if len(teams) < 2: logger.debug(
        f"Из таблицы получено недостаточное количество элементов: {len(teams)}. {' '.join([x for x in teams])}")
    return teams

# Отправка сообщения об ошибке на фронте
@eel.expose
def show_message(text):
    if text:
        messagebox.showerror("Произошла ошибка", text)

# Получение команд текущего матча
def get_teams():
    return game.get_current_teams()

# Запуск проверки выбранного экрана (отображается зеленая рамка в области, где программа будет искать худ для отслеживания
@eel.expose
def check_cv():
    with mss.mss() as sct:
        monitor = sct.monitors[int(cfg['screen'])]
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        cv2.rectangle(img, (cfg['hudCoords'][0]['x'], cfg['hudCoords'][0]['y']),
                      (cfg['hudCoords'][1]['x'], cfg['hudCoords'][1]['y']), (0, 255, 0), 2)
        cv2.imshow("Экран с ожидаемым местом для игрового HUD", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

# Функция нужна, чтобы обновить файл и подготовить его для обработки vMix
def refresh_table():
    xlapp = win32com.client.DispatchEx("Excel.Application",pythoncom.CoInitialize())
    wb = xlapp.Workbooks.Open(game.file_path)
    wb.RefreshAll()
    xlapp.CalculateUntilAsyncQueriesDone()
    wb.Save()
    # time.sleep(1)
    xlapp.Quit()

# Рудимент функция - раньше использовался pandas для сохранения результатов в excel. Из-за того, что без рефреша формул vMix не видел корректно данные пришлось уйти от этого варианта в сторону решения на чистом pywin32.
# Deprecated
def write_to_cell():
    teams = get_teams()
    match = game.get_current_match()
    if match:
        team_data = {'TEAM': teams}
        data = {}
        for i in range(0, len(match['players'][0]['cells'])):
            data[f"PEN{i + 1}"] = [match['players'][0]['cells'][i].value] if len(
                match['players'][1]['cells']) < i + 1 else [
                match['players'][0]['cells'][i].value, match['players'][1]['cells'][i].value]
        try:
            team_df = pd.DataFrame(team_data)
            df = pd.DataFrame.from_dict(data, orient='index')
            df = df.transpose()
            with pd.ExcelWriter(game.file_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                sheet_name = 'STATS'
                team_df.to_excel(writer, sheet_name=sheet_name, startrow=0, index=False, startcol=1)
                df.to_excel(writer, sheet_name=sheet_name, startrow=0, index=False, startcol=3)
            refresh_table()
        except Exception as e:
            logger.error(traceback.format_exc())
            messagebox.showerror('Произошла ошибка при записи файла',
                             'Не удалось записать в файл результаты удара. Проверьте, что не блокируете файл другими программами')

# Функция напрямую через win api меняет значения в таблице и обновляет формулы. Используется именно win api (а не pandas), чтобы было всего одно сохранение и данные в vMix не менялись постоянно
def write_to_excel():
    match = game.get_current_match()
    if not match: return
    player_names = game.get_player_names()
    teams = game.get_current_teams()
    # Были проблемы с сохранением/перерасчетом формул, поэтому не меняем их, просто оставляем дефолтные формулы в этих ячейках
    # score = f'=IF(D2="+",1,0)+IF(E2="+",1,0) + IF(F2="+",1,0) + IF(G2="+",1,0) + IF(H2="+",1,0)'
    # score2 = f'=IF(D3="+",1,0)+IF(E3="+",1,0) + IF(F3="+",1,0) + IF(G3="+",1,0) + IF(H3="+",1,0)'
    data = {'TEAMS':teams}
    for i in range(0, len(match['players'][0]['cells'])):
        data[f"PEN{i + 1}"] = [match['players'][0]['cells'][i].value] if len(
            match['players'][1]['cells']) < i + 1 else [
            match['players'][0]['cells'][i].value, match['players'][1]['cells'][i].value]
    df = pd.DataFrame.from_dict(data, orient='index')
    values = df.transpose().values.tolist()

    xlapp = win32com.client.DispatchEx("Excel.Application",pythoncom.CoInitialize())
    wb = xlapp.Workbooks.Open(game.file_path)
    sheet = wb.Sheets('STATS')

    try:
        for idx,line in enumerate(values):
            team,*pens = line
            # sheet.Range(f"A{idx+2}").Value = player_name
            sheet.Range(f"B{idx+2}").Value = team
            for pen_number,pen in enumerate(pens):
                column_liter = ['D','E','F','G','H']
                sheet.Range(f"{column_liter[pen_number]}{idx+2}").Value = pen
        wb.RefreshAll()
        xlapp.CalculateUntilAsyncQueriesDone()
        wb.Save()
    except Exception as e:
        logger.error(traceback.format_exc())
        messagebox.showerror('Произошла ошибка при записи файла',
                             'Не удалось записать в файл результаты удара. Проверьте, что не блокируете файл другими программами')
        print(f"An error occurred: {e}")

    finally:
        # Ensure Excel application is closed
        if 'wb' in locals() and wb:
            wb.Close(SaveChanges=False) # Don't save if an error occurred
        if 'xlapp' in locals() and xlapp:
            xlapp.Quit()

# Проверка корректную ли таблицу мы выбрали по заголовкам
def check_table_structure(file_path):
    correct_structure = np.array(['TEAM', 'SCORE', 'PEN1', 'PEN2', 'PEN3', 'PEN4', 'PEN5'])
    try:
        file = pd.read_excel(file_path, usecols='B:H', nrows=1, header=None)
        file_content = file.to_numpy()
        is_struct_correct = np.array_equal(correct_structure, file_content[0])
        if not is_struct_correct:
            messagebox.showerror("Произошла ошибка",
                                 "Некорректная структура таблицы, проверьте чтобы в первой строке в столбцах B:H были корректные заголовки от 'TEAM' до 'PEN5'")
            logger.error(
                'Не удалось загрузить таблицу, так как структура таблицы нарушена. Проверьте заголовки в столбцах B:H')
        else:
            return is_struct_correct
    except FileNotFoundError:
        messagebox.showerror("Произошла ошибка",
                             "Файл не найден. Возможно выбран ярлык несуществующего файла. Попробуйте выбрать другой файл")
        logger.exception('FileNotFoundError')
    return False

# Проверка прав в выбранном файле
@eel.expose
def check_file_permission():
    try:
        with open(game.file_path, 'a') as f:
            return True
    except IOError as e:
        messagebox.showerror("Произошла ошибка при открытии файла.",
                             f"Пожалуйста, убедитесь, что вы закрыли файл с таблицей в Excel. Ошибка: {e}")
        return False
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при проверке файла на доступные права")
        return False

# Показ диалогового окна для выбора файла (на фронте сделать такое нельзя, т.к. там не хранится полный путь файла)
@eel.expose
def ask_file():
    root = Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    file_path = filedialog.askopenfilename(title='Выберите файл таблицы',
                                           filetypes=[("XLSX Таблицы", "*.xlsx"), ("XLS Таблицы", "*.xls")])
    if file_path:
        if (os.path.exists(file_path)) and (os.access(file_path, os.R_OK)) and os.access(file_path, os.W_OK):
            if check_table_structure(file_path):
                game.set_file(file_path)
                save_config({'file_path': file_path})
                return file_path
        else:
            messagebox.showerror("Произошла ошибка",
                                 "Файл недоступен. Либо он не найден, либо недостаточно прав. Попробуйте закрыть этот файл в других программах или переместите его в другую папку.")
            logger.error(f"Не удалось загрузить файл: {file_path}. Он не найден, либо недостаточно прав.")
    return None

# Отдает на фронт список всех окон у пользователя на выбор
@eel.expose
def get_windows():
    """Возвращает список видимых окон (название + HWND)."""
    windows = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:  # Игнорируем окна без названия
                windows.append([title, hwnd])
        return True

    win32gui.EnumWindows(callback, None)
    return windows

# Отдает на фронт список всех мониторов на выбор
@eel.expose
def get_monitors():
    monitors = []

    for i, m in enumerate(screeninfo.get_monitors()):
        monitors.append({
            'id': i,
            'width': m.width,
            'height': m.height,
            'name': f"Монитор {i + 1}",
            'is_primary': m.is_primary
        })

    return monitors


@eel.expose
def set_window(hwnd: str):
    game.set_window(hwnd)


@eel.expose
def set_screen(screen_index):
    save_config({'screen': screen_index})


@eel.expose
def set_matches_in_series(amount):
    print(amount)
    save_config({'matches_in_series': amount})


@eel.expose
def set_match_start_number(number):
    game.set_start_match_number(int(number))
