"""Application configuration module using Pydantic Settings."""

from typing import Literal, Optional
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAS_PYDANTIC_SETTINGS = True
except ImportError:  # pragma: no cover
    from pydantic import BaseSettings
    HAS_PYDANTIC_SETTINGS = False


class Settings(BaseSettings):
    """Production settings for Enterprise Semantic Caching & TokenOps Gateway."""

    # Server settings
    PROJECT_NAME: str = "Enterprise LLM Semantic Caching & TokenOps Gateway"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/v1"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8090
    LOG_LEVEL: str = "INFO"

    # Redis Vector Store & Semantic Caching
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_INDEX_NAME: str = "idx:llm_semantic_cache"
    REDIS_PREFIX: str = "cache:llm:"
    VECTOR_DIMENSION: int = 1536
    SIMILARITY_THRESHOLD: float = 0.88  # Cosine similarity >= 0.88 counts as cache hit
    CACHE_TTL_SECONDS: int = 86400  # 24 hours
    CACHE_ENABLED: bool = True

    # Embedding Provider
    EMBEDDING_PROVIDER: Literal["openai", "deterministic"] = "deterministic"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Model Tiering & Dynamic Routing
    ROUTING_ENABLED: bool = True
    DEFAULT_BASELINE_MODEL: str = "gpt-4o"
    TIER_1_MODEL: str = "gpt-4o-mini"
    TIER_2_MODEL: str = "gpt-4o"
    TIER_3_MODEL: str = "o1-mini"

    # Complexity & Length Routing Thresholds
    TIER_1_MAX_TOKENS: int = 500
    TIER_2_MAX_TOKENS: int = 2500
    COMPLEXITY_THRESHOLD_TIER2: float = 0.35
    COMPLEXITY_THRESHOLD_TIER3: float = 0.70

    # Upstream LLM Configuration
    UPSTREAM_PROVIDER: Literal["openai", "mock"] = "mock"
    UPSTREAM_TIMEOUT_SECONDS: float = 30.0
    UPSTREAM_MAX_RETRIES: int = 3

    if HAS_PYDANTIC_SETTINGS:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=True,
            extra="ignore",
        )
    else:  # pragma: no cover
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = True
            extra = "ignore"


settings = Settings()
