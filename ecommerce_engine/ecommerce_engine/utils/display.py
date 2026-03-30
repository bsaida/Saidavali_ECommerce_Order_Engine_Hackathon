def header(title: str):
    width = 56
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def divider():
    print("-" * 56)


def success(msg: str):
    print(f"  ✅  {msg}")


def error(msg: str):
    print(f"  ❌  {msg}")


def warn(msg: str):
    print(f"  ⚠️   {msg}")


def info(msg: str):
    print(f"  ℹ️   {msg}")


def event_print(msg: str):
    print(f"  📡  {msg}")


def log_print(msg: str):
    print(f"  📋  {msg}")


def pause():
    input("\n  Press Enter to continue...")
    print()


def ask(prompt: str) -> str:
    return input(f"  {prompt}: ").strip()


def ask_int(prompt: str) -> int:
    while True:
        try:
            return int(ask(prompt))
        except ValueError:
            error("Please enter a valid number.")


def ask_float(prompt: str) -> float:
    while True:
        try:
            return float(ask(prompt))
        except ValueError:
            error("Please enter a valid number.")
