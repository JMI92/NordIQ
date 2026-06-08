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
