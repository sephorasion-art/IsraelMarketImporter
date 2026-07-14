from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Product(BaseModel):
	title: str = ""
	description: str = ""
	price: float | None = None
	compare_at_price: float | None = None
	sku: str = ""
	barcode: str = ""
	brand: str = ""
	category: str = ""
	image: str = ""
	gallery: list[str] = Field(default_factory=list)
	stock: int | None = None
	weight: float | None = None
	tags: list[str] = Field(default_factory=list)
	url: str = ""


class DetectionReport(BaseModel):
	domain: str
	cms: str = "unknown"
	technologies: list[str] = Field(default_factory=list)
	is_html: bool = True
	is_react: bool = False
	is_nextjs: bool = False
	has_rest_api: bool = False
	has_graphql: bool = False
	has_json_api: bool = False
	has_jsonld: bool = False
	has_schema_microdata: bool = False
	has_hydration_data: bool = False
	has_next_data: bool = False
	has_initial_state: bool = False
	preferred_engine: str = "html"


class LogEntry(BaseModel):
	ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
	level: str
	message: str


@dataclass(slots=True)
class EnginePayload:
	html: str = ""
	title: str = ""
	status_code: int | None = None
	final_url: str | None = None
	response_headers: dict[str, str] = field(default_factory=dict)
	network_calls: list[str] = field(default_factory=list)
	api_payloads: list[Any] = field(default_factory=list)


class ImportResult(BaseModel):
	detection: DetectionReport
	engine_used: str
	elapsed_ms: int
	products: list[Product] = Field(default_factory=list)
	logs: list[LogEntry] = Field(default_factory=list)


class RuntimeOptions(BaseModel):
	proxy_url: str | None = None
	cookie_header: str | None = None
	user_agent: str | None = None
