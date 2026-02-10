from pathlib import Path
from winreg import HKEY_LOCAL_MACHINE, OpenKey, QueryValueEx, KEY_READ, KEY_WOW64_64KEY

from cs2_map_parser import MapParser


def get_cs2_path() -> Path:
    key_path = OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\cs2", 0, KEY_READ | KEY_WOW64_64KEY)
    cs2_path = QueryValueEx(key_path, "installpath")[0]
    return Path(cs2_path)


def main() -> None:
    Path("./map").mkdir(exist_ok=True)

    map_folder_path = get_cs2_path() / "game" / "csgo" / "maps"
    for map_path in map_folder_path.iterdir():
        if not map_path.is_file() or not map_path.with_suffix(".vpk"):
            continue

        map_name = map_path.stem
        try:
            MapParser.vpk2tri(map_path, f"map/{map_name}.tri")
            print(f"[SUCC] {map_name}")
        except:
            print(f"[FAIL] {map_name}")
            continue



if __name__ == '__main__':
    main()