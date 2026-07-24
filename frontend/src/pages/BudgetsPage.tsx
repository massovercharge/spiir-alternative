import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { motion, AnimatePresence } from 'framer-motion';
import { useBudgetsSummary, useGenerateBudgets } from '../api/client';
import { Skeleton } from '../components/ui/Skeleton';
import { PeriodSelector } from '../components/ui/PeriodSelector';
import { FileWarning, ChevronRight, Sparkles } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { BudgetDetailsSidebar } from '../components/ui/BudgetDetailsSidebar';
import { MonthGrid, MonthState } from '../components/ui/MonthGrid';
import { BudgetResultView } from '../components/ui/BudgetResultView';
import CategoryPicker from '../components/ui/CategoryPicker';

function getMonthStates(months: any[], currentMonth: number, isCurrentYear: boolean, isIncome: boolean = false): MonthState[] {
  return Array.from({ length: 12 }, (_, i) => {
    const monthNum = i + 1;
    // For current year, future months are inactive
    if (isCurrentYear && monthNum > currentMonth) return 'inactive';

    const mData = months?.find((m: any) => m.month === monthNum);
    if (!mData) return 'inactive';
    if (mData.budgeted_minor === 0 && mData.actual_minor === 0) return 'inactive';

    const actual = Math.abs(mData.actual_minor);
    const budgeted = Math.abs(mData.budgeted_minor);

    if (isIncome) {
      if (actual < budgeted && budgeted > 0) return 'over'; // Bad (Red)
      if (actual > 0 || budgeted > 0) return 'under'; // Good (Green)
    } else {
      if (actual > budgeted && budgeted > 0) return 'over'; // Bad (Red)
      if (actual > 0 || budgeted > 0) return 'under'; // Good (Green)
    }
    
    return 'inactive';
  });
}

function ProgressBarWithHistory({ category, currentMonth, isCurrentYear, t }: any) {
  const months = category.months || [];
  const currentMonthData = months.find((m: any) => m.month === currentMonth);
  
  const used = Math.abs(currentMonthData?.actual_minor || 0) / 100;
  const total = Math.abs(currentMonthData?.budgeted_minor || 0) / 100;
  
  const percentage = total > 0 ? Math.min((used / total) * 100, 100) : 100;
  const isIncome = category.category_type === 'Income';
  const isOver = isIncome ? (used < total && total > 0) : (used > total && total > 0);
  const remaining = isIncome ? used - total : total - used;

  const monthStates = getMonthStates(months, currentMonth, isCurrentYear, isIncome);
  // Show history only up to the PREVIOUS month for the grid, as the current month is the progress bar
  const historyStates = monthStates.slice(0, currentMonth - 1);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between items-end text-sm">
        <div className="flex items-center gap-4">
          <span className="font-medium capitalize">{category.label}</span>
          {historyStates.length > 0 && (
            <div className="hidden sm:block">
              <MonthGrid states={historyStates} showOnlyPassedMonths={true} />
            </div>
          )}
        </div>
        <div className="text-right flex flex-col">
          {remaining >= 0 ? (
            <span className="text-xs font-semibold text-green-500 uppercase tracking-wide">
              {t('budgets.remaining', 'Tilbage')}: {remaining.toLocaleString('da-DK')} kr.
            </span>
          ) : (
            <span className="text-xs font-semibold text-[hsl(var(--brand-danger))] uppercase tracking-wide">
              {t('budgets.over_budget', 'Overskredet')}: {Math.abs(remaining).toLocaleString('da-DK')} kr.
            </span>
          )}
          <span className="text-[10px] text-muted">
            {used.toLocaleString('da-DK')} / {total.toLocaleString('da-DK')}
          </span>
        </div>
      </div>
      <div className="h-2 w-full bg-[hsl(var(--bg-tertiary))] rounded-full overflow-hidden">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={`h-full rounded-full ${isOver ? 'bg-[hsl(var(--brand-danger))]' : 'bg-[hsl(var(--brand-primary))]'}`}
        />
      </div>
    </div>
  );
}

function FixedExpenseRow({ category, isCurrentYear, currentMonth }: any) {
  const avgMonth = (Math.abs(category.total_budgeted_minor) / 100) / 12;
  const isIncome = category.category_type === 'Income';
  const monthStates = getMonthStates(category.months || [], currentMonth, isCurrentYear, isIncome);

  return (
    <div className="flex justify-between items-center w-full">
      <div className="flex flex-col gap-1">
        <span className="font-medium capitalize text-sm">{category.label}</span>
        <span className="text-xs text-muted">{Math.round(avgMonth).toLocaleString('da-DK')} kr. / md</span>
      </div>
      <div className="hidden sm:block">
        <MonthGrid states={monthStates} />
      </div>
    </div>
  );
}

