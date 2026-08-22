import React, { useState, useMemo, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { useInsightsSunburst, useCompleteBankConnection } from '../api/client';
import { Loader2, CalendarDays } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Skeleton } from '../components/ui/Skeleton';
import { Button } from '../components/ui/Button';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { SunburstChart } from 'echarts/charts';
import { TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchTransactions } from '../api/client';
import { useCategories } from '../components/ui/CategoryPicker';
import { TransactionDetailsSidebar } from '../components/ui/TransactionDetailsSidebar';
import { format, isToday, isYesterday, parseISO } from 'date-fns';
import { da, enUS } from 'date-fns/locale';

echarts.use([SunburstChart, TooltipComponent, CanvasRenderer]);

type PeriodMode = 'last12' | 'month' | 'year';

// Curated color palette - vibrant, distinguishable
const CATEGORY_COLORS: Record<string, string> = {
  'Bolig': '#6366f1',
  'Transport': '#f59e0b',
  'Mad & Drikke': '#10b981',
  'Underholdning': '#ec4899',
  'Tøj & Sko': '#8b5cf6',
  'Sundhed': '#ef4444',
  'Pension & Opsparing': '#14b8a6',
  'Børn': '#f97316',
  'Forsikring': '#3b82f6',
  'Personlig pleje': '#a855f7',
  'Diverse': '#6b7280',
  'Hus & Have': '#84cc16',
  'Elektronik': '#06b6d4',
  'Ferie & Rejser': '#eab308',
  'Gaver & Donationer': '#e11d48',
  'Abonnementer': '#7c3aed',
  'Andre leveomkostninger': '#64748b',
  'Privatforbrug': '#0ea5e9',
};

