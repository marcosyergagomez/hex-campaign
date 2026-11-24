"""Rule failures. The HTTP layer turns each code into a sentence."""


class DomainError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