function RestenRow({ categories, isCurrentYear, currentMonth, t, onCategoryClick }: any) {
  const totalActual = categories.reduce((sum: number, c: any) => sum + Math.abs(c.total_actual_minor), 0) / 100;
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.5 }}
      onClick={() => onCategoryClick(categories[0])} // Clicking it opens the first unbudgeted cat, maybe we should open a combined view, but this is fine for now
      className="p-3 rounded-lg bg-[hsl(var(--bg-tertiary))] hover:bg-[hsl(var(--border-color))] cursor-pointer transition-colors group relative mt-4 border border-[hsl(var(--border-color))]"
    >
      <div className="pr-6">
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-end text-sm">
            <span className="font-medium">{t('budgets.unbudgeted_consumption')}</span>
            <div className="text-right flex flex-col">
              <span className="text-xs font-semibold text-[hsl(var(--brand-danger))] uppercase tracking-wide">
                -{totalActual.toLocaleString('da-DK')} kr.
              </span>
            </div>
          </div>
          <p className="text-xs text-muted">
            {categories.map((c:any) => c.label).slice(0, 3).join(', ')} {categories.length > 3 ? `+ ${categories.length - 3} ${t('budgets.more')}` : ''}
          </p>
        </div>
      </div>
      <div className="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
        <ChevronRight size={20} className="text-muted" />
      </div>
    </motion.div>
  );
}

function BudgetSection({ title, categories, type, isCurrentYear, currentMonth, t, onCategoryClick, unbudgetedCategories = [] }: any) {
  if ((!categories || categories.length === 0) && (!unbudgetedCategories || unbudgetedCategories.length === 0)) return null;

  return (
    <div className="space-y-1 pt-4">
      {categories.map((cat: any, index: number) => {
        return (
          <motion.div
            key={cat.category_id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => onCategoryClick(cat)}
            className="p-3 rounded-lg hover:bg-[hsl(var(--bg-tertiary))] cursor-pointer transition-colors group relative bg-[hsl(var(--bg-secondary))]"
          >
            <div className="pr-6">
              {type === 'variable' && isCurrentYear ? (
                <ProgressBarWithHistory category={cat} currentMonth={currentMonth} isCurrentYear={isCurrentYear} t={t} />
              ) : (
                <FixedExpenseRow category={cat} currentMonth={currentMonth} isCurrentYear={isCurrentYear} />
              )}
            </div>
            <div className="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
              <ChevronRight size={20} className="text-muted" />
            </div>
          </motion.div>
        );
      })}

      {type === 'variable' && unbudgetedCategories.length > 0 && (
        <RestenRow 
          categories={unbudgetedCategories} 
          isCurrentYear={isCurrentYear} 
          currentMonth={currentMonth} 
          t={t} 
          onCategoryClick={onCategoryClick} 
        />
      )}
    </div>
  );
}

type TabType = 'resultat' | 'indkomst' | 'regninger' | 'forbrug';

