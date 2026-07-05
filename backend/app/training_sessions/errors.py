class TrainingSessionNotFoundError(Exception):
    def __init__(self, message: str = "Training session not found"):
        super().__init__(message)


class TrainingSessionAlreadyExistsError(Exception):
    def __init__(self, message: str = "Training session already exists"):
        super().__init__(message)


class PermissionDeniedError(Exception):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)