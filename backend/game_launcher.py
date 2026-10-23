"""Runs project.py inside its own terminal window (opened by game_runner).

Usage: python game_launcher.py <path to project.py> <path to game.log>
If the game crashes, the error stays visible in the terminal and is written to game.log
so the backend can show it on the website.
"""
import ctypes
import os
import runpy
import sys
import traceback

CRASH_MARKER = "GAME CRASHED"


def main():
    game_path, log_path = sys.argv[1], sys.argv[2]
    player = os.environ.get("TANK_PLAYER", "Player")

    if os.name == "nt":
        ctypes.windll.kernel32.SetConsoleTitleW(f"Tank Survival 3D - {player}")

    print("=" * 54)
    print(f"  Tank Survival 3D  |  Player: {player}")
    print("  Your score is saved automatically on game over.")
    print("  Press P (or Esc) in the game window to pause / resume.")
    print("  Press M to turn sound on / off.")
    print("  Close the game window (or this terminal) to stop.")
    print("=" * 54, flush=True)

    # Run the game as if started with "python project.py" from its own folder,
    # so the bundled OpenGL package (with freeglut DLLs) is imported
    game_dir = os.path.dirname(os.path.abspath(game_path))
    sys.path.insert(0, game_dir)
    sys.argv = [game_path]
    try:
        runpy.run_path(game_path, run_name="__main__")
    except SystemExit:
        raise
    except BaseException:
        error = traceback.format_exc()
        with open(log_path, "w", encoding="utf-8") as log:
            log.write(f"{CRASH_MARKER}\n{error}")
        print(f"\n{CRASH_MARKER}:\n{error}", flush=True)
        try:
            input("Press Enter to close this window...")
        except EOFError:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
