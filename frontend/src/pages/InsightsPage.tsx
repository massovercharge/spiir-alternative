import React, { useState, useMemo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import {
  useInsightsSunburst,
  useIncomeExpenseSeries,
  useCategoryDrilldown,
  useInsightsAverages,
} from '../api/client';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Skeleton } from '../components/ui/Skeleton';
import { PeriodSelector } from '../components/ui/PeriodSelector';
import { Button } from '../components/ui/Button';
import { X, TrendingUp, TrendingDown, LayoutDashboard, PieChart } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  ComposedChart,
} from 'recharts';

function CategoryDrilldownView({
  category,
  year,
  onClose,
  isMobile,
}: {
  category: string;
  year: number;
  onClose: () => void;
  isMobile: boolean;
}) {
  const { data, isLoading } = useCategoryDrilldown(category, year);

  if (isLoading) return <Skeleton className="w-full h-full rounded-xl" />;

  const DrilldownTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const monthData = data?.monthly_data.find((m: any) => m.month === label);

      return (
        <div className="bg-[hsl(var(--bg-secondary))] p-4 border border-[hsl(var(--border-color))] rounded-lg shadow-xl w-72 z-50">
          <p className="font-medium mb-2 text-[hsl(var(--text-primary))]">
            {new Date(label).toLocaleDateString('da-DK', { month: 'long', year: 'numeric' })}
          </p>
          <p className="text-lg font-bold text-[hsl(var(--brand-primary))] mb-4">
            {(payload[0].value / 100).toLocaleString('da-DK')} kr.
          </p>

          {monthData && monthData.top_transactions.length > 0 && (
            <div className="space-y-2 mt-2 pt-3 border-t border-[hsl(var(--border-color))]">
              <p className="text-xs text-muted font-semibold uppercase tracking-wider mb-2">
                Største poster
              </p>
              {monthData.top_transactions.map((tx: any, idx: number) => (
                <div key={idx} className="flex justify-between items-center text-sm">
                  <span className="truncate w-2/3 pr-2" title={tx.payee}>
                    {idx + 1}. {tx.payee}
                  </span>
                  <span className="font-medium w-1/3 text-right">
                    {(Math.abs(tx.amount_minor) / 100).toLocaleString('da-DK')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  const formattedData =
    data?.monthly_data.map((m: any) => ({
      name: m.month,
      value: Math.abs(m.total_amount_minor),
    })) || [];

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="h-full"
    >
      <Card className="h-full border-[hsl(var(--brand-primary))] border-2 shadow-lg">
        <CardHeader className="flex flex-row items-start justify-between pb-2 relative pr-12">
          <div>
            <CardTitle className="flex items-center gap-2 text-xl">
              Detaljer for <span className="text-[hsl(var(--brand-primary))]">{category}</span>
            </CardTitle>
            <p className="text-sm text-muted mt-1">Månedlig udvikling i {year}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="absolute top-4 right-4 rounded-full w-10 h-10 p-0 flex items-center justify-center text-[hsl(var(--text-secondary))] hover:bg-[hsla(var(--brand-danger),0.1)] hover:text-[hsl(var(--brand-danger))] transition-colors"
          >
            <X size={28} strokeWidth={2.5} />
          </Button>
        </CardHeader>
        <CardContent className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={formattedData}
              margin={{ top: 20, right: 30, left: isMobile ? -15 : 10, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="hsl(var(--border-color))"
              />
              <XAxis
                dataKey="name"
                stroke="hsl(var(--text-secondary))"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={(val) =>
                  new Date(val).toLocaleDateString('da-DK', { month: 'short' })
                }
              />
              <YAxis
                stroke="hsl(var(--text-secondary))"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${(value / 100).toLocaleString('da-DK')}`}
                width={isMobile ? 45 : 70}
              />
              <RechartsTooltip
                content={<DrilldownTooltip />}
                cursor={{
                  stroke: 'hsl(var(--border-color))',
                  strokeWidth: 1,
                  strokeDasharray: '5 5',
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="hsl(var(--brand-primary))"
                strokeWidth={4}
                dot={{
                  r: 4,
                  fill: 'hsl(var(--brand-primary))',
                  strokeWidth: 2,
                  stroke: 'hsl(var(--bg-primary))',
                }}
                activeDot={{ r: 8, strokeWidth: 0 }}
                animationDuration={1000}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function InsightsPage() {
  const { t } = useTranslation();

  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const year = selectedDate.getFullYear();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  type TabType = 'overblik' | 'udgifter' | 'indkomst';
  const [activeTab, setActiveTab] = useState<TabType>('overblik');

  type ExpenseFilterType = 'Alle' | 'Fixed' | 'Variable';
  const [expenseFilter, setExpenseFilter] = useState<ExpenseFilterType>('Alle');

  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Fetch averages
  const { data: averages, isLoading: isLoadingAvg } = useInsightsAverages(year);

  // Fetch series
  const { data: trendData, isLoading: isLoadingTrend } = useIncomeExpenseSeries(year);

  // Fetch sunburst based on active tab and filter
  let sunburstFilterType: string | undefined = undefined;
  if (activeTab === 'indkomst') {
    sunburstFilterType = 'Income';
  } else if (activeTab === 'udgifter' && expenseFilter !== 'Alle') {
    sunburstFilterType = expenseFilter;
  }

  const { data: sunburstData, isLoading: isLoadingSunburst } = useInsightsSunburst({
    year,
    filterType: sunburstFilterType,
  });

  // Reset category selection when changing tabs
  useEffect(() => {
    setSelectedCategory(null);
  }, [activeTab, expenseFilter]);

  // Formatted data for charts
  const topCategories = useMemo(() => {
    if (!sunburstData || !sunburstData.labels) return [];
    const { labels, parents, values } = sunburstData;

    const categories: { name: string; value: number }[] = [];

    labels.forEach((label: string, i: number) => {
      if (parents[i] === 'Total') {
        const val = parseFloat(values[i]);
        // If we are on income tab, we want income categories.
        // Sunburst backend handles the filtering, we just take the top level items.
        if (!isNaN(val) && val > 0 && label !== 'Indkomst' && label !== 'Udgifter') {
          categories.push({ name: label, value: val });
        }
      }
    });

    return categories.sort((a, b) => b.value - a.value).slice(0, 10);
  }, [sunburstData]);

  const formattedTrendData = useMemo(() => {
    if (!trendData || !trendData.series) return [];

    const yearMonths = Array.from(
      { length: 12 },
      (_, i) => `${year}-${String(i + 1).padStart(2, '0')}`
    );

    return yearMonths.map((monthStr) => {
      const found = trendData.series.find((item: any) => item.month === monthStr);
      const indkomst = found ? Number(found.income) : 0;
      const udgifter = found ? Math.abs(Number(found.expense)) : 0;

      return {
        name: monthStr,
        [t('dashboard.income') || 'Indkomst']: indkomst,
        ['Regninger']: found ? Math.abs(Number(found.expense_fixed)) : 0,
        ['Forbrug']: found ? Math.abs(Number(found.expense_variable)) : 0,
        ['Opsparing']: found ? Math.abs(Number(found.savings)) : 0,
        ['Udgifter']: udgifter,
        ['NegativeUdgifter']: -udgifter,
        ['Resultat']: found ? Number(found.net) : 0,
      };
    });
  }, [trendData, t, year]);

  const BarTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[hsl(var(--bg-secondary))] p-3 border border-[hsl(var(--border-color))] rounded-lg shadow-xl pointer-events-none z-50 relative">
          <p className="font-medium mb-1 text-[hsl(var(--text-primary))]">{label}</p>
          <p className="text-sm font-semibold" style={{ color: payload[0].fill }}>
            {payload[0].value.toLocaleString('da-DK')} kr.
          </p>
          <p className="text-xs text-muted mt-2">Klik for at se detaljer</p>
        </div>
      );
    }
    return null;
  };

  const LineTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[hsl(var(--bg-secondary))] p-3 border border-[hsl(var(--border-color))] rounded-lg shadow-xl pointer-events-none z-50 relative">
          <p className="font-medium mb-2">
            {new Date(label).toLocaleDateString('da-DK', { month: 'long', year: 'numeric' })}
          </p>
          {payload.map((entry: any, index: number) => {
            // Expenses are drawn as negative bars, but should display as positive amounts in the tooltip
            const displayValue = entry.name === 'Udgifter' ? Math.abs(entry.value) : entry.value;
            return (
              <p key={index} style={{ color: entry.color }} className="text-sm font-medium">
                {entry.name}: {displayValue.toLocaleString('da-DK')} kr.
              </p>
            );
          })}
        </div>
      );
    }
    return null;
  };

  // ----- TABS -----

  const renderOverblik = () => {
    const netAvg = parseFloat(averages?.net_avg || '0');
    const netTotal = parseFloat(averages?.net_total || '0');
    const savingsTotal = parseFloat(averages?.savings_total || '0');
    const netWithSavings = netTotal + savingsTotal; // Since savings are already treated as expenses (subtracted), adding them back gives the 'with savings' result. Wait, if savings are separated from expenses, then Resultat = Income - Expenses (excluding savings).
    // Let's use the explicit fields from our backend:
    const incomeTotal = averages?.income_total || '0';
    const regningerTotal = averages?.expense_fixed_total || '0';
    const forbrugTotal = averages?.expense_variable_total || '0';

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="space-y-6"
      >
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main Content (Charts) */}
          <div className="lg:col-span-3 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-2xl font-normal text-[hsl(var(--text-secondary))]">
                  Indkomst og udgifter
                </CardTitle>
              </CardHeader>
              <CardContent className="h-[400px]">
                {isLoadingTrend ? (
                  <Skeleton className="w-full h-full rounded-xl" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={formattedTrendData}
                      margin={{ top: 20, right: 30, left: isMobile ? -15 : 20, bottom: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="hsl(var(--border-color))"
                      />
                      <XAxis
                        dataKey="name"
                        stroke="hsl(var(--text-secondary))"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(val) =>
                          new Date(val).toLocaleDateString('da-DK', { month: 'short' })
                        }
                      />
                      <YAxis
                        stroke="hsl(var(--text-secondary))"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => `${value}`}
                        width={isMobile ? 45 : 60}
                      />
                      <RechartsTooltip content={<LineTooltip />} />

                      {/* Income bars going up */}
                      <Bar
                        dataKey="Indkomst"
                        fill="hsl(var(--brand-success))"
                        radius={[4, 4, 0, 0]}
                        maxBarSize={40}
                      />
                      {/* Expense bars going down (NegativeUdgifter) */}
                      <Bar
                        dataKey="NegativeUdgifter"
                        name="Udgifter"
                        fill="hsl(var(--brand-warning))"
                        radius={[0, 0, 4, 4]}
                        maxBarSize={40}
                      />

                      <Line
                        type="monotone"
                        dataKey="Resultat"
                        stroke="hsl(var(--text-primary))"
                        strokeWidth={3}
                        dot={{ r: 4, fill: 'hsl(var(--bg-primary))', strokeWidth: 2 }}
                        activeDot={{ r: 6 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <div className="h-[480px]">
              <AnimatePresence mode="wait">
                {selectedCategory ? (
                  <CategoryDrilldownView
                    key="drilldown"
                    category={selectedCategory}
                    year={year}
                    onClose={() => setSelectedCategory(null)}
                    isMobile={isMobile}
                  />
                ) : (
                  <motion.div
                    key="topexpenses"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="h-full"
                  >
                    <Card className="h-full border-none shadow-none bg-transparent">
                      <CardHeader className="px-0">
                        <CardTitle className="text-xl font-normal text-[hsl(var(--text-secondary))]">
                          Hvad har jeg brugt mine penge på?
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="h-[400px] px-0">
                        {isLoadingSunburst ? (
                          <Skeleton className="w-full h-full rounded-xl" />
                        ) : topCategories.length === 0 ? (
                          <div className="h-full flex items-center justify-center text-muted">
                            Ingen udgifter at vise.
                          </div>
                        ) : (
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                              data={topCategories}
                              layout="vertical"
                              margin={{ top: 5, right: 30, left: 5, bottom: 5 }}
                            >
                              <CartesianGrid
                                strokeDasharray="3 3"
                                horizontal={true}
                                vertical={false}
                                stroke="hsl(var(--border-color))"
                              />
                              <XAxis type="number" hide />
                              <YAxis
                                dataKey="name"
                                type="category"
                                axisLine={false}
                                tickLine={false}
                                tick={{ fill: 'hsl(var(--text-primary))', fontSize: 12 }}
                                width={isMobile ? 80 : 160}
                              />
                              <RechartsTooltip
                                content={<BarTooltip />}
                                cursor={{ fill: 'hsl(var(--bg-tertiary))' }}
                              />
                              <Bar
                                dataKey="value"
                                radius={[0, 4, 4, 0]}
                                maxBarSize={30}
                                onClick={(data) => {
                                  if (data && data.name) setSelectedCategory(data.name);
                                }}
                                className="cursor-pointer transition-opacity hover:opacity-80"
                              >
                                {topCategories.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill="hsl(var(--brand-warning))" />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Right Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-[hsl(var(--bg-secondary))] p-6 rounded-xl border border-[hsl(var(--border-color))] sticky top-6 space-y-8">
              <div className="text-center">
                <p className="text-lg text-[hsl(var(--text-secondary))] font-medium mb-4">
                  Sidste 12 mdr.
                </p>
                <p className="text-xs font-semibold text-muted tracking-wider uppercase mb-2">
                  Resultat
                </p>
                <h2 className="text-3xl font-bold text-[hsl(var(--text-primary))]">
                  {isLoadingAvg ? (
                    <Skeleton className="h-10 w-32 mx-auto" />
                  ) : (
                    `${parseFloat(averages?.net_avg || '0').toLocaleString('da-DK')} kr`
                  )}
                </h2>
                <p className="text-sm text-muted mt-1">gns/md</p>
              </div>

              <div className="space-y-3 pt-6 border-t border-[hsl(var(--border-color))]">
                <div className="flex justify-between text-sm">
                  <span className="text-[hsl(var(--text-secondary))]">Indkomst</span>
                  <span className="font-medium">
                    {parseFloat(incomeTotal).toLocaleString('da-DK')} kr
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[hsl(var(--text-secondary))]">Regninger</span>
                  <span className="font-medium text-[hsl(var(--text-primary))]">
                    -{parseFloat(regningerTotal).toLocaleString('da-DK')} kr
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[hsl(var(--text-secondary))]">Forbrug</span>
                  <span className="font-medium text-[hsl(var(--text-primary))]">
                    -{parseFloat(forbrugTotal).toLocaleString('da-DK')} kr
                  </span>
                </div>
                <div className="flex justify-between font-semibold pt-3 border-t border-[hsl(var(--border-color))]">
                  <span className="text-[hsl(var(--text-primary))]">Resultat</span>
                  <span className="text-[hsl(var(--brand-success))]">
                    {netTotal.toLocaleString('da-DK')} kr
                  </span>
                </div>
              </div>

              <div className="pt-6">
                <div className="bg-[hsl(var(--bg-primary))] rounded-lg p-4 border border-[hsl(var(--border-color))] text-center shadow-sm">
                  <p className="text-xs font-semibold text-muted tracking-wider uppercase mb-1">
                    Opsparing
                  </p>
                  <p className="text-lg font-bold text-[hsl(var(--text-primary))]">
                    {savingsTotal.toLocaleString('da-DK')} kr
                  </p>
                </div>
                <div className="mt-4 text-center">
                  <p className="text-[10px] font-semibold text-muted tracking-wider uppercase mb-1">
                    Resultat m. opsparing
                  </p>
                  <p className="font-medium text-[hsl(var(--text-primary))]">
                    {netWithSavings.toLocaleString('da-DK')} kr
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    );
  };

  const renderUdgifter = () => {
    // Determine which line to show based on filter
    let dataKey = 'Udgifter';
    let lineColor = 'hsl(var(--brand-danger))';
    if (expenseFilter === 'Fixed') {
      dataKey = 'Regninger';
      lineColor = 'hsl(var(--brand-warning))';
    } else if (expenseFilter === 'Variable') {
      dataKey = 'Forbrug';
    }

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="space-y-6"
      >
        {/* Filter */}
        <div className="flex bg-[hsl(var(--bg-secondary))] p-1 rounded-lg w-fit">
          <button
            onClick={() => setExpenseFilter('Alle')}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${expenseFilter === 'Alle' ? 'bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))] shadow-sm' : 'text-muted hover:text-[hsl(var(--text-primary))]'}`}
          >
            Alle udgifter
          </button>
          <button
            onClick={() => setExpenseFilter('Variable')}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${expenseFilter === 'Variable' ? 'bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))] shadow-sm' : 'text-muted hover:text-[hsl(var(--text-primary))]'}`}
          >
            Forbrug
          </button>
          <button
            onClick={() => setExpenseFilter('Fixed')}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${expenseFilter === 'Fixed' ? 'bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))] shadow-sm' : 'text-muted hover:text-[hsl(var(--text-primary))]'}`}
          >
            Regninger
          </button>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Expense Trend */}
          <Card className="h-[480px]">
            <CardHeader>
              <CardTitle>Mine udgifter over tid</CardTitle>
            </CardHeader>
            <CardContent className="h-[400px]">
              {isLoadingTrend ? (
                <Skeleton className="w-full h-full rounded-xl" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={formattedTrendData}
                    margin={{ top: 20, right: 30, left: isMobile ? -15 : 20, bottom: 5 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="hsl(var(--border-color))"
                    />
                    <XAxis
                      dataKey="name"
                      stroke="hsl(var(--text-secondary))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(val) =>
                        new Date(val).toLocaleDateString('da-DK', { month: 'short' })
                      }
                    />
                    <YAxis
                      stroke="hsl(var(--text-secondary))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `${value}`}
                      width={isMobile ? 45 : 60}
                    />
                    <RechartsTooltip content={<LineTooltip />} />
                    <Line
                      type="monotone"
                      dataKey={dataKey}
                      stroke={lineColor}
                      strokeWidth={3}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Top Expenses */}
          <div className="h-[480px]">
            <AnimatePresence mode="wait">
              {selectedCategory ? (
                <CategoryDrilldownView
                  key="drilldown"
                  category={selectedCategory}
                  year={year}
                  onClose={() => setSelectedCategory(null)}
                  isMobile={isMobile}
                />
              ) : (
                <motion.div
                  key="topexpenses"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="h-full"
                >
                  <Card className="h-full">
                    <CardHeader>
                      <CardTitle>Hvad har jeg brugt mine penge på?</CardTitle>
                    </CardHeader>
                    <CardContent className="h-[400px]">
                      {isLoadingSunburst ? (
                        <Skeleton className="w-full h-full rounded-xl" />
                      ) : topCategories.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-muted">
                          Ingen udgifter at vise.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={topCategories}
                            layout="vertical"
                            margin={{ top: 5, right: 30, left: isMobile ? 5 : 20, bottom: 5 }}
                          >
                            <CartesianGrid
                              strokeDasharray="3 3"
                              horizontal={true}
                              vertical={false}
                              stroke="hsl(var(--border-color))"
                            />
                            <XAxis type="number" hide />
                            <YAxis
                              dataKey="name"
                              type="category"
                              axisLine={false}
                              tickLine={false}
                              tick={{ fill: 'hsl(var(--text-primary))', fontSize: 12 }}
                              width={isMobile ? 80 : 120}
                            />
                            <RechartsTooltip
                              content={<BarTooltip />}
                              cursor={{ fill: 'hsl(var(--bg-tertiary))' }}
                            />
                            <Bar
                              dataKey="value"
                              radius={[0, 4, 4, 0]}
                              maxBarSize={40}
                              onClick={(data) => {
                                if (data && data.name) setSelectedCategory(data.name);
                              }}
                              className="cursor-pointer transition-opacity hover:opacity-80"
                            >
                              {topCategories.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={lineColor} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.div>
    );
  };

  const renderIndkomst = () => {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="space-y-6"
      >
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card className="h-[480px]">
            <CardHeader>
              <CardTitle>Min indkomst over tid</CardTitle>
            </CardHeader>
            <CardContent className="h-[400px]">
              {isLoadingTrend ? (
                <Skeleton className="w-full h-full rounded-xl" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={formattedTrendData}
                    margin={{ top: 20, right: 30, left: isMobile ? -15 : 20, bottom: 5 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="hsl(var(--border-color))"
                    />
                    <XAxis
                      dataKey="name"
                      stroke="hsl(var(--text-secondary))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(val) =>
                        new Date(val).toLocaleDateString('da-DK', { month: 'short' })
                      }
                    />
                    <YAxis
                      stroke="hsl(var(--text-secondary))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `${value}`}
                      width={isMobile ? 45 : 60}
                    />
                    <RechartsTooltip content={<LineTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="Indkomst"
                      stroke="hsl(var(--brand-success))"
                      strokeWidth={3}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <div className="h-[480px]">
            <AnimatePresence mode="wait">
              {selectedCategory ? (
                <CategoryDrilldownView
                  key="drilldown"
                  category={selectedCategory}
                  year={year}
                  onClose={() => setSelectedCategory(null)}
                  isMobile={isMobile}
                />
              ) : (
                <motion.div
                  key="topincome"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="h-full"
                >
                  <Card className="h-full">
                    <CardHeader>
                      <CardTitle>Hvor kommer mine penge fra?</CardTitle>
                    </CardHeader>
                    <CardContent className="h-[400px]">
                      {isLoadingSunburst ? (
                        <Skeleton className="w-full h-full rounded-xl" />
                      ) : topCategories.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-muted">
                          Ingen indkomst at vise.
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={topCategories}
                            layout="vertical"
                            margin={{ top: 5, right: 30, left: isMobile ? 5 : 20, bottom: 5 }}
                          >
                            <CartesianGrid
                              strokeDasharray="3 3"
                              horizontal={true}
                              vertical={false}
                              stroke="hsl(var(--border-color))"
                            />
                            <XAxis type="number" hide />
                            <YAxis
                              dataKey="name"
                              type="category"
                              axisLine={false}
                              tickLine={false}
                              tick={{ fill: 'hsl(var(--text-primary))', fontSize: 12 }}
                              width={isMobile ? 80 : 120}
                            />
                            <RechartsTooltip
                              content={<BarTooltip />}
                              cursor={{ fill: 'hsl(var(--bg-tertiary))' }}
                            />
                            <Bar
                              dataKey="value"
                              radius={[0, 4, 4, 0]}
                              maxBarSize={40}
                              onClick={(data) => {
                                if (data && data.name) setSelectedCategory(data.name);
                              }}
                              className="cursor-pointer transition-opacity hover:opacity-80"
                            >
                              {topCategories.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill="hsl(var(--brand-success))" />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 pb-28 md:pb-8"
    >
      <div className="mb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <motion.h1
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="text-3xl font-bold text-[hsl(var(--text-primary))]"
          >
            {t('insights.title', 'Indblik')}
          </motion.h1>
          <motion.p
            initial={{ y: -5, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-muted mt-2"
          >
            Få dybere indsigt i din økonomi.
          </motion.p>
        </div>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
          <PeriodSelector
            mode="year"
            date={selectedDate}
            onChange={(d) => {
              setSelectedDate(d);
              setSelectedCategory(null);
            }}
          />
        </motion.div>
      </div>

      {/* Tabs */}
      <div className="border-b border-[hsl(var(--border-color))] mb-6">
        <nav className="-mb-px flex space-x-8 overflow-x-auto">
          <button
            onClick={() => setActiveTab('overblik')}
            className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
              activeTab === 'overblik'
                ? 'border-[hsl(var(--brand-primary))] text-[hsl(var(--brand-primary))]'
                : 'border-transparent text-muted hover:text-[hsl(var(--text-primary))] hover:border-[hsl(var(--border-color))]'
            }`}
          >
            <LayoutDashboard size={18} />
            Overblik
          </button>
          <button
            onClick={() => setActiveTab('udgifter')}
            className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
              activeTab === 'udgifter'
                ? 'border-[hsl(var(--brand-danger))] text-[hsl(var(--brand-danger))]'
                : 'border-transparent text-muted hover:text-[hsl(var(--text-primary))] hover:border-[hsl(var(--border-color))]'
            }`}
          >
            <TrendingDown size={18} />
            Udgifter
          </button>
          <button
            onClick={() => setActiveTab('indkomst')}
            className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
              activeTab === 'indkomst'
                ? 'border-[hsl(var(--brand-success))] text-[hsl(var(--brand-success))]'
                : 'border-transparent text-muted hover:text-[hsl(var(--text-primary))] hover:border-[hsl(var(--border-color))]'
            }`}
          >
            <TrendingUp size={18} />
            Indkomst
          </button>
        </nav>
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        {activeTab === 'overblik' && <motion.div key="overblik">{renderOverblik()}</motion.div>}
        {activeTab === 'udgifter' && <motion.div key="udgifter">{renderUdgifter()}</motion.div>}
        {activeTab === 'indkomst' && <motion.div key="indkomst">{renderIndkomst()}</motion.div>}
      </AnimatePresence>
    </motion.div>
  );
}
