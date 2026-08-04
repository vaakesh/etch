class TrainingSessionNotFoundError(Exception):
    def __init__(self, message: str = "Training session not found"):
        super().__init__(message)

class TrainingSessionItemNotFoundError(Exception):
    def __init__(self, message: str = "Training session item not found"):
        super().__init__(message)

class CardAlreadyAnsweredError(Exception):
    def __init__(self, message: str = "Card already answered"):
        super().__init__(message)

class TrainingSessionAlreadyFinishedError(Exception):
    def __init__(self, message: str = "Training session already finished"):
            super().__init__(message)

class TrainingSessionAlreadyExistsError(Exception):
    def __init__(self, message: str = "Training session already exists"):
        super().__init__(message)

class TrainingSessionNotFinishedYet(Exception):
    def __init__(self, message: str = "Training session not finished yet"):
        super().__init__(message)

class PermissionDeniedError(Exception):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)