import cv2
import mss
import win32api
import win32.lib.win32con as win32con

from cfg_utils import cfg
from path_utils import resource_path
from game_controller import game
from log_settings import logger
from type_declarations import CellState, CVMode, MatchState, PlayerState
from utils import thresholding, convert_contours_to_bboxes, sort_bboxes, cell_check, ask_file, write_to_cell, \
    clear_table, get_teams, extract_teams, calculate_score
import eel
import time
import threading
import numpy as np

### TODO:
# Возможность выбора цвета HUD
# Реализовать Template Matching с поддержкой ресайза для большей гибкости
# Возможность выгружать логи на какой-то фронт
#

recognized_success_cells = []
recognized_fail_cells = []
not_recognized_cells = []


def get_cells(image):
    binary_first_player_img = thresholding(image, 80, 255)
    contours, _ = cv2.findContours(binary_first_player_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bounding_boxes = convert_contours_to_bboxes(contours, 11, 11, 14, 14)
    bounding_boxes = sort_bboxes(bounding_boxes, method='left-to-right')
    cur_cells = []
    for i in range(0,len(bounding_boxes)):
        cell = cell_check(image[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4])
        if cell:
            cur_cells.append(cell)
            cell_color = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4]
            if cell == CellState.SUCCESS:
                recognized_success_cells.append(cell_color)
            else:
                recognized_fail_cells.append(cell_color)
        else:
            print(
                f"Неверная ячейка {i}. Цвет: {cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4]}")
            not_recognized_cells.append(
                cv2.cvtColor(image, cv2.COLOR_BGR2RGB)[bounding_boxes[i][1] + 5, bounding_boxes[i][0] + 4])
    return cur_cells


def log_cell_colors():
    sorted_success_cells = sorted({item[1]: item for item in recognized_success_cells}.values(),
                                  key=lambda cell: cell[1])
    sorted_fail_cells = sorted({item[0]: item for item in recognized_fail_cells}.values(), key=lambda cell: cell[0])
    logger.debug(
        f"После окончания сессии следующие цвета были распознаны как несоответствующие: {not_recognized_cells}")
    logger.debug(
        f"После окончания сессии следующие цвета были распознаны как корректные (SUCCESS): {sorted_success_cells}")
    logger.debug(
        f"После окончания сессии следующие цвета были распознаны как корректные (FAIL): {sorted_fail_cells}")
    not_recognized_cells.clear()
    recognized_fail_cells.clear()
    recognized_success_cells.clear()


stop_capture_event = threading.Event()
pause_capture_event = threading.Event()


@eel.expose
def start_series():
    player_names = extract_teams()
    game.start_series(player_names)
    stop_capture_event.clear()
    pause_capture_event.set()
    capturing_thread = threading.Thread(target=series_control, daemon=True)
    capturing_thread.start()



@eel.expose
def finish_series():
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
            pause_capture_event.wait()
            if stop_capture_event.is_set(): break
            start_time = time.time()
            monitor = sct.monitors[int(cfg['screen'])]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            check_screen(img)
            elapsed = time.time() - start_time
            time.sleep(max(0, (1 / cfg['fps'] - elapsed)))


def start_match():
    game.start_match()
    clear_table()
    screen_capture()


def check_screen(image):
    res_image = image[cfg['hudCoords'][0]['y']:cfg['hudCoords'][1]['y'],
                cfg['hudCoords'][0]['x']:cfg['hudCoords'][1]['x']]
    height, width, _ = res_image.shape
    match = game.get_current_match()
    if game.get_match_number() == game.start_match_number - 1: return
    first_player_image = res_image[0:int(height / 2), 0:width]
    first_player_cells = get_cells(first_player_image)

    second_player_image = res_image[int(height / 2):int(height), 0:width]
    second_player_cells = get_cells(second_player_image)

    kicks_stored = len(match['players'][0]['cells']) + len(match['players'][1]['cells'])
    kicks_detected = len(second_player_cells) + len(first_player_cells)
    kicks_made_in_turn = kicks_detected - kicks_stored

    if kicks_made_in_turn > 1:
        first_player_score = calculate_score(first_player_cells)
        second_player_score = calculate_score(second_player_cells)
        game.set_status(
            f"Матч {match['players'][0]['team']}-{match['players'][1]['team']} был восстановлен на результате: {first_player_score}:{second_player_score}.")
        game.set_status('История матча:')
    for i in range(kicks_stored, kicks_detected):
        current_kicks = second_player_cells if i % 2 else first_player_cells
        kick = current_kicks[len(match['players'][i % 2]['cells'])]
        game.commit_result(kick,i%2)
    if kicks_made_in_turn >1:
        game.set_status('Конец истории матча')

    if kicks_made_in_turn > 0:
        write_to_cell()
        logger.debug(f"Первый игрок: {first_player_cells}. Второй игрок: {second_player_cells}. Количество ударов за ход: {kicks_made_in_turn}. Количество ударов в памяти:{kicks_stored}. Количество ударов на экране:{kicks_detected}. Отправлена пауза - {bool(kicks_made_in_turn == 1)}")
        # Отправляем в vMix команду на таймер только если игра не завершена и не восстановлена (т.е. когда разница с прошлой картинкой - 1 удар, а не сессия восстановлена программно)
        if not game.check_game_end(cfg['max_kicks']) and game.window and kicks_made_in_turn == 1:
            time.sleep(2)
            win32api.SendMessage(game.window, win32con.WM_KEYDOWN, ord('Q'), 0)
            win32api.SendMessage(game.window, win32con.WM_KEYUP, ord('Q'), 0)

def manually_set_match_state(state:list[list[CellState]]):
    match = game.get_current_match()
    if not match or len(state) != 2: return
    if match['players'][0]['cells']==state[0] and match['players'][1]['cells']==state[1]:
        return
    game.set_status(f"Вручную выставлено следующее состояние текущего матча:")
    new_cell_amount = len(state[0])+len(state[1])
    game.clear_match()
    for i in range(0,new_cell_amount):
        current_cells = state[1] if i%2 else state[0]
        game.commit_result(current_cells.pop(0),i%2)
    write_to_cell()
    game.check_game_end(cfg['max_kicks'])


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

@eel.expose
def turn_mode(value,state:list[list[str]] = []):
    try:
        if CVMode(value) == CVMode.ON:
            game.set_status("Автоопределение результатов включено.")
            casted_cells = [[],[]]
            for i,row in enumerate(state):
                for cell in row:
                    casted_cells[i].append(CellState(cell))
            manually_set_match_state(casted_cells)
            pause_capture_event.set()
        if CVMode(value) == CVMode.OFF:
            game.set_status("Автоопределение результатов отключено.")
            pause_capture_event.clear()
    except ValueError as e:
        logger.exception("ValueError")




def main():
    eel.init(resource_path('ui'))
    eel.start('main.html', mode='edge', size=(540, 450), position=(100, 100))


if __name__ == "__main__":
    main()
