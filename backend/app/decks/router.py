from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.auth.deps import get_current_user
from app.cards.schemas import CardSchema
from app.users.models import User

from .deps import get_deck_service, get_user_deck_service
from .schemas import (
    DeckCardSchema,
    DeckCardUpdate,
    DeckCreate,
    DeckOut,
    DeckSchema,
    DeckUpdate,
    ReorderCards,
    UserDeckSchema,
)
from .service import DeckService, UserDeckService


router = APIRouter(prefix="/decks")


@router.get("/", response_model=list[DeckSchema])
async def get_all_decks_by_limit(
    limit: int = 10,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_all_decks_by_limit(limit)


@router.get("/public", response_model=list[DeckSchema])
async def get_public_decks_by_limit(
    limit: int = 10,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_public_decks_by_limit(limit)

@router.get(
    "/followed",
)
async def get_followed_decks_by_user(
    limit: int = Query(default=10),
    current_user: User = Depends(get_current_user),
    user_deck_service: UserDeckService = Depends(get_user_deck_service),
) -> list[UserDeckSchema]:
    user_decks = await user_deck_service.get_followed_decks_by_user_id(
        user_id=current_user.id,
        limit=limit,
    )
    return user_decks


@router.get("/{deck_uuid}", response_model=DeckSchema)
async def get_deck(
    deck_uuid: UUID,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_by_uuid(deck_uuid)


@router.post("/", response_model=DeckOut)
async def create_deck(
    payload: DeckCreate,
    current_user: User = Depends(get_current_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.create_deck(payload, user_id=current_user.id)


@router.patch("/{deck_uuid}", response_model=DeckSchema)
async def update_deck(
    deck_uuid: UUID,
    payload: DeckUpdate,
    current_user: User = Depends(get_current_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.update_deck(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        payload=payload,
    )


@router.delete("/{deck_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    deck_uuid: UUID,
    deck_service: DeckService = Depends(get_deck_service),
):
    await deck_service.delete_deck(deck_uuid)
    return None


@router.get("/{deck_uuid}/cards", response_model=list[CardSchema])
async def get_deck_cards(
    deck_uuid: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_deck_cards(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        offset=offset,
        limit=limit,
    )

@router.post(
    "/{deck_uuid}/cards/remove/{card_uuid}",
    response_model=None,
)
async def remove_card_from_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    current_user: User = Depends(get_current_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.remove_card_from_deck(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        card_uuid=card_uuid,
    )

@router.post(
        "/{deck_uuid}/cards/reorder",
)
async def reorder_deck_cards(
    deck_uuid: UUID,
    payload: ReorderCards,
    current_user: User = Depends(get_current_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    await deck_service.reorder_cards(
            user_id=current_user.id,
            deck_uuid=deck_uuid,
            card_uuid=payload.card_uuid,
            to_position=payload.to_position,
    )

@router.post(
    "/{deck_uuid}/cards/{card_uuid}",
    response_model=DeckCardSchema,
)
async def add_card_to_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    current_user: User = Depends(get_current_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.add_card_to_deck(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        card_uuid=card_uuid,
    )


@router.patch(
    "/{deck_uuid}/cards/{card_uuid}",
    response_model=DeckCardSchema,
)
async def update_deck_card(
    deck_card_uuid: UUID,
    payload: DeckCardUpdate,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.update_deck_card(
        deck_card_uuid=deck_card_uuid,
        position=payload.position,
    )


@router.delete(
    "/{deck_uuid}/cards/{card_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_card_from_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    current_user: User = Depends(get_current_user),
    deck_service: DeckService = Depends(get_deck_service),
):
    await deck_service.remove_card_from_deck(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        card_uuid=card_uuid,
    )
    return None


@router.patch(
    "/{deck_uuid}/set-favourite",
    response_model=UserDeckSchema,
)
async def set_favourite(
    deck_uuid: UUID,
    value: bool = Query(),
    current_user: User = Depends(get_current_user),
    user_deck_service: UserDeckService = Depends(get_user_deck_service),
):
    user_deck = await user_deck_service.set_favourite_deck(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        value=value,
    )
    return user_deck


@router.post(
    "/{deck_uuid}/follow",
    response_model=UserDeckSchema,
)
async def follow_deck(
    deck_uuid: UUID,
    current_user: User = Depends(get_current_user),
    user_deck_service: UserDeckService = Depends(get_user_deck_service),
):
    user_deck = await user_deck_service.follow_deck(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
    )
    return user_deck

@router.post(
    "/{deck_uuid}/unfollow",
    response_model=UserDeckSchema,
)
async def unfollow_deck(
    deck_uuid: UUID,
    current_user: User = Depends(get_current_user),
    user_deck_service: UserDeckService = Depends(get_user_deck_service),
):
    user_deck = await user_deck_service.unfollow_deck(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
    )
    return user_deck