export default function BudgetsPage() {
  const { t } = useTranslation();
  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const [selectedCategory, setSelectedCategory] = useState<any | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('resultat');
  
  const currentYear = selectedDate.getFullYear();
  const actualCurrentYear = new Date().getFullYear();
  const isCurrentYear = currentYear === actualCurrentYear;
  const currentMonth = isCurrentYear ? new Date().getMonth() + 1 : 12;

  const { data: summary, isLoading } = useBudgetsSummary(currentYear);
  const generateBudgets = useGenerateBudgets();

  const categoriesWithLabels = summary?.categories?.map((c: any) => {
    const labelParts = c.category_id.split('|');
    const mainLabel = labelParts[0].charAt(0).toUpperCase() + labelParts[0].slice(1);
    const subLabel = labelParts[1] ? labelParts[1] : labelParts[0];
    return {
      ...c,
      label: labelParts[1] ? `${mainLabel} - ${subLabel}` : subLabel
    };
  }) || [];

  const hasData = (c: any) => Math.abs(c.total_budgeted_minor) > 0 || Math.abs(c.total_actual_minor) > 0;

  const allIncome = categoriesWithLabels.filter((c: any) => hasData(c) && c.category_type === 'Income');
  const allBillsRaw = categoriesWithLabels.filter((c: any) => hasData(c) && c.category_type === 'Expense' && c.expense_type === 'Fixed');
  const budgetedConsumption = categoriesWithLabels.filter((c: any) => c.total_budgeted_minor > 0 && c.category_type === 'Expense' && c.expense_type === 'Variable');
  

  
  const unbudgetedConsumption = categoriesWithLabels.filter((c: any) => 
    c.total_budgeted_minor === 0 && 
    c.category_type === 'Expense' && 
    c.expense_type === 'Variable' && 
    Math.abs(c.total_actual_minor) > 0
  ).sort((a: any, b: any) => Math.abs(b.total_actual_minor) - Math.abs(a.total_actual_minor));

  const TabButton = ({ id, label }: { id: TabType, label: string }) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`px-4 py-2 font-medium text-sm transition-colors relative shrink-0 ${
        activeTab === id ? 'text-[hsl(var(--text-primary))]' : 'text-muted hover:text-[hsl(var(--text-primary))]'
      }`}
    >
      {label}
      {activeTab === id && (
        <motion.div 
          layoutId="activeTabIndicator"
          className="absolute bottom-0 left-0 right-0 h-0.5 bg-[hsl(var(--brand-primary))]" 
          initial={false}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        />
      )}
    </button>
  );

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-4 md:p-8 max-w-6xl mx-auto space-y-6 pb-28 md:pb-8"
    >
      <div className="mb-4 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <motion.h1 
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="text-3xl font-bold text-[hsl(var(--text-primary))]"
          >
            {t('app.budgets')}
          </motion.h1>
          <motion.p 
            initial={{ y: -5, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-muted mt-2"
          >
            {t('budgets.description', { year: currentYear })}
          </motion.p>
        </div>
        <motion.div 
          initial={{ opacity: 0 }} 
          animate={{ opacity: 1 }} 
          transition={{ delay: 0.2 }}
          className="flex items-center gap-4"
        >
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => generateBudgets.mutate({ year: currentYear })} 
            disabled={generateBudgets.isPending}
            className="hidden md:flex gap-2"
          >
            <Sparkles size={16} />
            {t('budgets.generate', 'Autogenerér')}
          </Button>
          <PeriodSelector mode="year" date={selectedDate} onChange={setSelectedDate} />
        </motion.div>
      </div>

      {isLoading && (
        <Card>
          <CardHeader>
            <CardTitle>{t('common.loading', 'Indlæser...')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-8 pt-4">
            <div className="space-y-6">
              {[1, 2, 3].map(i => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                  <Skeleton className="h-2 w-full" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {!isLoading && summary?.categories?.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center text-muted">
            <FileWarning size={48} className="mb-4 text-[hsl(var(--text-secondary))] opacity-50" />
            <p className="mb-4">{t('budgets.no_budgets', 'Du har ikke oprettet nogen budgetter endnu.')}</p>
            <Button onClick={() => generateBudgets.mutate({ year: currentYear })} disabled={generateBudgets.isPending}>
              {generateBudgets.isPending ? t('common.loading', 'Indlæser...') : t('budgets.generate', 'Autogenerer budget ud fra historik')}
            </Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && summary?.categories?.length > 0 && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center gap-2 border-b border-[hsl(var(--border-color))] pb-[-2px] overflow-x-auto whitespace-nowrap scrollbar-none">
            <TabButton id="resultat" label={t('budgets.tab_result')} />
            <TabButton id="indkomst" label={t('budgets.tab_income')} />
            <TabButton id="regninger" label={t('budgets.tab_bills')} />
            <TabButton id="forbrug" label={t('budgets.tab_consumption')} />
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              {activeTab === 'resultat' && (
                <BudgetResultView 
                  summary={summary}
                  currentYear={currentYear}
                  currentMonth={currentMonth}
                  isCurrentYear={isCurrentYear}
                />
              )}
              
              {activeTab === 'indkomst' && (
                <div className="space-y-4">
                  <BudgetSection 
                    title={t('budgets.income_title', 'Mit budget for indkomst')} 
                    categories={allIncome} 
                    type="fixed"
                    isCurrentYear={isCurrentYear}
                    currentMonth={currentMonth}
                    t={t}
                    onCategoryClick={setSelectedCategory}
                  />
                  <div className="flex justify-center pt-4 pb-8">
                    <CategoryPicker 
                      placeholder={t('budgets.add_category', '+ Tilføj kategori')}
                      onSelect={(id) => setSelectedCategory({ category_id: id, category_type: 'Income', expense_type: 'Fixed', months: [] })}
                    />
                  </div>
                </div>
              )}

              {activeTab === 'regninger' && (
                <div className="space-y-4">
                  <BudgetSection 
                    title={t('budgets.bills_title', 'Mit budget for regninger i {{year}}', { year: currentYear })} 
                    categories={allBillsRaw} 
                    type="fixed" 
                    isCurrentYear={isCurrentYear} 
                    currentMonth={currentMonth} 
                    t={t}
                    onCategoryClick={setSelectedCategory} 
                  />
                  <div className="flex justify-center pt-4 pb-8">
                    <CategoryPicker 
                      placeholder={t('budgets.add_category', '+ Tilføj kategori')}
                      onSelect={(id) => setSelectedCategory({ category_id: id, category_type: 'Expense', expense_type: 'Fixed', months: [] })}
                    />
                  </div>
                </div>
              )}

              {activeTab === 'forbrug' && (
                <div className="space-y-4">
                  <BudgetSection 
                    title={t('budgets.consumption_title', 'Mit budget for forbrug')} 
                    categories={budgetedConsumption} 
                    unbudgetedCategories={unbudgetedConsumption}
                    type="variable"
                    isCurrentYear={isCurrentYear}
                    currentMonth={currentMonth}
                    t={t}
                    onCategoryClick={setSelectedCategory}
                  />
                  <div className="flex justify-center pt-4 pb-8">
                    <CategoryPicker 
                      placeholder={t('budgets.add_category', '+ Tilføj kategori')}
                      onSelect={(id) => setSelectedCategory({ category_id: id, category_type: 'Expense', expense_type: 'Variable', months: [] })}
                    />
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      )}

      {selectedCategory && (
        <BudgetDetailsSidebar
          category={selectedCategory}
          year={currentYear}
          onClose={() => setSelectedCategory(null)}
        />
      )}
    </motion.div>
  );
}
