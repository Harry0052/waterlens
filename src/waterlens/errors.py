"""Actionable input errors. These are not detector failures."""


class WaterLensError(Exception):
    def __init__(
        self,
        category: str,
        message: str,
        *,
        path: str | None = None,
        row: int | None = None,
    ) -> None:
        self.category = category
        self.path = path
        self.row = row
        super().__init__(message)

    def as_dict(self) -> dict:
        return {
            "status": "error",
            "category": self.category,
            "message": str(self),
            "path": self.path,
            "row": self.row,
        }
