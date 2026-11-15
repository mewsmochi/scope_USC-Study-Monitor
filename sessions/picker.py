"""Start-of-session prompts: which class, which timer."""
from data.db import add_class, list_classes


def pick_class():
    """Returns (class_id, name). Loops until a class is chosen or created."""
    while True:
        classes = list_classes()
        print("\nWhich class are you studying?")
        for i, c in enumerate(classes, start=1):
            print(f"  {i}. {c['name']}")
        print("  n. Add a new class")
        pick = input("> ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(classes):
            c = classes[int(pick) - 1]
            return c["id"], c["name"]
        if pick.lower() == "n":
            name = input("Class name: ").strip()
            if name:
                return add_class(name), name


def pick_timer(config):
    """Returns "regular" or "pomodoro"."""
    work, brk, rounds = (config["pomodoro_work_minutes"], config["pomodoro_break_minutes"],
                         config["pomodoro_rounds"])
    while True:
        print("\nTimer:")
        print("  1. Regular (counts up, Ctrl+C to end)")
        print(f"  2. Pomodoro ({work}/{brk} min x {rounds} rounds, change in config.json)")
        pick = input("> ").strip()
        if pick in ("1", "2"):
            return "regular" if pick == "1" else "pomodoro"
