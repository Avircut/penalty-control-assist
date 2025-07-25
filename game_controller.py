import win32gui

from log_settings import logger
from type_declarations import MatchState, CellState, SeriesState, MatchResult

'''
Series - это текущая серия матчей. Там хранится базовая информация об игроках (включая ники, команды и счет по серии), а также текущие матчи
file_path, window - это значения из конфига. Путь до файла с таблицей и окно для отправки туда хоткеев
status - Сообщение, которое отображается в UI и также записывается в логи
start_match_number - номер первого матча в серии. Массив матчей всё также начинается 0, это чисто UI смещение, от этого номера зависит положение команд (они каждый матч меняются местами)
'''
class GameController:
    series: SeriesState
    file_path: str
    window: str
    status: str | None
    start_match_number: int

    def __init__(self):
        self.series = {
            'players': [],
            'matches': []
        }
        self.file_path = ''
        self.window = win32gui.FindWindow(None, 'vMix 4K - 28.0.0.39 x64 - UPL_STARS.vmix')
        self.status = None
        self.start_match_number = 1

    def clear_series(self):
        self.series = {
            'players': [],
            'matches': []
        }

    # Получить текущий номер матча
    def get_match_number(self):
        return len(self.series['matches']) + self.start_match_number - 1

    # Получить текущий матч
    def get_current_match(self):
        if len(self.series['matches']) < 1: return None
        return self.series['matches'][-1]

    def clear_match(self):
        match = self.get_current_match()
        if match:
            for i in range(0, len(match['players'])):
                match['players'][i]['score'] = 0
                match['players'][i]['cells'] = []
            match['isGameOver'] = False

    # Старт матча - подготовка состояния
    def start_match(self):
        is_odd = self.get_match_number() % 2
        teams = []
        for i in range(0, len(self.series['players'])):
            teams.append(self.series['players'][i]['team'])
        if is_odd: teams.reverse()
        if not len(teams): teams = ['TBA', 'TBA']
        new_match: MatchState = {
            'players': [{'team': teams[0], 'score': 0, 'cells': []},
                        {'team': teams[1], 'score': 0, 'cells': []}],
            'isGameOver': False
        }
        player_names = [self.get_match_player_name(new_match['players'][0]['team']), self.get_match_player_name(new_match['players'][1]['team'])]
        self.series['matches'].append(new_match)
        self.set_status(f"Старт матча - {new_match['players'][0]['team']} ({player_names[0]}) vs {new_match['players'][1]['team']} ({player_names[1]})")

    # Зачисление результата удара
    def commit_result(self, result: CellState, player_index: int):
        match = self.get_current_match()
        if not match: return
        if result == CellState.SUCCESS:
            match['players'][player_index]['score'] += 1
        match['players'][player_index]['cells'].append(result)
        team = self.get_current_teams()[player_index]
        player_name = self.get_match_player_name(team)
        result = 'Забит' if result == CellState.SUCCESS else 'Отбит'
        game.set_status(
            f"Игрок {team}({player_name}) завершил удар. Результат: {result}. Счет: {match['players'][0]['score']}:{match['players'][1]['score']}.")

    # Получение имени игрока по названию команды (берется из серии, т.к. в каждом матче игроки меняются местами)
    def get_match_player_name(self, team:str):
        return [player for player in self.series['players'] if player['team'] == team][0]['name']

    # Проверка игры на завершенность
    def check_game_end(self, max_kicks: int = 5):
        match = self.get_current_match()
        if match:
            first_player_won = (match['players'][0]['score'] > match['players'][1]['score'] + (
                    max_kicks - len(match['players'][1]['cells'])))
            second_player_won = match['players'][1]['score'] > match['players'][0]['score'] + (
                    max_kicks - len(match['players'][0]['cells']))
            win_condition = first_player_won or second_player_won
            draw_condition = (len(match['players'][0]['cells']) == len(match['players'][1]['cells'])) and (
                    len(match['players'][0]['cells']) == max_kicks)
            if win_condition or draw_condition:
                match_result = MatchResult.FIRST_PLAYER if first_player_won else MatchResult.SECOND_PLAYER if second_player_won else MatchResult.DRAW
                self.finish_match(match_result)
            return win_condition or draw_condition
        return False

    # Завершение матча и отправка соответствующего сообщения в лог
    def finish_match(self, match_result: MatchResult):
        match = self.get_current_match()
        if match:
            match['isGameOver'] = True
            winner_message = ''
            if match_result.value >= 0:
                player_index = match_result.value
                series_player = None
                for i, player in enumerate(self.series['players']):
                    if player['team'] == match['players'][player_index]['team']:
                        series_player = player
                        break
                if series_player:
                    series_player['score'] += 1
                    winner_message = f"Победитель: {match['players'][player_index]['team']} ({series_player['name']})"
            if match_result == MatchResult.DRAW:
                winner_message = 'Ничья'
            match_suspended_message = " досрочно" if match_result == MatchResult.SUSPENDED else ''
            self.set_status(
                f"Матч завершен{match_suspended_message}. Результат: {match['players'][0]['team']} {match['players'][0]['score']}:{match['players'][1]['score']} {match['players'][1]['team']} Удары: {match['players'][0]['team']} {len(match['players'][0]['cells'])}:{len(match['players'][1]['cells'])} {match['players'][1]['team']}. {winner_message}")

    # Начало новой серии и подготовка состояния
    def start_series(self, player_names: list[str]):
        self.series['matches'] = []
        self.series['players'] = []
        if len(player_names) < 2: logger.warning('Серия не получила достаточного количества игроков')
        for i in range(0, len(player_names)):
            self.series['players'].append({
                'team': player_names[i].split(' ')[0],
                'name': player_names[i].split(' ')[1][1: -1],
                'score': 0
            })
        names = self.get_player_names()
        if self.start_match_number == 1:
            self.set_status(f"Старт серии - {names[0]} vs {names[1]}")
        else:
            self.set_status(
                f"Серия между {names[0]} vs {names[1]} восстановлена с {self.start_match_number} матча.")

    # Преждевременная остановка серии
    def stop_series(self):
        self.finish_match(MatchResult.SUSPENDED)
        names = self.get_player_names()
        self.set_status(
            f"Серия {names[0]} vs {names[1]} завершена досрочно на результате: {self.series['players'][0]['score']}:{self.series['players'][1]['score']}.")
        self.clear_series()

    # Флаг идет ли в данный момент серия
    def series_in_progress(self):
        return len(self.series['players']) > 0

    # Закономерное окончание серии и очистка состояния
    def finish_series(self):
        if self.series_in_progress():
            names = self.get_player_names()
            self.set_status(
                f"Серия {names[0]} vs {names[1]} завершена на результате: {self.series['players'][0]['score']}:{self.series['players'][1]['score']}.")
            self.clear_series()

    def set_file(self, file_path: str):
        self.file_path = file_path

    def set_window(self, window: str):
        self.window = window

    # Статус отображается на фронте и отправляется в логи. По сути - текущее состояние приложения
    def set_status(self, status: str | None):
        logger.info(status)
        self.status = status

    def set_start_match_number(self, number: int):
        self.start_match_number = number

    # Получение массива команд текущего матча
    def get_current_teams(self):
        match = self.get_current_match()
        teams = []
        if not match: return None
        if len(match['players']) == 2:
            for i in range(0, len(match['players'])):
                teams.append(match['players'][i]['team'])
        return teams

    # Получение готовых для отправки пар команда - ник по типу 'JUV (NickName)'
    def get_player_names(self):
        if len(self.series['players']) <2:
            return None
        return list(f"{x['team']} ({x['name']})" for x in self.series['players'])



game = GameController()
