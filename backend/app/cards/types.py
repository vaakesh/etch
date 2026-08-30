from typing import Annotated

from pydantic import Field

type CardImportBatch[T] = Annotated[
    list[T],
    Field(min_length=1, max_length=500),
]
