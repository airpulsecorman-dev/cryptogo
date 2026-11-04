from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=8_192)


class DevelopmentAuthRequest(BaseModel):
    telegram_id: int = Field(gt=0)
    first_name: str = Field(min_length=1, max_length=128)
    username: str | None = Field(default=None, max_length=64)


class PlayerResponse(BaseModel):
    id: UUID
    telegram_id: int
    first_name: str
    username: str | None
    points: int
    total_xp: int
    level: int
    xp_into_level: int
    xp_for_next_level: int
    collected_count: int
    registered_at: datetime


class NearbyCollectible(BaseModel):
    id: UUID
    ticker: str
    name: str
    symbol: str
    rarity: str
    latitude: float
    longitude: float
    distance_meters: float
    collection_radius_meters: int
    expires_at: datetime


class CollectRequest(BaseModel):
    spawn_instance_id: UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float = Field(gt=0, le=10_000)
    client_timestamp: datetime

    @field_validator("client_timestamp")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("client_timestamp must include a timezone.")
        return value


class CollectibleResult(BaseModel):
    ticker: str
    name: str
    rarity: str


class RewardResult(BaseModel):
    points: int
    xp: int


class CollectResponse(BaseModel):
    success: bool
    collection_id: UUID
    collectible: CollectibleResult
    rewards: RewardResult
    player: PlayerResponse
    message: str


class InventoryItem(BaseModel):
    ticker: str
    name: str
    symbol: str
    rarity: str
    count: int


class CollectionHistoryItem(BaseModel):
    collection_id: UUID
    ticker: str
    name: str
    collected_at: datetime
    points: int
    xp: int


class InventoryResponse(BaseModel):
    items: list[InventoryItem]
    history: list[CollectionHistoryItem]
    total_collected: int


class LeaderboardEntry(BaseModel):
    rank: int
    first_name: str
    points: int
    level: int
    is_current_player: bool


class ZoneResponse(BaseModel):
    id: UUID
    name: str
    boundary: dict


class MissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    missions: list[dict] = []
