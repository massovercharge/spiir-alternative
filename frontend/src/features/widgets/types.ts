export type WidgetType = 'sql' | 'script';
export type WidgetWidth = 'half' | 'full';
export type TrendType = 'positive' | 'negative' | 'neutral';
export type ChartType = 'bar' | 'line' | 'area' | 'composed' | 'pie';

export interface WidgetKPI {
  label: string;
  value_minor?: number;
  formatted_value?: string;
  trend?: TrendType;
  subtitle?: string;
}

export interface WidgetSeries {
  key: string;
  label: string;
  color?: string;
  type?: 'bar' | 'line' | 'area';
}

export interface WidgetChart {
  chart_type: ChartType;
  x_axis: string;
  series: WidgetSeries[];
  data: Record<string, any>[];
}

export interface WidgetTable {
  columns: string[];
  rows: any[][];
}

export interface WidgetManifest {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  category: string;
  icon: string;
  type: WidgetType;
  width: WidgetWidth;
  sql_query?: string;
  refresh_interval_seconds: number;
  default_enabled: boolean;
}

export interface WidgetOutput {
  success: boolean;
  summary?: string;
  kpis: WidgetKPI[];
  chart?: WidgetChart;
  table?: WidgetTable;
  image?: string;
  error?: string;
  traceback?: string;
  computed_at?: string;
}

export interface WidgetListItem {
  manifest: WidgetManifest;
  is_enabled: boolean;
  position: number;
  has_script: boolean;
  last_updated?: string;
}

export interface ActiveWidgetData {
  manifest: WidgetManifest;
  output: WidgetOutput;
  position: number;
}
