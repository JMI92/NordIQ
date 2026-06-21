"""Shared enumerations used across multiple models."""

import enum


class ProductCategory(str, enum.Enum):
    PACKAGING = "packaging"
    WEEE = "weee"
    BATTERIES = "batteries"
    VEHICLES = "vehicles"
    OTHER = "other"


class MaterialType(str, enum.Enum):
    PLASTIC = "plastic"
    PAPER = "paper"
    GLASS = "glass"
    METAL = "metal"
    WOOD = "wood"
    ELECTRONICS = "electronics"
    BATTERY = "battery"
    OTHER = "other"
    RIGID_PLASTIC = "rigid_plastic"
    FLEXIBLE_PLASTIC = "flexible_plastic"
    SINGLE_USE_PLASTIC = "single_use_plastic"
    BEVERAGE_CARTON = "beverage_carton"
    COMPOSITE = "composite"


class PackagingStream(str, enum.Enum):
    HOUSEHOLD = "household"
    COMMERCIAL = "commercial"
    MIXED = "mixed"


class DataSourceType(str, enum.Enum):
    SNOWFLAKE = "snowflake"
    CSV = "csv"
    API = "api"


class ObligationStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALISED = "finalised"
    SUBMITTED = "submitted"


class SubmissionMethod(str, enum.Enum):
    API = "api"
    PORTAL = "portal"
    EMAIL = "email"


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class ImportJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DataRecordSource(str, enum.Enum):
    SNOWFLAKE = "snowflake"
    CSV = "csv"
    MANUAL = "manual"
