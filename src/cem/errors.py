"""Stable errors never interpolate collected values or exception messages."""


class CEMError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def refuse(code: str, message: str, status: int = 400):
    raise CEMError(code, message, status)
