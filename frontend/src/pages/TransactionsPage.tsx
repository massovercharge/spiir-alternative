import React, { useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { MoreHorizontal, CheckSquare, Square, Trash2, X } from 'lucide-react';
import { useTransactions, useUpdateTransactionCategory, useCreateCustomRule, useTags, useUpdateTransactions as useBulkUpdate } from '../api/client';
import { Skeleton } from '../components/ui/Skeleton';
import CategoryPicker from '../components/ui/CategoryPicker';
import { getCategoryIcon } from '../components/ui/CategoryIcon';
import { TransactionFilters } from '../components/ui/TransactionFilters';
import { TransactionDetailsSidebar } from '../components/ui/TransactionDetailsSidebar';
import { format, isToday, isYesterday, parseISO } from 'date-fns';
import { da, enUS } from 'date-fns/locale';
import { motion, AnimatePresence } from 'framer-motion';

function formatTransactionDate(dateStr: string, t: any, currentLang: string) {
  if (!dateStr) return t('transactions.unknown_date');
  try {
    const d = parseISO(dateStr);
    if (isToday(d)) return t('transactions.today', 'I dag');
    if (isYesterday(d)) return t('transactions.yesterday', 'I går');
    return format(d, 'd. MMMM yyyy', { locale: currentLang === 'en' ? enUS : da });
  } catch (e) {
    return dateStr.substring(0, 10);
  }
}

export default function TransactionsPage() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navState = location.state as any;
  
  const [filterType, setFilterType] = useState('Alle poster');
  const [startDate, setStartDate] = useState(navState?.startDate || '');
  const [endDate, setEndDate] = useState(navState?.endDate || '');
  const [search, setSearch] = useState('');
  const [selectedTag, setSelectedTag] = useState('');
  const [amountOp, setAmountOp] = useState<string>('');
  const [amountVal, setAmountVal] = useState<number | undefined>(undefined);
  const [categoryId, setCategoryId] = useState<string>(navState?.categoryId || '');
  
  const [selectedTransaction, setSelectedTransaction] = useState<any>(null);
  
  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data: tagsData } = useTags();
  const { data, isLoading, isError } = useTransactions(
    500, // Load more to allow better bulk editing
    0,
    filterType === 'Alle poster' ? undefined : filterType,
    selectedTag || undefined,
    startDate || undefined,
    endDate || undefined,
    search || undefined,
    amountOp || undefined,
    amountVal,
    categoryId || undefined
  );
  
  const updateCategoryMutation = useUpdateTransactionCategory();
  const bulkUpdateMutation = useBulkUpdate();
  const createRuleMutation = useCreateCustomRule();
  
  // Rule Creation State
  const [rulePrompt, setRulePrompt] = useState<{
    isOpen: boolean;
    txId: string;
    description: string;
    categoryId: string;
    categoryName: string;
  }>({ isOpen: false, txId: "", description: "", categoryId: "", categoryName: "" });

  const transactions = data?.transactions || [];

  const grouped = useMemo(() => {
    // Group transactions by date string
    const groups = transactions.reduce((acc: Record<string, any[]>, tx: any) => {
      const dateStr = tx.booking_date;
      if (!acc[dateStr]) acc[dateStr] = [];
      acc[dateStr].push(tx);
      return acc;
    }, {});
    
    // Sort groups by date descending
    return Object.entries(groups).sort((a, b) => 
      new Date(b[0]).getTime() - new Date(a[0]).getTime()
    );
  }, [transactions]);

  // Derived statistics for summary box
  const txCount = transactions.length;
  const uncategorizedCount = transactions.filter((t: any) => {
    const catId = t.allocations?.[0]?.category_id;
    return !catId || catId === 'diverse|ikke-kategoriseret' || catId === 'diverse|ukategoriseret';
  }).length;
  const totalAmount = transactions.reduce((sum: number, t: any) => sum + (t.amount_minor / 100), 0);
  const avgAmount = txCount > 0 ? totalAmount / txCount : 0;

  const handleCategoryChange = (tx: any, newCategoryId: string) => {
    updateCategoryMutation.mutate({ transactionId: tx.id, categoryId: newCategoryId });
    
    if (tx.description && tx.description.trim().length > 2) {
      const catParts = newCategoryId.split('|');
      const catName = catParts[1] ? catParts[1] : catParts[0];
      setRulePrompt({
        isOpen: true,
        txId: tx.id,
        description: tx.description,
        categoryId: newCategoryId,
        categoryName: catName
      });
    }
  };

  const handleCreateRule = () => {
    createRuleMutation.mutate({
      matchPattern: rulePrompt.description.toLowerCase().trim(),
      categoryId: rulePrompt.categoryId
    }, {
      onSuccess: () => {
        setRulePrompt({ ...rulePrompt, isOpen: false });
      }
    });
  };

  const handleFindSimilar = (desc: string) => {
    setFilterType('Alle poster');
    setStartDate('');
    setEndDate('');
    setSelectedTag('');
    setCategoryId('');
    setAmountOp('');
    setAmountVal(undefined);
    setSearch(desc);
    setSelectedTransaction(null);
  };

  const toggleSelection = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const toggleAll = () => {
    if (selectedIds.size === transactions.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(transactions.map((t: any) => t.id)));
    }
  };

  const handleBulkCategorize = (newCategoryId: string) => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    bulkUpdateMutation.mutate({
      transactionIds: ids,
      patch: { category_id: newCategoryId }
    }, {
      onSuccess: () => {
        setSelectedIds(new Set());
      }
    });
  };

  const generateFilterSummary = () => {
    const isDa = i18n.language === 'da';
    let text = isDa ? `Viser ${txCount}${txCount === 500 ? '+' : ''} poster` : `Showing ${txCount}${txCount === 500 ? '+' : ''} transactions`;
    
    if (filterType !== 'Alle poster') {
      text += isDa ? ` under '${filterType}'` : ` under '${filterType}'`;
    }
    
    if (startDate && endDate) {
      text += isDa ? ` fra ${startDate} til ${endDate}` : ` from ${startDate} to ${endDate}`;
    } else {
      text += isDa ? ` fra hele perioden` : ` from all time`;
    }

    if (search) {
      text += isDa ? ` der matcher '${search}'` : ` matching '${search}'`;
    }

    if (selectedTag) {
      text += isDa ? ` med tagget '${selectedTag}'` : ` tagged with '${selectedTag}'`;
    }

    if (amountOp && amountVal !== undefined) {
      const opText = amountOp === 'gt' ? 'større end' : amountOp === 'lt' ? 'mindre end' : 'lig med';
      text += isDa ? ` med beløb ${opText} ${amountVal}` : ` with amount ${opText} ${amountVal}`;
    }

    return text + ".";
  };

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6 pb-24">
      <motion.div 
        initial={{ opacity: 0, y: -10 }} 
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-4"
      >
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">{t('app.transactions', 'Poster')}</h1>
            <p className="text-muted text-sm mt-1">{generateFilterSummary()}</p>
          </div>
        </div>
        
        <TransactionFilters 
          filterType={filterType}
          setFilterType={setFilterType}
          startDate={startDate}
          setStartDate={setStartDate}
          endDate={endDate}
          setEndDate={setEndDate}
          search={search}
          setSearch={setSearch}
          tags={tagsData?.tags || []}
          selectedTag={selectedTag}
          setSelectedTag={setSelectedTag}
          amountOp={amountOp}
          setAmountOp={setAmountOp}
          amountVal={amountVal} setAmountVal={setAmountVal}
          categoryId={categoryId} setCategoryId={setCategoryId}
        />
      </motion.div>

      {/* Summary Box */}
      {!isLoading && txCount > 0 && (
        <motion.div 
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-[hsla(var(--brand-primary),0.05)] border border-[hsla(var(--brand-primary),0.2)] rounded-xl p-4 flex flex-col md:flex-row gap-4 justify-between items-center shadow-sm"
        >
          <div className="text-sm">
            <span className="font-semibold">{txCount} poster</span> fra den valgte periode. 
            Deraf <span 
              onClick={() => { if (uncategorizedCount > 0) setFilterType('Ukategoriseret'); }}
              className={`font-semibold ${uncategorizedCount > 0 ? 'text-[hsl(var(--brand-danger))] cursor-pointer hover:underline' : 'text-success'}`}
            >
              {uncategorizedCount} ikke kategoriserede
            </span>.
          </div>
          <div className="text-sm md:text-right flex items-center md:items-end flex-col">
            <div>
              I alt: <span className="font-bold text-lg">{totalAmount.toLocaleString('da-DK', { style: 'currency', currency: 'DKK' })}</span>
            </div>
            <span className="text-muted text-xs">(Gennemsnit: {Math.round(avgAmount).toLocaleString('da-DK')} kr.)</span>
          </div>
        </motion.div>
      )}

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          {isLoading && (
            <div className="p-6 space-y-6">
              {[1, 2, 3].map((g) => (
                <div key={g} className="space-y-4">
                  <Skeleton className="h-5 w-24" />
                  {[1, 2].map((i) => (
                    <div key={i} className="flex items-center gap-4">
                      <Skeleton className="h-10 w-10 rounded-full" />
                      <div className="flex-1 space-y-2">
                        <Skeleton className="h-4 w-1/3" />
                        <Skeleton className="h-3 w-1/4" />
                      </div>
                      <Skeleton className="h-4 w-16" />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {!isLoading && grouped.length === 0 && (
            <div className="p-12 text-center text-muted">
              {t('transactions.no_transactions', 'Ingen poster fundet')}
            </div>
          )}

          {!isLoading && grouped.length > 0 && (
            <div className="bg-[hsl(var(--bg-tertiary))] border-b border-[hsl(var(--border-color))] px-4 md:px-6 py-2 flex items-center gap-3">
              <button onClick={toggleAll} className="text-muted hover:text-[hsl(var(--text-primary))] transition-colors">
                {selectedIds.size === transactions.length ? <CheckSquare size={18} className="text-[hsl(var(--brand-primary))]" /> : <Square size={18} />}
              </button>
              <span className="text-xs font-semibold text-muted uppercase tracking-wider">Vælg alle</span>
            </div>
          )}

          {!isLoading && grouped.map(([dateKey, txs]: [string, any], groupIndex) => (
            <motion.div 
              key={dateKey}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: groupIndex * 0.05 }}
              className="border-b border-[hsl(var(--border-color))] last:border-0"
            >
              <div className="bg-[hsl(var(--bg-tertiary))] px-4 md:px-6 py-2 sticky top-0 z-10 border-y border-[hsl(var(--border-color))] first:border-t-0 text-xs font-semibold text-muted uppercase tracking-wider ml-10">
                {formatTransactionDate(dateKey, t, i18n.language)}
              </div>
              <div className="divide-y divide-[hsla(var(--border-color),0.5)]">
                {txs.map((tx: any) => {
                  const amount = tx.amount_minor / 100;
                  const description = tx.description || t('transactions.unknown', 'Ukendt');
                  const categoryParts = (tx.allocations?.[0]?.category_id || '').split('|');
                  const categoryName = categoryParts[1] ? categoryParts[1] : categoryParts[0] || t('transactions.uncategorized', 'Ukategoriseret');
                  const isSelected = selectedIds.has(tx.id);

                  return (
                    <div 
                      key={tx.id} 
                      className={`flex items-center gap-3 md:gap-4 px-4 md:px-6 py-5 md:py-4 transition-colors group cursor-pointer ${isSelected ? 'bg-[hsla(var(--brand-primary),0.1)]' : 'hover:bg-[hsla(var(--bg-tertiary),0.5)]'}`}
                      onClick={() => setSelectedTransaction(tx)}
                    >
                      <button 
                        onClick={(e) => toggleSelection(tx.id, e)}
                        className="text-muted hover:text-[hsl(var(--brand-primary))] transition-colors shrink-0"
                      >
                        {isSelected ? <CheckSquare size={18} className="text-[hsl(var(--brand-primary))]" /> : <Square size={18} className="opacity-30 group-hover:opacity-100" />}
                      </button>
                      
                      <div className={`hidden sm:flex flex-shrink-0 w-10 h-10 rounded-full bg-[hsla(var(--border-color),0.5)] flex items-center justify-center text-muted group-hover:bg-[hsl(var(--bg-secondary))] group-hover:shadow-sm transition-all ${isSelected ? 'bg-[hsl(var(--bg-secondary))] shadow-sm' : ''}`}>
                        {getCategoryIcon(tx.allocations?.[0]?.category_id || '')}
                      </div>
                      
                      <div className="flex-1 min-w-0 flex flex-col justify-center items-start" onClick={(e) => e.stopPropagation()}>
                        <p className="font-medium text-sm md:text-base line-clamp-2 md:line-clamp-1 break-words mb-1 max-w-full cursor-pointer" onClick={() => setSelectedTransaction(tx)}>{description}</p>
                        <CategoryPicker 
                          selectedCategoryId={tx.allocations?.[0]?.category_id} 
                          onSelect={(newCatId) => handleCategoryChange(tx, newCatId)}
                        />
                        {tx.note && <span className="text-xs text-muted mt-1">📝 {tx.note}</span>}
                        {tx.tags?.length > 0 && (
                          <div className="flex gap-1 mt-1">
                            {tx.tags.map((t: string) => (
                              <span key={t} className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">#{t}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className={`font-semibold ${amount > 0 ? "text-success" : ""}`}>
                          {amount > 0 ? '+' : ''}{amount.toLocaleString('da-DK', { style: 'currency', currency: 'DKK' })}
                        </p>
                      </div>
                      <div className="hidden sm:block flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button variant="ghost" size="sm" className="px-2 h-8 w-8 rounded-full">
                          <MoreHorizontal size={16} />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ))}
        </CardContent>
      </Card>

      {/* Bulk Action Toolbar */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <motion.div 
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-full max-w-lg px-4"
          >
            <div className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] shadow-2xl rounded-2xl p-4 flex flex-col sm:flex-row items-center gap-4 justify-between">
              <div className="flex items-center gap-3">
                <div className="bg-[hsl(var(--brand-primary))] text-white font-bold w-8 h-8 rounded-full flex items-center justify-center">
                  {selectedIds.size}
                </div>
                <span className="font-semibold text-sm">poster valgt</span>
              </div>
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <div className="flex-1 sm:w-48">
                  <CategoryPicker 
                    onSelect={handleBulkCategorize}
                    className="w-full"
                  />
                </div>
                <button 
                  onClick={() => setSelectedIds(new Set())}
                  className="p-2 text-muted hover:text-[hsl(var(--text-primary))] bg-[hsl(var(--bg-tertiary))] rounded-lg shrink-0"
                  title="Annuller"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rule Prompt Dialog */}
      {rulePrompt.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="bg-[hsl(var(--bg-primary))] rounded-2xl shadow-xl p-6 max-w-md w-full border border-[hsl(var(--border-color))]"
          >
            <h3 className="text-xl font-bold mb-2">Husk denne fremover?</h3>
            <p className="text-muted text-sm mb-6">
              Vil du automatisk kategorisere fremtidige og tidligere betalinger til <strong className="text-[hsl(var(--text-primary))]">"{rulePrompt.description}"</strong> som <strong className="text-[hsl(var(--brand-primary))] capitalize">{rulePrompt.categoryName.replace('-', ' ')}</strong>?
            </p>
            <div className="flex justify-end gap-3">
              <Button 
                variant="outline" 
                onClick={() => setRulePrompt({ ...rulePrompt, isOpen: false })}
                disabled={createRuleMutation.isPending}
              >
                Nej tak
              </Button>
              <Button 
                onClick={handleCreateRule}
                disabled={createRuleMutation.isPending}
                className="bg-[hsl(var(--brand-primary))] text-white"
              >
                {createRuleMutation.isPending ? 'Gemmer...' : 'Ja, husk det'}
              </Button>
            </div>
          </motion.div>
        </div>
      )}
      
      {selectedTransaction && (
        <TransactionDetailsSidebar 
          transaction={selectedTransaction} 
          onClose={() => setSelectedTransaction(null)}
          onFindSimilar={handleFindSimilar}
        />
      )}
    </div>
  );
}
