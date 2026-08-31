import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from './Card';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ReferenceLine,
} from 'recharts';

export function BudgetResultView({ summary, currentYear, currentMonth, isCurrentYear }: any) {
  const { t } = useTranslation();

  const categoriesWithLabels = summary?.categories || [];

  const budgetedIncome = categoriesWithLabels.filter((c: any) => c.category_type === 'Income');
  const budgetedExpenses = categoriesWithLabels.filter((c: any) => c.category_type === 'Expense');

  const bills = categoriesWithLabels.filter(
    (c: any) => c.category_type === 'Expense' && c.expense_type === 'Fixed'
  );
  const consumption = categoriesWithLabels.filter(
    (c: any) => c.category_type === 'Expense' && c.expense_type === 'Variable'
  );

  // Accumulate monthly data
  const chartData = useMemo(() => {
    let cumulativeBudget = 0;
    let cumulativeActual = 0;
    const data = [];

    for (let m = 1; m <= 12; m++) {
      // Calculate this month's net result (Income - Expense)
      let monthBudgetNet = 0;
      let monthActualNet = 0;

      // Add Income
      budgetedIncome.forEach((c: any) => {
        const d = c.months.find((x: any) => x.month === m);
        if (d) {
          monthBudgetNet += d.budgeted_minor;
          monthActualNet += d.actual_minor;
        }
      });

      // Subtract bills and consumption
      const allExpenses = [...bills, ...consumption];
      allExpenses.forEach((c: any) => {
        const d = c.months.find((x: any) => x.month === m);
        if (d) {
          monthBudgetNet -= Math.abs(d.budgeted_minor);
          monthActualNet += d.actual_minor; // actuals for expenses are natively negative, so algebraic addition handles net refunds correctly
        }
      });

      cumulativeBudget += monthBudgetNet;

      let actualValue = null;
      if (!isCurrentYear || m <= currentMonth) {
        cumulativeActual += monthActualNet;
        actualValue = cumulativeActual / 100;
      }

      data.push({
        month: m,
        name: new Date(2026, m - 1, 1).toLocaleDateString('da-DK', { month: 'short' }),
        planlagt: cumulativeBudget / 100,
        faktisk: actualValue,
      });
    }
    return data;
  }, [budgetedIncome, bills, consumption, currentMonth, isCurrentYear]);

  // Calculate YTD actuals for the cards
  const ytdIncome =
    budgetedIncome.reduce(
      (sum: number, c: any) =>
        sum +
        c.months
          .filter((m: any) => m.month <= currentMonth)
          .reduce((s: number, m: any) => s + m.actual_minor, 0),
      0
    ) / 100;

  const ytdBills =
    -bills.reduce(
      (sum: number, c: any) =>
        sum +
        c.months
          .filter((m: any) => m.month <= currentMonth)
          .reduce((s: number, m: any) => s + m.actual_minor, 0),
      0
    ) / 100;

  const ytdConsumption =
    -consumption.reduce(
      (sum: number, c: any) =>
        sum +
        c.months
          .filter((m: any) => m.month <= currentMonth)
          .reduce((s: number, m: any) => s + m.actual_minor, 0),
      0
    ) / 100;

  // Calculate year budgets (using Math.abs to gracefully handle legacy positive budgets)
  const totalIncomeBudget =
    budgetedIncome.reduce((sum: number, c: any) => sum + Math.abs(c.total_budgeted_minor), 0) / 100;
  const totalBillsBudget =
    bills.reduce((sum: number, c: any) => sum + Math.abs(c.total_budgeted_minor), 0) / 100;
  const totalConsumptionBudget =
    consumption.reduce((sum: number, c: any) => sum + Math.abs(c.total_budgeted_minor), 0) / 100;

  // Calculate averages per month (up to 12)
  const avgIncome = totalIncomeBudget / 12;
  const avgBills = totalBillsBudget / 12;
  const avgDisposable = avgIncome - avgBills;
  const avgConsumption = totalConsumptionBudget / 12;
  const avgResult = avgDisposable - avgConsumption;

  // Calculate YTD budgets for the cards
  const ytdIncomeBudget =
    budgetedIncome.reduce(
      (sum: number, c: any) =>
        sum +
        c.months
          .filter((m: any) => m.month <= currentMonth)
          .reduce((s: number, m: any) => s + Math.abs(m.budgeted_minor), 0),
      0
    ) / 100;
  const ytdBillsBudget =
    bills.reduce(
      (sum: number, c: any) =>
        sum +
        c.months
          .filter((m: any) => m.month <= currentMonth)
          .reduce((s: number, m: any) => s + Math.abs(m.budgeted_minor), 0),
      0
    ) / 100;
  const ytdConsumptionBudget =
    consumption.reduce(
      (sum: number, c: any) =>
        sum +
        c.months
          .filter((m: any) => m.month <= currentMonth)
          .reduce((s: number, m: any) => s + Math.abs(m.budgeted_minor), 0),
      0
    ) / 100;

  // Current balance (actual)
  const currentActualBalance = chartData.reduce(
    (acc, curr) => (curr.faktisk !== null ? curr.faktisk : acc),
    0
  );

  // Final predicted balance (Prognosis = YTD Actual + Remaining Budget)
  const remainingIncomeBudget = totalIncomeBudget - ytdIncomeBudget;
  const remainingBillsBudget = totalBillsBudget - ytdBillsBudget;
  const remainingConsumptionBudget = totalConsumptionBudget - ytdConsumptionBudget;
  const projectedBalance =
    currentActualBalance +
    remainingIncomeBudget -
    (remainingBillsBudget + remainingConsumptionBudget);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[hsl(var(--bg-secondary))] p-3 border border-[hsl(var(--border-color))] rounded-lg shadow-xl">
          <p className="font-medium mb-2 capitalize">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ color: entry.color }} className="text-sm font-medium">
              {entry.name === 'planlagt'
                ? t('budgets.planned_balance')
                : t('budgets.actual_balance')}
              : {entry.value.toLocaleString('da-DK')} kr.
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  const getStatusText = (actual: number, planned: number, inverted: boolean = false) => {
    const diff = actual - planned;
    if (diff === 0) return t('budgets.exactly_as_planned');
    const isMore = diff > 0;

    // For expenses: more is bad, less is good. (inverted = false)
    // For income: more is good, less is bad. (inverted = true)
    return (
      <span
        className={
          isMore
            ? inverted
              ? 'text-green-500'
              : 'text-[hsl(var(--brand-danger))]'
            : inverted
              ? 'text-[hsl(var(--brand-danger))]'
              : 'text-green-500'
        }
      >
        {isMore ? t('budgets.more_than_planned') : t('budgets.less_than_planned')}
      </span>
    );
  };

  const currentMonthName = new Date(currentYear, currentMonth - 1, 1).toLocaleDateString('da-DK', {
    month: 'long',
  });

  return (
    <div className="flex flex-col xl:flex-row gap-6 mt-6">
      <div className="flex-1 space-y-6">
        <div>
          <h2 className="text-2xl font-light text-[hsl(var(--text-primary))]">
            {t('budgets.result_for', { year: currentYear })}
          </h2>
          <p className="text-muted">
            {t('budgets.balance_end_of', { month: currentMonthName })}{' '}
            <span className="font-bold text-[hsl(var(--text-primary))]">
              {currentActualBalance.toLocaleString('da-DK')} kr.
            </span>
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-[hsl(var(--bg-secondary))] border-none shadow-sm">
            <CardContent className="p-4 flex flex-col items-center justify-center text-center h-full">
              <span className="text-sm text-muted mb-2">
                {t('budgets.balance_ultimo', { month: currentMonthName })}
              </span>
              <span className="text-xl font-bold mb-1">
                {currentActualBalance.toLocaleString('da-DK')} kr
              </span>
              <span className="text-xs font-medium">
                {getStatusText(
                  currentActualBalance,
                  chartData[currentMonth - 1]?.planlagt || 0,
                  true
                )}
              </span>
            </CardContent>
          </Card>
          <Card className="border-none shadow-sm">
            <CardContent className="p-4 flex flex-col items-center justify-center text-center h-full">
              <span className="text-sm text-muted mb-2">{t('budgets.income_ytd')}</span>
              <span className="text-xl font-bold mb-1">{ytdIncome.toLocaleString('da-DK')} kr</span>
              <span className="text-xs font-medium">
                {getStatusText(ytdIncome, ytdIncomeBudget, true)}
              </span>
            </CardContent>
          </Card>
          <Card className="border-none shadow-sm">
            <CardContent className="p-4 flex flex-col items-center justify-center text-center h-full">
              <span className="text-sm text-muted mb-2">{t('budgets.bills_ytd')}</span>
              <span className="text-xl font-bold mb-1">{ytdBills.toLocaleString('da-DK')} kr</span>
              <span className="text-xs font-medium">{getStatusText(ytdBills, ytdBillsBudget)}</span>
            </CardContent>
          </Card>
          <Card className="border-none shadow-sm">
            <CardContent className="p-4 flex flex-col items-center justify-center text-center h-full">
              <span className="text-sm text-muted mb-2">{t('budgets.consumption_ytd')}</span>
              <span className="text-xl font-bold mb-1">
                {ytdConsumption.toLocaleString('da-DK')} kr
              </span>
              <span className="text-xs font-medium">
                {getStatusText(ytdConsumption, ytdConsumptionBudget)}
              </span>
            </CardContent>
          </Card>
        </div>

        <div className="pt-6">
          <h3 className="text-xl font-light mb-1">{t('budgets.budget_balance')}</h3>
          <p className="text-sm text-muted mb-6">{t('budgets.budget_balance_desc')}</p>

          <div className="h-[400px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
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
                />
                <YAxis
                  stroke="hsl(var(--text-secondary))"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(val) => `${val.toLocaleString('da-DK')}`}
                  width={80}
                />
                <RechartsTooltip
                  content={<CustomTooltip />}
                  cursor={{
                    stroke: 'hsl(var(--border-color))',
                    strokeWidth: 1,
                    strokeDasharray: '5 5',
                  }}
                />
                <ReferenceLine y={0} stroke="hsl(var(--border-color))" />
                <Line
                  type="monotone"
                  dataKey="planlagt"
                  stroke="hsl(var(--text-secondary))"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={{ r: 4, fill: 'hsl(var(--bg-primary))', strokeWidth: 2 }}
                  activeDot={{ r: 6 }}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="faktisk"
                  stroke="hsl(var(--brand-primary))"
                  strokeWidth={3}
                  dot={{ r: 4, fill: 'hsl(var(--bg-primary))', strokeWidth: 2 }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="xl:w-80 space-y-6">
        <Card className="bg-[hsl(var(--bg-secondary))] border-none text-center pt-6">
          <CardContent className="flex flex-col items-center">
            <h3 className="text-xl font-light mb-6">
              {t('budgets.my_budget_year', { year: currentYear })}
            </h3>

            {/* Simple CSS Gauge */}
            <div className="relative w-48 h-24 overflow-hidden mb-2">
              <div className="absolute top-0 left-0 w-48 h-48 rounded-full border-[24px] border-l-[hsl(var(--brand-danger))] border-t-[hsl(var(--brand-danger))] border-r-green-500 border-b-green-500 transform -rotate-45"></div>
              <div
                className="absolute bottom-0 left-1/2 w-4 h-24 bg-[hsl(var(--text-primary))] origin-bottom transform -translate-x-1/2 rotate-45 rounded-full z-10 transition-transform duration-1000"
                style={{
                  transform: `translateX(-50%) rotate(${projectedBalance >= 0 ? '60deg' : '-60deg'})`,
                }}
              ></div>
              <div className="absolute bottom-[-10px] left-1/2 w-6 h-6 bg-[hsl(var(--text-primary))] rounded-full transform -translate-x-1/2 z-20"></div>
            </div>
            <div className="flex justify-between w-48 text-xs font-bold text-muted tracking-wider mb-6">
              <span>{t('budgets.debt')}</span>
              <span>{t('budgets.savings')}</span>
            </div>

            <div className="flex flex-col items-center border-t border-[hsl(var(--border-color))] pt-6 w-full">
              <span className="text-xs font-bold text-muted uppercase tracking-wider mb-2">
                {t('budgets.final_balance_forecast', { year: currentYear })}
              </span>
              <span className="text-3xl font-bold">
                {projectedBalance.toLocaleString('da-DK')} kr.
              </span>
              <span className="text-xs text-muted mt-1">
                {t('budgets.budget_forecast')} {projectedBalance.toLocaleString('da-DK')}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[hsl(var(--bg-secondary))] border-none">
          <CardContent className="p-6">
            <h3 className="font-medium mb-4 text-lg">{t('budgets.budget_avg_month')}</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted">{t('budgets.income')}</span>
                <span className="font-medium">
                  {Math.round(avgIncome).toLocaleString('da-DK')} kr
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">{t('budgets.bills')}</span>
                <span className="font-medium">
                  {Math.round(avgBills).toLocaleString('da-DK')} kr
                </span>
              </div>
              <div className="flex justify-between pt-2 border-t border-[hsl(var(--border-color))]">
                <span className="text-muted">{t('budgets.disposable_amount')}</span>
                <span className="font-bold text-lg">
                  {Math.round(avgDisposable).toLocaleString('da-DK')} kr
                </span>
              </div>
              <div className="flex justify-between pt-2">
                <span className="text-muted">{t('budgets.consumption')}</span>
                <span className="font-medium text-[hsl(var(--brand-danger))]">
                  -{Math.round(avgConsumption).toLocaleString('da-DK')} kr
                </span>
              </div>
              <div className="flex justify-between pt-2 border-t border-[hsl(var(--border-color))] font-bold text-green-500">
                <span>{t('budgets.result')}</span>
                <span>{Math.round(avgResult).toLocaleString('da-DK')} kr</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
