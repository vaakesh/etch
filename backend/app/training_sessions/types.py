from typing import Annotated

from pydantic import Field

from app.training_sessions.schemas import SkipAnswerRequest, SubmittedAnswerRequest

type UserAnswer = Annotated[
    SkipAnswerRequest | SubmittedAnswerRequest,
    Field(discriminator="action"),
]