function hslToHex(h: number, s: number, l: number): string {
  l /= 100;
  const a = s * Math.min(l, 1 - l) / 100;
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function getColorForCategory(name: string, idx: number): string {
  if (CATEGORY_COLORS[name]) return CATEGORY_COLORS[name];
  const hue = (idx * 47 + 200) % 360;
  return hslToHex(hue, 65, 55);
}

/** Lighten a hex color by a factor (0 = same, 0.5 = halfway to white) */
function lightenHex(hex: string, factor: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const lr = Math.min(255, Math.round(r + (255 - r) * factor));
  const lg = Math.min(255, Math.round(g + (255 - g) * factor));
  const lb = Math.min(255, Math.round(b + (255 - b) * factor));
  return `#${lr.toString(16).padStart(2, '0')}${lg.toString(16).padStart(2, '0')}${lb.toString(16).padStart(2, '0')}`;
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isMobile;
}

export default function DashboardPage() {
  const { t, i18n } = useTranslation();
  const completeBankMutation = useCompleteBankConnection();
  const [isFinishingConnection, setIsFinishingConnection] = useState(false);
  const isMobile = useIsMobile();
  const chartRef = useRef<any>(null);

  // Period state
  const [periodMode, setPeriodMode] = useState<PeriodMode>('last12');
  const [selectedDate, setSelectedDate] = useState(() => new Date());

  // Legend hover state
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);
  // Clicked/focused category for scorecards
  const [focusedCategory, setFocusedCategory] = useState<{ name: string; value: number } | null>(null);
  // Selected transaction for details sidebar
  const [selectedTransaction, setSelectedTransaction] = useState<any>(null);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const code = searchParams.get('code');
    if (code && !isFinishingConnection) {
      // Clear the code from the URL immediately to prevent double-call
      // (React StrictMode double-mount or fast re-renders could re-trigger)
      window.history.replaceState({}, document.title, window.location.pathname);
      setIsFinishingConnection(true);
      completeBankMutation.mutate(code, {
        onSuccess: () => {
          setIsFinishingConnection(false);
        },
        onError: () => setIsFinishingConnection(false),
      });
    }
  }, []);

  // Compute API params based on period mode
  const sunburstParams = useMemo(() => {
    if (periodMode === 'last12') {
      const end = new Date();
      const start = new Date();
      start.setMonth(start.getMonth() - 12);
      start.setDate(1);
      return {
        startDate: start.toISOString().slice(0, 10),
        endDate: end.toISOString().slice(0, 10),
      };
    }
    if (periodMode === 'month') {
      return {
        year: selectedDate.getFullYear(),
        month: selectedDate.getMonth() + 1,
      };
    }
    return { year: selectedDate.getFullYear() };
  }, [periodMode, selectedDate]);

  const { data: sunburstData, isLoading } = useInsightsSunburst(sunburstParams);

  const { data: allCategories } = useCategories();
  
  const focusedCategoryId = useMemo(() => {
    if (!focusedCategory || !allCategories) return undefined;
    
    const sub = allCategories.find(c => c.name === focusedCategory.name);
    if (sub) return sub.id;
    
    const main = allCategories.find(c => c.mainCategoryName === focusedCategory.name);
    if (main) return main.id.split('|')[0];
    
    return undefined;
  }, [focusedCategory, allCategories]);

  const searchName = (!focusedCategoryId && focusedCategory) ? focusedCategory.name : undefined;

  const txDateParams = useMemo(() => {
    if (periodMode === 'last12') {
      const end = new Date();
      const start = new Date();
      start.setMonth(start.getMonth() - 12);
      start.setDate(1);
      return {
        start_date: start.toISOString().slice(0, 10),
        end_date: end.toISOString().slice(0, 10),
      };
    }
    if (periodMode === 'month') {
      const start = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1);
      const end = new Date(selectedDate.getFullYear(), selectedDate.getMonth() + 1, 0);
      return {
        start_date: start.toISOString().slice(0, 10),
        end_date: end.toISOString().slice(0, 10),
      };
    }
    const start = new Date(selectedDate.getFullYear(), 0, 1);
    const end = new Date(selectedDate.getFullYear(), 11, 31);
    return {
      start_date: start.toISOString().slice(0, 10),
      end_date: end.toISOString().slice(0, 10),
    };
  }, [periodMode, selectedDate]);

  const { data: focusedTxData, isLoading: isLoadingFocusedTx } = useQuery({
    queryKey: ['focused-transactions', txDateParams.start_date, txDateParams.end_date, focusedCategoryId, searchName],
    queryFn: () => fetchTransactions(
      100, 0, undefined, undefined, txDateParams.start_date, txDateParams.end_date, searchName, undefined, undefined, focusedCategoryId
    ),
    enabled: !!focusedCategory,
  });

  const formatTransactionDate = (dateStr: string, currentLang: string) => {
    if (!dateStr) return t('transactions.unknown_date');
    try {
      const d = parseISO(dateStr);
      if (isToday(d)) return t('transactions.today', 'I dag');
      if (isYesterday(d)) return t('transactions.yesterday', 'I går');
      return format(d, 'd. MMM yyyy', { locale: currentLang === 'en' ? enUS : da });
    } catch (e) {
      return dateStr.substring(0, 10);
    }
  };

  // Calculate totals from echarts_data
  const { totalExpense, categories } = useMemo(() => {
    const echartsData = sunburstData?.echarts_data || [];
    let total = 0;
    const cats: { name: string; value: number; children: { name: string; value: number; children?: { name: string; value: number }[] }[] }[] = [];

    for (const item of echartsData) {
      const val = Math.abs(Number(item.value));
      total += val;
      cats.push({
        name: item.name,
        value: val,
        children: (item.children || []).map((c: any) => ({
          name: c.name,
          value: Math.abs(Number(c.value)),
          children: c.children ? c.children.map((i: any) => ({ name: i.name, value: Math.abs(Number(i.value)) })) : undefined,
        })),
      });
    }

    return { totalExpense: total, categories: cats };
  }, [sunburstData]);

  // ECharts option — no labels, rely on legend + tooltip
  const chartOption = useMemo(() => {
    if (!categories.length) return {};

    const data = categories.map((cat, idx) => {
      const baseColor = getColorForCategory(cat.name, idx);
      return {
        name: cat.name,
        value: cat.value,
        itemStyle: {
          color: baseColor,
          borderColor: 'rgba(0,0,0,0.2)',
          borderWidth: 1,
        },
        children: cat.children.map((sub, sIdx) => ({
          name: sub.name,
          value: sub.value,
          itemStyle: {
            color: lightenHex(baseColor, 0.1 + sIdx * 0.08),
            borderColor: 'rgba(0,0,0,0.15)',
            borderWidth: 1,
          },
          ...(sub.children && sub.children.length > 0 ? {
            children: sub.children.map((item, iIdx) => ({
              name: item.name,
              value: item.value,
              itemStyle: {
                color: lightenHex(baseColor, 0.25 + iIdx * 0.04),
                borderColor: 'rgba(0,0,0,0.1)',
                borderWidth: 0.5,
              },
            })),
          } : {}),
        })),
      };
    });

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const pct = totalExpense > 0 ? ((params.value / totalExpense) * 100).toFixed(1) : '0';
          return `<div style="font-family: Inter, sans-serif; padding: 4px 0;">
            <strong>${params.name}</strong><br/>
            ${(params.value).toLocaleString('da-DK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr.<br/>
            <span style="color: #999">${pct}%</span>
          </div>`;
        },
        backgroundColor: 'rgba(30, 30, 40, 0.95)',
        borderColor: 'rgba(255,255,255,0.1)',
        textStyle: { color: '#f0f0f0', fontSize: 13 },
        extraCssText: 'border-radius: 10px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);',
      },
      series: [{
        type: 'sunburst',
        data,
        radius: ['12%', '95%'],
        sort: 'desc',
        emphasis: {
          focus: 'ancestor',
          itemStyle: {
            shadowBlur: 20,
            shadowColor: 'rgba(0,0,0,0.3)',
          },
        },
        levels: [
          {},
          {
            r0: '12%',
            r: '40%',
            label: { show: false },
            itemStyle: { borderRadius: 4 },
          },
          {
            r0: '40%',
            r: '68%',
            label: { show: false },
            itemStyle: { borderRadius: 3 },
          },
          {
            r0: '68%',
            r: '95%',
            label: {
              show: true,
              position: 'outside',
              fontSize: 9,
              color: 'rgba(255,255,255,0.6)',
              overflow: 'truncate',
              ellipsis: '…',
              minAngle: 8,
            },
            itemStyle: { borderRadius: 2 },
          },
        ],
        label: { show: false },
        animationDuration: 800,
        animationEasing: 'cubicInOut',
      }],
    };
  }, [categories, totalExpense]);

  // Highlight/downplay via ECharts dispatch
  const highlightCategory = useCallback((name: string) => {
    const instance = chartRef.current?.getEchartsInstance();
    if (!instance) return;
    instance.dispatchAction({ type: 'highlight', seriesIndex: 0, name });
  }, []);

  const downplayCategory = useCallback((name: string) => {
    const instance = chartRef.current?.getEchartsInstance();
    if (!instance) return;
    instance.dispatchAction({ type: 'downplay', seriesIndex: 0, name });
  }, []);

  const handleLegendHover = useCallback((catName: string) => {
    setHoveredCategory(catName);
    highlightCategory(catName);
  }, [highlightCategory]);

  const handleLegendLeave = useCallback((catName: string) => {
    setHoveredCategory(null);
    downplayCategory(catName);
  }, [downplayCategory]);

  const handleLegendClick = useCallback((cat: { name: string; value: number }) => {
    setFocusedCategory(prev => prev?.name === cat.name ? null : cat);
  }, []);

  // Handle click on sunburst segment
  const onChartClick = useCallback((params: any) => {
    if (params.data) {
      setFocusedCategory(prev =>
        prev?.name === params.data.name ? null : { name: params.data.name, value: Math.abs(params.data.value) }
      );
    }
  }, []);

  const onChartEvents = useMemo(() => ({
    click: onChartClick,
    sunburstroottochange: (params: any) => {
      const nodeName = params.toNode?.name;
      if (!nodeName || nodeName === 'Total') {
        setFocusedCategory(null);
      } else {
        setFocusedCategory({ name: nodeName, value: Math.abs(params.toNode.value) });
      }
    }
  }), [onChartClick]);

  // Period navigation
  const handlePrev = () => {
    const d = new Date(selectedDate);
    if (periodMode === 'month') d.setMonth(d.getMonth() - 1);
    else d.setFullYear(d.getFullYear() - 1);
    setSelectedDate(d);
  };
  const handleNext = () => {
    const d = new Date(selectedDate);
    if (periodMode === 'month') d.setMonth(d.getMonth() + 1);
    else d.setFullYear(d.getFullYear() + 1);
    setSelectedDate(d);
  };

  const periodLabel = useMemo(() => {
    if (periodMode === 'last12') return t('dashboard.last_12_months') || 'Seneste 12 måneder';
    if (periodMode === 'month') return selectedDate.toLocaleString('da-DK', { month: 'long', year: 'numeric' });
    return selectedDate.getFullYear().toString();
  }, [periodMode, selectedDate, t]);

  // Focused category details
  const focusedPct = focusedCategory && totalExpense > 0
    ? ((focusedCategory.value / totalExpense) * 100).toFixed(1)
    : null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 pb-28 md:pb-8"
    >
      {/* Header */}
      <div className="mb-2 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <motion.h1
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="text-3xl font-bold text-[hsl(var(--text-primary))]"
          >
            {t('app.dashboard')}
          </motion.h1>
          <motion.p
            initial={{ y: -5, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-muted mt-2"
          >
            {t('dashboard.overview')}
          </motion.p>
        </div>

        {/* Period Selector */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="flex items-center gap-2"
        >
          <div className="flex bg-[hsl(var(--bg-tertiary))] rounded-lg p-1 border border-[hsl(var(--border-color))]">
            <Button variant={periodMode === 'last12' ? 'primary' : 'ghost'} size="sm" onClick={() => setPeriodMode('last12')} className="text-xs px-3">
              <CalendarDays size={14} className="mr-1" />
              {t('dashboard.last_12_months') || '12 mdr.'}
            </Button>
            <Button variant={periodMode === 'month' ? 'primary' : 'ghost'} size="sm" onClick={() => setPeriodMode('month')} className="text-xs px-3">
              {t('dashboard.this_month') || 'Måned'}
            </Button>
            <Button variant={periodMode === 'year' ? 'primary' : 'ghost'} size="sm" onClick={() => setPeriodMode('year')} className="text-xs px-3">
              {t('dashboard.year') || 'År'}
            </Button>
          </div>

          {periodMode !== 'last12' && (
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-1 bg-[hsl(var(--bg-tertiary))] rounded-lg p-1 border border-[hsl(var(--border-color))]"
            >
              <Button variant="ghost" size="sm" onClick={handlePrev} className="px-2">‹</Button>
              <span className="font-medium text-sm min-w-[110px] text-center capitalize">{periodLabel}</span>
              <Button variant="ghost" size="sm" onClick={handleNext} className="px-2" disabled={selectedDate > new Date()}>›</Button>
            </motion.div>
          )}
        </motion.div>
      </div>

      {isFinishingConnection && (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="mb-6">
          <div className="bg-[hsl(var(--brand-primary))] text-white p-4 rounded-xl flex items-center gap-3 shadow-lg">
            <Loader2 className="animate-spin" size={24} />
            <div>
              <h3 className="font-semibold text-lg">Forbinder til bank...</h3>
              <p className="text-sm opacity-80">Henter dine konti og overfører transaktioner sikkert.</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Focused category detail bar */}
      <AnimatePresence>
        {focusedCategory && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <Card className="bg-[hsla(var(--brand-primary),0.05)] border-[hsla(var(--brand-primary),0.2)]">
              <CardContent className="py-4">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full" style={{ backgroundColor: getColorForCategory(focusedCategory.name, categories.findIndex(c => c.name === focusedCategory.name)) }} />
                    <div>
                      <p className="font-semibold text-lg text-[hsl(var(--text-primary))]">{focusedCategory.name}</p>
                      <p className="text-sm text-muted">{focusedPct}% af samlet forbrug</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-[hsl(var(--brand-primary))]">
                      {focusedCategory.value.toLocaleString('da-DK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr.
                    </p>
                    <button className="text-xs text-muted hover:underline mt-1" onClick={() => setFocusedCategory(null)}>
                      ← Luk
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sunburst + Legend */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-xl font-normal text-[hsl(var(--text-secondary))]">
              {t('dashboard.spending_breakdown') || 'Forbrugsoversigt'} — {periodLabel}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="w-full flex items-center justify-center" style={{ height: 420 }}>
                <Skeleton className="w-64 h-64 rounded-full" />
              </div>
            ) : categories.length === 0 ? (
              <div className="w-full flex items-center justify-center text-muted text-lg" style={{ height: 420 }}>
                Ingen udgifter at vise for denne periode.
              </div>
            ) : (
              <div className={`flex ${isMobile ? 'flex-col' : 'flex-row items-stretch'} gap-6 w-full`}>
                {/* Sunburst */}
                <div 
                  className={isMobile ? 'w-full relative' : 'flex-1 min-w-0 relative'} 
                  style={isMobile ? { height: 350 } : { aspectRatio: '1 / 1', maxHeight: 650, minHeight: 400 }}
                >
                  <div className="absolute inset-0">
                    <ReactEChartsCore
                      ref={chartRef}
                      echarts={echarts}
                      option={chartOption}
                      style={{ height: '100%', width: '100%' }}
                      onEvents={onChartEvents}
                      opts={{ renderer: 'canvas' }}
                    />
                  </div>
                </div>

                {/* Legend */}
                <div 
                  className={`${isMobile ? 'w-full' : 'w-80'} flex flex-col gap-1 ${isMobile ? '' : 'py-4 overflow-y-auto pr-2'}`} 
                  style={isMobile ? {} : { maxHeight: '100%' }}
                >
                  <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2 px-2">
                    Kategorier
                  </p>
                  {categories.map((cat, idx) => {
                    const pct = totalExpense > 0 ? ((cat.value / totalExpense) * 100).toFixed(1) : '0';
                    const isHovered = hoveredCategory === cat.name;
                    const isFocused = focusedCategory?.name === cat.name;
                    return (
                      <div
                        key={cat.name}
                        className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150 ${
                          isHovered || isFocused
                            ? 'bg-[hsl(var(--bg-tertiary))] scale-[1.02]'
                            : 'hover:bg-[hsl(var(--bg-tertiary))]'
                        }`}
                        onMouseEnter={() => handleLegendHover(cat.name)}
                        onMouseLeave={() => handleLegendLeave(cat.name)}
                        onClick={() => handleLegendClick(cat)}
                      >
                        <div
                          className="w-3 h-3 rounded-full flex-shrink-0"
                          style={{ backgroundColor: getColorForCategory(cat.name, idx) }}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate text-[hsl(var(--text-primary))]">
                            {cat.name}
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="text-sm font-semibold text-[hsl(var(--text-primary))]">
                            {cat.value.toLocaleString('da-DK', { maximumFractionDigits: 0 })} kr.
                          </p>
                          <p className="text-xs text-muted">{pct}%</p>
                        </div>
                      </div>
                    );
                  })}

                  {/* Total */}
                  <div className="flex items-center gap-3 px-3 py-2 mt-2 border-t border-[hsl(var(--border-color))]">
                    <div className="w-3 h-3" />
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-muted">I alt</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold text-[hsl(var(--text-primary))]">
                        {totalExpense.toLocaleString('da-DK', { maximumFractionDigits: 0 })} kr.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Transactions for Focused Category */}
      <AnimatePresence>
        {focusedCategory && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-xl font-normal text-[hsl(var(--text-secondary))]">
                  Transaktioner for {focusedCategory.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isLoadingFocusedTx ? (
                  <div className="space-y-4">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                ) : !focusedTxData?.transactions || focusedTxData.transactions.length === 0 ? (
                  <div className="text-center text-muted py-8">
                    Ingen transaktioner at vise.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {focusedTxData.transactions.map((tx: any) => (
                      <div 
                        key={tx.id} 
                        className="flex items-center justify-between p-3 bg-[hsl(var(--bg-tertiary))] rounded-lg cursor-pointer hover:bg-[hsl(var(--bg-secondary))] transition-colors"
                        onClick={() => setSelectedTransaction(tx)}
                      >
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate text-[hsl(var(--text-primary))]">{tx.description}</p>
                          <p className="text-xs text-muted">{formatTransactionDate(tx.booking_date, i18n.language)}</p>
                        </div>
                        <div className="text-right flex-shrink-0 pl-4">
                          <p className={`font-semibold ${tx.amount_minor > 0 ? "text-[hsl(var(--brand-success))]" : "text-[hsl(var(--text-primary))]"}`}>
                            {tx.amount_minor > 0 ? '+' : ''}{(tx.amount_minor / 100).toLocaleString('da-DK', { style: 'currency', currency: 'DKK' })}
                          </p>
                        </div>
                      </div>
                    ))}
                    {focusedTxData.transactions.length === 100 && (
                      <p className="text-center text-xs text-muted pt-2">Viser de seneste 100 transaktioner.</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
      
      <AnimatePresence>
        {selectedTransaction && (
          <TransactionDetailsSidebar
            transaction={selectedTransaction}
            onClose={() => setSelectedTransaction(null)}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
