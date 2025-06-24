import time

import win32gui

from log_settings import logger
from type_declarations import MatchState, CellState, SeriesState


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

    def get_match_number(self):
        return len(self.series['matches']) + self.start_match_number - 1

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

    def finish_match(self, player_index: int):
        match = self.get_current_match()
        if match:
            match['isGameOver'] = True
            if player_index != -1:
                series_player = None
                for i, player in enumerate(self.series['players']):
                    if player['team'] == match['players'][player_index]['team']:
                        series_player = player
                        break
                series_player['score'] += 1
            winner_message = f"Победитель: {match['players'][player_index]['team']}" if player_index != -1 else 'Ничья'
            self.set_status(
                f"Матч завершен. Результат: {match['players'][0]['team']} {match['players'][0]['score']}:{match['players'][1]['score']} {match['players'][1]['team']}. {winner_message}")

    def set_player_state(self, player: int, score: int, cells: list[CellState]):
        match = self.get_current_match()
        if match:
            match['players'][player]['score'] = score
            match['players'][player]['cells'] = cells

    def commit_result(self,result:CellState,player_index:int):
        match = self.get_current_match()
        if not match: return
        if result == CellState.SUCCESS:
            match['players'][player_index]['score'] += 1
        match['players'][player_index]['cells'].append(result)
        team = game.get_current_teams()[player_index]
        result = 'Успешно' if result == CellState.SUCCESS else 'Промах'
        game.set_status(
            f"Команда {team} завершила удар. Результат: {result}. Счет: {match['players'][0]['score']}:{match['players'][1]['score']}.")

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
                player_won_index = 0 if first_player_won else 1 if second_player_won else -1
                self.finish_match(player_won_index)
            return win_condition or draw_condition
        return False

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
        self.series['matches'].append(new_match)
        self.set_status(f"Старт матча - {new_match['players'][0]['team']}-{new_match['players'][1]['team']}")

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
        if self.start_match_number == 1:
            self.set_status(f"Старт серии - {player_names[0]}-{player_names[1]}")
        else: self.set_status(f"Серия между {player_names[0]} и {player_names[1]} восстановлена с {self.start_match_number} матча.")

    def stop_series(self):
        self.finish_match(-1)
        self.set_status(
            f"Серия между {self.series['players'][0]['name']} и {self.series['players'][1]['name']} завершена досрочно на результате: {self.series['players'][0]['score']}:{self.series['players'][1]['score']}.")
        self.clear_series()

    def series_in_progress(self):
        return len(self.series['players']) > 0

    def finish_series(self):
        if self.series_in_progress():
            self.set_status(
                f"Серия между {self.series['players'][0]['name']} и {self.series['players'][1]['name']} завершена на результате: {self.series['players'][0]['score']}:{self.series['players'][1]['score']}.")
            self.clear_series()

    def set_file(self, file_path: str):
        self.file_path = file_path

    def set_window(self, window: str):
        self.window = window

    def set_status(self, status: str | None):
        print(status)
        logger.info(status)
        self.status = status

    def get_current_teams(self):
        match = self.get_current_match()
        teams = []
        if not match: return None
        if len(match['players']) == 2:
            for i in range(0, len(match['players'])):
                teams.append(match['players'][i]['team'])
        return teams

    def set_start_match_number(self, number: int):
        self.start_match_number = number


game = GameController()
