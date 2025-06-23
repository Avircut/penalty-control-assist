import cv2
import mss
import win32api
import win32.lib.win32con as win32con

from cfg_utils import cfg
from path_utils import resource_path
from game_controller import game
from log_settings import logger
from type_declarations import CellState
from utils import thresholding, convert_contours_to_bboxes, sort_bboxes, cell_check, ask_file, write_to_cell, \
    clear_match_info, get_teams, extract_teams
import eel
import time
import threading
import numpy as np

### TODO:
# Фикс чтобы все промежуточные удары тоже прописывались в лог, а не только последний (сравнивать текущий cells и озвучивать все отличия)
# Возможность менять вручную данные (клик на квадратик)
# Возможность выбора цвета HUD
# Реализовать Template Matching с поддержкой ресайза для большей гибкости
# Поддержка импорта расписания
# Возможность выгружать логи на какой-то фронт
#

recognized_success_cells = []
recognized_fail_cells=[]
not_recognized_cells = []


def get_score(image):
    binary_first_player_img = thresholding(image, 80, 255)
    contours, _ = cv2.findContours(binary_first_player_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bounding_boxes = convert_contours_to_bboxes(contours, 11, 11,14,14)
    bounding_boxes = sort_bboxes(bounding_boxes, method='left-to-right')
    cur_score = 0
    cur_cells = []
    for i in range(0, len(bounding_boxes)):
        cell = cell_check(image[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4])
        if cell == CellState.SUCCESS: cur_score += 1
        if cell:
            cur_cells.append(cell)
            cell_color = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4]
            if cell == CellState.SUCCESS:
                recognized_success_cells.append(cell_color)
            else:
                recognized_fail_cells.append(cell_color)
            # logger.debug(f'Ячейка распознана. Цвет: {cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4]}')
        else:
            print(
                f"Неверная ячейка {i}. Цвет: {cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4]}")
            # logger.debug(f"Неверная ячейка {i}. Цвет: {cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4]}")
            not_recognized_cells.append(
                cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4])

    return [cur_score, cur_cells]


def log_cell_colors():
    sorted_success_cells = sorted({item[1]: item for item in recognized_success_cells}.values(),key=lambda cell: cell[1])
    sorted_fail_cells = sorted({item[0]: item for item in recognized_fail_cells}.values(),key=lambda cell: cell[0])
    logger.debug(
        f"После окончания сессии следующие цвета были распознаны как несоответствующие: {not_recognized_cells}")
    logger.debug(
        f"После окончания сессии следующие цвета были распознаны как корректные (SUCCESS): {sorted_success_cells}")
    logger.debug(
        f"После окончания сессии следующие цвета были распознаны как корректные (FAIL): {sorted_fail_cells}")
    not_recognized_cells.clear()
    recognized_fail_cells.clear()
    recognized_success_cells.clear()


@eel.expose
def start_series(log_series_start:bool):
    player_names = extract_teams()
    game.start_series(player_names, log_series_start)
    stop_capture_event.clear()
    capturing_thread.start()


@eel.expose
def finish_series():
    clear_match_info()
    game.stop_series()
    stop_capture_event.set()
    log_cell_colors()


def series_control():
    while not stop_capture_event.is_set():
        while game.get_match_number() < cfg['matches_in_series'] and game.series_in_progress():
            start_match()
        stop_capture_event.set()
    game.finish_series()
    log_cell_colors()



def screen_capture():
    match = game.get_current_match()
    if not match: return
    with mss.mss() as sct:
        while not match['isGameOver']:
            if stop_capture_event.is_set(): break
            start_time = time.time()
            monitor = sct.monitors[int(cfg['screen'])]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            check_screen(img)
            elapsed = time.time() - start_time
            time.sleep(max(0, (1 / cfg['fps'] - elapsed)))


capturing_thread = threading.Thread(target=series_control, daemon=True)
stop_capture_event = threading.Event()


def start_match():
    game.start_match()
    clear_match_info()
    screen_capture()


def check_screen(image):
    res_image = image[cfg['hudCoords'][0]['y']:cfg['hudCoords'][1]['y'],
                cfg['hudCoords'][0]['x']:cfg['hudCoords'][1]['x']]
    match = game.get_current_match()
    if game.get_match_number() == 0: return
    first_player_image = res_image[0:18, 0:100]
    first_player_score, first_player_kicks = get_score(first_player_image)

    second_player_image = res_image[21:40, 0:100]
    second_player_score, second_player_kicks = get_score(second_player_image)

    first_player_kicked = len(first_player_kicks) > len(match['players'][0]['cells'])
    second_player_kicked = len(second_player_kicks) > len(match['players'][1]['cells'])
    first_player_scored = first_player_score > match['players'][0]['score']
    second_player_scored = second_player_score > match['players'][1]['score']
    if first_player_kicked:
        game.set_player_state(0, first_player_score, first_player_kicks)
    if second_player_kicked:
        game.set_player_state(1, second_player_score, second_player_kicks)
    if first_player_kicked or second_player_kicked:
        write_to_cell()
        team = game.get_current_teams()[0] if first_player_kicked else game.get_current_teams()[1]
        result = 'Успешно' if first_player_scored or second_player_scored else 'Промах'
        game.set_status(
            f"Команда {team} завершила удар. Результат: {result}. Счет: {first_player_score}:{second_player_score}.")
        if not game.check_game_end(cfg['max_kicks']) and game.window:
            if (len(match['players'][0]['cells']) > 0) and (
                    len(match['players'][1]['cells']) > 0):  # Иногда почему-то в начале таймер вызывается.
                time.sleep(2)
                win32api.SendMessage(game.window, win32con.WM_KEYDOWN, ord('Q'), 0)
                win32api.SendMessage(game.window, win32con.WM_KEYUP, ord('Q'), 0)


@eel.expose
def get_state():
    teams = get_teams()
    match = game.get_current_match()
    status = game.status
    stop_series = not game.series_in_progress()
    first_player_cells = [x.value for x in match['players'][0]['cells']] if match else []
    second_player_cells = [x.value for x in match['players'][1]['cells']] if match else []
    res = [game.get_match_number(), status, stop_series, teams, first_player_cells, second_player_cells]
    return res


def main():
    eel.init(resource_path('ui'))
    eel.start('main.html', mode='edge', size=(540, 420), position=(100, 100))


if __name__ == "__main__":
    main()
