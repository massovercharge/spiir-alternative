import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  BarChart3,
  Zap,
  ShoppingBag,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Table as TableIcon,
  PieChart,
  Wallet,
  Calendar,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  LineChart,
  Line,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card';
import { ActiveWidgetData } from './types';
import { fetchSingleWidgetData } from '../../api/domains/widgets';
import { useQueryClient } from '@tanstack/react-query';

const ICON_MAP: Record<string, React.ReactNode> = {
  Zap: <Zap size={20} className="text-amber-500" />,
  ShoppingBag: <ShoppingBag size={20} className="text-emerald-500" />,
  BarChart3: <BarChart3 size={20} className="text-blue-500" />,
  TrendingUp: <TrendingUp size={20} className="text-emerald-500" />,
  PieChart: <PieChart size={20} className="text-indigo-500" />,
  Wallet: <Wallet size={20} className="text-purple-500" />,
  Calendar: <Calendar size={20} className="text-rose-500" />,
};

interface WidgetCardProps {
  widget: ActiveWidgetData;
}

export const WidgetCard: React.FC<WidgetCardProps> = ({ widget }) => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showTraceback, setShowTraceback] = useState(false);

  const manifest = widget.manifest;
  const output = widget.output;

  const renderCustomLegend = () => {
    if (!output.chart?.custom_legend) return null;
    return (
      <div className="flex flex-wrap items-center justify-center gap-4 pt-2.5 text-xs">
        {output.chart.custom_legend.map((item, i) => (
          <div key={i} className="flex items-center gap-1.5">
            {item.type === 'line' ? (
              <span className="w-4 h-0.5" style={{ backgroundColor: item.color }} />
            ) : (
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: item.color }} />
            )}
            <span className="text-[hsl(var(--text-secondary))] font-medium">{item.label}</span>
          </div>
        ))}
      </div>
    );
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetchSingleWidgetData(manifest.id, true);
      queryClient.invalidateQueries({ queryKey: ['widgets', 'active-data'] });
    } catch (err) {
      console.error('Failed to refresh widget:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const formatCurrencyMinor = (minor?: number) => {
    if (minor === undefined || minor === null) return null;
    const locale = i18n.language === 'da' ? 'da-DK' : 'en-US';
    return `${(minor / 100).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr.`;
  };

  const iconComponent = ICON_MAP[manifest.icon] || (
    <BarChart3 size={20} className="text-[hsl(var(--brand-primary))]" />
  );

  return (
    <Card className="flex flex-col h-full overflow-hidden border border-[hsl(var(--border-color))] shadow-sm hover:shadow-md transition-shadow bg-[hsl(var(--bg-secondary))]">
      {/* Widget Header */}
      <CardHeader className="pb-3 border-b border-[hsl(var(--border-color))] flex flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="p-2 rounded-xl bg-[hsl(var(--bg-tertiary))] shrink-0">
            {iconComponent}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base sm:text-lg font-bold truncate text-[hsl(var(--text-primary))]">
                {manifest.name}
              </CardTitle>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] font-medium shrink-0">
                {manifest.category}
              </span>
            </div>
            {manifest.description && (
              <p className="text-xs text-[hsl(var(--text-secondary))] truncate mt-0.5">
                {manifest.description}
              </p>
            )}
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="p-1.5 rounded-lg text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors disabled:opacity-50 shrink-0"
          title={t('widgets.refresh', 'Opdater widget')}
        >
          <RefreshCw size={16} className={isRefreshing ? 'animate-spin' : ''} />
        </button>
      </CardHeader>

      <CardContent className="flex-1 p-4 sm:p-5 space-y-5">
        {/* Error State */}
        {(!output.success || output.error) && (
          <div className="p-4 rounded-xl bg-[hsla(var(--brand-danger),0.1)] border border-[hsla(var(--brand-danger),0.2)] text-[hsl(var(--text-primary))] space-y-2">
            <div className="flex items-center gap-2 text-[hsl(var(--brand-danger))] font-semibold text-sm">
              <AlertTriangle size={18} />
              <span>{t('widgets.errorTitle', 'Der opstod en fejl i denne widget')}</span>
            </div>
            <p className="text-sm text-[hsl(var(--text-secondary))]">{output.error}</p>
            {output.traceback && (
              <div className="pt-2">
                <button
                  onClick={() => setShowTraceback(!showTraceback)}
                  className="flex items-center gap-1 text-xs font-medium text-[hsl(var(--brand-primary))] hover:underline"
                >
                  {showTraceback ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  <span>
                    {showTraceback
                      ? t('widgets.hideTraceback', 'Skjul teknisk log')
                      : t('widgets.showTraceback', 'Vis teknisk fejllog')}
                  </span>
                </button>
                {showTraceback && (
                  <pre className="mt-2 p-3 rounded-lg bg-[hsl(var(--bg-tertiary))] text-xs font-mono overflow-x-auto text-[hsl(var(--text-secondary))] max-h-48">
                    {output.traceback}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}

        {/* Summary text */}
        {output.summary && (
          <div className="p-3.5 rounded-xl bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-color))]">
            <p className="text-sm text-[hsl(var(--text-primary))] leading-relaxed">
              {output.summary}
            </p>
          </div>
        )}

        {/* KPIs Grid */}
        {output.kpis && output.kpis.length > 0 && (
          <div
            className={`grid gap-3 grid-cols-2 ${output.kpis.length >= 4 ? 'sm:grid-cols-4' : 'sm:grid-cols-3'}`}
          >
            {output.kpis.map((kpi, idx) => {
              const displayVal =
                kpi.value_minor !== undefined && kpi.value_minor !== null
                  ? formatCurrencyMinor(kpi.value_minor)
                  : kpi.formatted_value;

              const trendColor =
                kpi.trend === 'positive'
                  ? 'text-emerald-500 dark:text-emerald-400'
                  : kpi.trend === 'negative'
                    ? 'text-rose-500 dark:text-rose-400'
                    : 'text-[hsl(var(--text-primary))]';

              return (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-color))] flex flex-col justify-between"
                >
                  <span className="text-xs font-medium text-[hsl(var(--text-secondary))] line-clamp-1">
                    {kpi.label}
                  </span>
                  <div className="mt-1">
                    <span className={`text-lg sm:text-xl font-bold tracking-tight ${trendColor}`}>
                      {displayVal}
                    </span>
                    {kpi.subtitle && (
                      <p className="text-[11px] text-[hsl(var(--text-secondary))] mt-0.5 line-clamp-1">
                        {kpi.subtitle}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Recharts Diagram */}
        {output.chart && output.chart.data && output.chart.data.length > 0 && (
          <div className="pt-2">
            <div className="h-64 sm:h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                {output.chart.chart_type === 'composed' || output.chart.chart_type === 'bar' ? (
                  <ComposedChart
                    data={output.chart.data}
                    margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(var(--border-color))"
                      vertical={false}
                    />
                    <XAxis
                      dataKey={output.chart.x_axis}
                      tick={{ fill: 'hsl(var(--text-secondary))', fontSize: 11 }}
                      axisLine={{ stroke: 'hsl(var(--border-color))' }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'hsl(var(--text-secondary))', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--bg-secondary))',
                        borderColor: 'hsl(var(--border-color))',
                        borderRadius: '0.75rem',
                        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                        color: 'hsl(var(--text-primary))',
                      }}
                    />
                    {output.chart.custom_legend ? (
                      <Legend content={renderCustomLegend} />
                    ) : (
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
                    )}
                    {output.chart.series.map((s, idx) => {
                      const color = s.color || (idx === 0 ? '#10b981' : '#3b82f6');
                      if (s.type === 'line') {
                        return (
                          <Line
                            key={s.key}
                            type="monotone"
                            dataKey={s.key}
                            name={s.label}
                            stroke={color}
                            strokeWidth={2.5}
                            dot={{ r: 3 }}
                          />
                        );
                      }
                      return (
                        <Bar
                          key={s.key}
                          dataKey={s.key}
                          name={s.label}
                          fill={color}
                          radius={[4, 4, 0, 0]}
                        >
                          {output.chart?.data?.map((entry, entryIdx) => {
                            const cellColor = entry[`${s.key}_color`] || entry.color || color;
                            return <Cell key={`cell-${entryIdx}`} fill={cellColor} />;
                          })}
                        </Bar>
                      );
                    })}
                  </ComposedChart>
                ) : (
                  <LineChart
                    data={output.chart.data}
                    margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(var(--border-color))"
                      vertical={false}
                    />
                    <XAxis
                      dataKey={output.chart.x_axis}
                      tick={{ fill: 'hsl(var(--text-secondary))', fontSize: 11 }}
                      axisLine={{ stroke: 'hsl(var(--border-color))' }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'hsl(var(--text-secondary))', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--bg-secondary))',
                        borderColor: 'hsl(var(--border-color))',
                        borderRadius: '0.75rem',
                        color: 'hsl(var(--text-primary))',
                      }}
                    />
                    {output.chart.custom_legend ? (
                      <Legend content={renderCustomLegend} />
                    ) : (
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
                    )}
                    {output.chart.series.map((s, idx) => (
                      <Line
                        key={s.key}
                        type="monotone"
                        dataKey={s.key}
                        name={s.label}
                        stroke={s.color || (idx === 0 ? '#10b981' : '#3b82f6')}
                        strokeWidth={2}
                      />
                    ))}
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Table representation */}
        {output.table && output.table.rows && output.table.rows.length > 0 && (
          <div className="pt-2">
            <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wider text-[hsl(var(--text-secondary))]">
              <TableIcon size={14} />
              <span>{t('widgets.dataTable', 'Datatabel')}</span>
            </div>
            <div className="overflow-x-auto rounded-xl border border-[hsl(var(--border-color))] max-h-60 overflow-y-auto">
              <table className="w-full text-left text-xs sm:text-sm">
                <thead className="bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] font-medium border-b border-[hsl(var(--border-color))] sticky top-0">
                  <tr>
                    {output.table.columns.map((col, idx) => (
                      <th key={idx} className="py-2.5 px-3 whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border-color))]">
                  {output.table.rows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-[hsl(var(--bg-tertiary))] transition-colors">
                      {row.map((cell, cIdx) => (
                        <td
                          key={cIdx}
                          className="py-2 px-3 whitespace-nowrap text-[hsl(var(--text-primary))]"
                        >
                          {String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Generated Image/Plot */}
        {output.image && (
          <div className="pt-2 rounded-xl overflow-hidden border border-[hsl(var(--border-color))]">
            <img
              src={output.image}
              alt={manifest.name}
              className="w-full h-auto object-contain max-h-96"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
};
