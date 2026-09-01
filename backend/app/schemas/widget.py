from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

WidgetType = Literal["sql", "script"]
WidgetWidth = Literal["half", "full"]
TrendType = Literal["positive", "negative", "neutral"]
ChartType = Literal["bar", "line", "area", "composed", "pie"]


class WidgetKPI(BaseModel):
    label: str
    value_minor: Optional[int] = None
    formatted_value: Optional[str] = None
    trend: Optional[TrendType] = "neutral"
    subtitle: Optional[str] = None


class WidgetSeries(BaseModel):
    key: str
    label: str
    color: Optional[str] = None
    type: Optional[Literal["bar", "line", "area"]] = "bar"


class WidgetLegendItem(BaseModel):
    label: str
    color: str
    type: Optional[Literal["line", "rect", "circle"]] = "rect"


class WidgetChart(BaseModel):
    chart_type: ChartType = "bar"
    x_axis: str = "name"
    series: list[WidgetSeries] = []
    data: list[dict[str, Any]] = []
    custom_legend: Optional[list[WidgetLegendItem]] = None


class WidgetTable(BaseModel):
    columns: list[str] = []
    rows: list[list[Any]] = []


class WidgetManifest(BaseModel):
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    category: str = "Generelt"
    icon: str = "BarChart3"
    type: WidgetType = "sql"
    width: WidgetWidth = "half"
    sql_query: Optional[str] = None
    refresh_interval_seconds: int = 3600
    default_enabled: bool = True


class WidgetOutput(BaseModel):
    success: bool = True
    summary: Optional[str] = None
    kpis: list[WidgetKPI] = Field(default_factory=list)
    chart: Optional[WidgetChart] = None
    table: Optional[WidgetTable] = None
    image: Optional[str] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    computed_at: Optional[str] = None


class WidgetListItem(BaseModel):
    manifest: WidgetManifest
    is_enabled: bool
    position: int = 0
    has_script: bool = False
    last_updated: Optional[str] = None


class ToggleWidgetRequest(BaseModel):
    enabled: bool


class ReorderWidgetRequest(BaseModel):
    direction: Literal["up", "down"]
