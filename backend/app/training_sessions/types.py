from typing import Annotated

from app.training_sessions.schemas import SkipAnswerRequest, SubmittedAnswerRequest
from pydantic import Field

type UserAnswer = Annotated[
    SkipAnswerRequest | SubmittedAnswerRequest,
    Field(discriminator="action"),
]
