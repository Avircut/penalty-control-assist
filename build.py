import os

name_proj = "PenaltyControlAssist"
noconsole="--windowed"
onefile=" --onefile "

if __name__ == "__main__":
    cmd_txt = f'python -m eel main.py ui {onefile} {noconsole} --name {name_proj} '
    os.system(cmd_txt)
