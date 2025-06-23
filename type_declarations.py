from enum import Enum
from typing import TypeAlias

Point: TypeAlias = {
    'x': float,
    'y': float
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

Configuration: TypeAlias = {
    'hud_coords': tuple[Point, Point],
    'max_kicks': int,
    'fps': int,
    'matches_in_series': int,
    'file_path': str
}

class CVMode(Enum):
    ON = 'on'
    OFF = 'off'
