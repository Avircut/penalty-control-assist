from enum import Enum
from typing import TypeAlias

Point: TypeAlias = {
    'x': float,
    'y': float
}

Configuration: TypeAlias = {
    'hud_coords': tuple[Point, Point],
    'max_kicks': int,
    'fps': int,
    'matches_in_series': int,
    'file_path': str,
    'screen': str
}


class CellState(Enum):
    SUCCESS = '+'
    FAIL = '-'


PlayerState: TypeAlias = {
    'team': str,
    'score': int,
    'cells': list[CellState]
}

SeriesPlayerState: TypeAlias = {
    'score': int,
    'name': str,
    'team': str,
}

MatchState: TypeAlias = {'players': list[PlayerState], 'isGameOver': bool}

SeriesState: TypeAlias = {
    'players': list[SeriesPlayerState],
    'matches': list[MatchState]
}



class CVMode(Enum):
    ON = 'on'
    OFF = 'off'

class MatchResult(Enum):
    SUSPENDED = -2
    DRAW = -1
    FIRST_PLAYER = 0
    SECOND_PLAYER = 1
