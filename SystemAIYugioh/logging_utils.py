from __future__ import annotations

LEVELS = {"quiet": 0, "normal": 1, "verbose": 2, "debug": 3}


class Logger:
    def __init__(self, level: str = "normal") -> None:
        self.level = LEVELS.get(level, 1)

    def log(self, message: str, level: str = "normal") -> None:
        if self.level >= LEVELS.get(level, 1):
            print(message)

    def debug(self, message: str) -> None:
        self.log(message, "debug")

    def verbose(self, message: str) -> None:
        self.log(message, "verbose")

    def normal(self, message: str) -> None:
        self.log(message, "normal")


def get_logger(level: str = "normal") -> Logger:
    return Logger(level)
