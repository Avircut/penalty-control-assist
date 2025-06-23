import json
import os
import eel

from game_controller import game
from path_utils import get_executable_path
from type_declarations import Configuration

default_cfg={
    "hudCoords": [
        {
            "x": 1163,
            "y": 114
        },
        {
            "x": 1256,
            "y": 154
        }
    ],
    "max_kicks": 5,
    "matches_in_series": 6,
    "fps": 30,
    "screen": 1
}


def load_config():
    config_path = get_executable_path('config.json')
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if 'file_path' in data:
                game.set_file(data['file_path'])
            if 'screen' in data:
                game.set_window(data['screen'])
            return data
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(default_cfg, f, indent=4)
    return default_cfg


cfg: Configuration = load_config()

def save_config(data):
    config_path = get_executable_path('config.json')
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({**cfg,**data}, f, indent=4)
    cfg.update(data)

@eel.expose
def get_config():
    return cfg
