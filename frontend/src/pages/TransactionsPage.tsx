import React, { useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { MoreHorizontal, CheckSquare, Square, Trash2, X, AlertTriangle, CheckCheck } from 'lucide-react';
import {
  useTransactions,
  useUpdateTransactionCategory,
  useCreateCustomRule,
  useTags,
  useUpdateTransactions as useBulkUpdate,
  useResolveDuplicates,
  useDuplicatePreview,
} from '../api/client';
import { toast } from 'sonner';
import { Skeleton } from '../components/ui/Skeleton';
import CategoryPicker from '../components/ui/CategoryPicker';
import { getCategoryIcon } from '../components/ui/CategoryIcon';
import { TransactionFilters } from '../components/ui/TransactionFilters';
import { TransactionDetailsSidebar } from '../components/ui/TransactionDetailsSidebar';
import { format, isToday, isYesterday, parseISO } from 'date-fns';
import { da, enUS } from 'date-fns/locale';
import { motion, AnimatePresence } from 'framer-motion';
import { useVirtualizer } from '@tanstack/react-virtual';
import DuplicateReviewModal from '../components/transactions/DuplicateReviewModal';

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
  
  const [filterType, setFilterType] = useState(navState?.filterType || 'Alle poster');
  const [startDate, setStartDate] = useState(navState?.startDate || '');
  const [endDate, setEndDate] = useState(navState?.endDate || '');
  const [search, setSearch] = useState(navState?.search || '');
  const [selectedTag, setSelectedTag] = useState('');
  const [amountOp, setAmountOp] = useState<string>('');
  const [amountVal, setAmountVal] = useState<number | undefined>(undefined);
  const [categoryId, setCategoryId] = useState<string>(navState?.categoryId || '');
  
  const [selectedTransaction, setSelectedTransaction] = useState<any>(null);
  const [isDuplicateReviewOpen, setIsDuplicateReviewOpen] = useState(false);
  const resolveDuplicatesMutation = useResolveDuplicates();
  const { data: duplicatePreviewData } = useDuplicatePreview();
  const duplicateGroupsCount = duplicatePreviewData?.total_groups || 0;
  
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

  const flattened = useMemo(() => {
    const flat: any[] = [];
    grouped.forEach(([dateKey, txs]: [string, any]) => {
      flat.push({ type: 'header', dateKey });
      txs.forEach((tx: any) => {
        flat.push({ type: 'item', tx });
      });
    });
    return flat;
  }, [grouped]);

  const virtualizer = useVirtualizer({
    count: flattened.length,
    getScrollElement: () => document.getElementById('scroll-container'),
    estimateSize: (index: number) => flattened[index].type === 'header' ? 33 : 89,
    overscan: 10,
  });

  // Derived statistics for summary box
  const { txCount, uncategorizedCount, totalAmount, avgAmount } = useMemo(() => {
    const count = transactions.length;
    const uncategorized = transactions.filter((t: any) => {
      const catId = t.allocations?.[0]?.category_id;
      return !catId || catId === 'diverse|ikke-kategoriseret' || catId === 'diverse|ukategoriseret';
    }).length;
    const total = transactions.reduce((sum: number, t: any) => sum + (t.amount_minor / 100), 0);
    const avg = count > 0 ? total / count : 0;
    
    return { txCount: count, uncategorizedCount: uncategorized, totalAmount: total, avgAmount: avg };
  }, [transactions]);

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
    let text = t('transactions.showingCount', { count: `${txCount}${txCount === 500 ? '+' : ''}` });
    
    if (filterType !== 'Alle poster') {
      text += ` ${t('transactions.underFilter', { filter: filterType })}`;
    }
    
    if (startDate && endDate) {
      text += ` ${t('transactions.dateRange', { start: startDate, end: endDate })}`;
    } else {
      text += ` ${t('transactions.allTime')}`;
    }

    if (search) {
      text += ` ${t('transactions.matchingSearch', { search })}`;
    }

    if (selectedTag) {
      text += ` ${t('transactions.taggedWith', { tag: selectedTag })}`;
    }

    if (amountOp && amountVal !== undefined) {
      const opText = amountOp === 'gt' ? '>' : amountOp === 'lt' ? '<' : '=';
      text += ` ${t('transactions.withAmount', { op: opText, amount: amountVal })}`;
    }

    return text + ".";
  };

  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6 pb-28 md:pb-8">
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

      {/* Persistent Duplicate Notification Banner (always visible if unresolved duplicates exist anywhere in the household) */}
      {(duplicateGroupsCount > 0 || transactions.some((t: any) => t.has_duplicate_warning)) && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs"
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 text-amber-500 flex items-center justify-center shrink-0">
              <AlertTriangle size={17} />
            </div>
            <div>
              <div className="text-xs font-bold text-[hsl(var(--text-primary))] flex items-center gap-1.5">
                <span>{t('duplicates.bannerTitle', 'Mulig dobbeltbetaling detekteret')}</span>
                {duplicateGroupsCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 text-[10px] font-bold">
                    {duplicateGroupsCount} {duplicateGroupsCount === 1 ? t('duplicates.groupSingle', 'gruppe') : t('duplicates.groupPlural', 'grupper')}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-muted mt-0.5">
                {t('duplicates.persistentBannerDesc', 'Der er uafklarede posteringer med samme dato og beløb.')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <button
              onClick={() => {
                setFilterType('Mulige dubletter');
                setStartDate('');
                setEndDate('');
              }}
              className="px-2.5 py-1 text-xs font-semibold text-amber-600 dark:text-amber-400 hover:underline transition-colors"
            >
              {t('duplicates.showInList', 'Vis i listen')}
            </button>
            <button
              onClick={() => setIsDuplicateReviewOpen(true)}
              className="px-3 py-1.5 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white rounded-lg shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <AlertTriangle size={13} />
              <span>{t('duplicates.reviewButton', 'Undersøg & Løs')}</span>
            </button>
          </div>
        </motion.div>
      )}

      {/* Summary Box */}
      {!isLoading && txCount > 0 && (
        <motion.div 
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-[hsla(var(--brand-primary),0.05)] border border-[hsla(var(--brand-primary),0.2)] rounded-xl p-4 flex flex-col md:flex-row gap-4 justify-between items-center shadow-sm"
        >
          <div className="text-sm space-y-1">
            <div>
              <span className="font-semibold">{txCount}</span> {t('transactions.summaryFromPeriod', 'poster fra den valgte periode.')}{' '}
              <span 
                onClick={() => { if (uncategorizedCount > 0) setFilterType('Ukategoriseret'); }}
                className={`font-semibold ${uncategorizedCount > 0 ? 'text-[hsl(var(--brand-danger))] cursor-pointer hover:underline' : 'text-success'}`}
              >
                {uncategorizedCount} {t('transactions.notCategorized', 'ikke kategoriserede')}
              </span>.
            </div>
          </div>
          <div className="text-sm md:text-right flex items-center md:items-end flex-col">
            <div>
              {t('transactions.total', 'I alt:')} <span className="font-bold text-lg">{totalAmount.toLocaleString(i18n.language === 'da' ? 'da-DK' : 'en-US', { style: 'currency', currency: 'DKK' })}</span>
            </div>
            <span className="text-muted text-xs">({t('transactions.average', 'Gennemsnit:')} {Math.round(avgAmount).toLocaleString(i18n.language === 'da' ? 'da-DK' : 'en-US')} kr.)</span>
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

          {!isLoading && flattened.length > 0 && (
            <div
              style={{
                height: `${virtualizer.getTotalSize()}px`,
                width: '100%',
                position: 'relative',
              }}
            >
              {virtualizer.getVirtualItems().map((virtualItem: any) => {
                const item = flattened[virtualItem.index];
                
                return (
                  <div
                    key={virtualItem.key}
                    data-index={virtualItem.index}
                    ref={virtualizer.measureElement}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      transform: `translateY(${virtualItem.start}px)`,
                    }}
                  >
                    {item.type === 'header' ? (
                      <div className="bg-[hsl(var(--bg-tertiary))] px-4 md:px-6 py-2 border-y border-[hsl(var(--border-color))] text-xs font-semibold text-muted uppercase tracking-wider ml-10 z-10">
                        {formatTransactionDate(item.dateKey, t, i18n.language)}
                      </div>
                    ) : (
                      <div className="border-b border-[hsl(var(--border-color))]">
                        {(() => {
                          const tx = item.tx;
                          const amount = tx.amount_minor / 100;
                          const description = tx.description || t('transactions.unknown', 'Ukendt');
                          const categoryParts = (tx.allocations?.[0]?.category_id || '').split('|');
                          const categoryName = categoryParts[1] ? categoryParts[1] : categoryParts[0] || t('transactions.uncategorized', 'Ukategoriseret');
                          const isSelected = selectedIds.has(tx.id);

                          return (
                            <div 
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
                                <div className="flex items-center gap-2 max-w-full flex-wrap mb-1">
                                  <p className="font-medium text-sm md:text-base line-clamp-2 md:line-clamp-1 break-words cursor-pointer" onClick={() => setSelectedTransaction(tx)}>{description}</p>
                                  {tx.has_duplicate_warning && (
                                    <span
                                      title={t('duplicates.bannerTitle', 'Mulig dobbeltbetaling detekteret')}
                                      className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 shrink-0"
                                    >
                                      <AlertTriangle size={11} />
                                      {t('duplicates.warningBadge', 'Mulig dublet')}
                                    </span>
                                  )}
                                </div>
                                <CategoryPicker 
                                  selectedCategoryId={tx.allocations?.[0]?.category_id} 
                                  onSelect={(newCatId) => handleCategoryChange(tx, newCatId)}
                                />
                                {tx.note && <span className="text-xs text-muted mt-1">📝 {tx.note}</span>}
                                {tx.tags?.length > 0 && (
                                  <div className="flex gap-1 mt-1">
                                    {tx.tags.map((tag: string) => (
                                      <span key={tag} className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">#{tag}</span>
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
                        })()}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
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
                <span className="font-semibold text-sm">{t('transactions.itemsSelected', 'poster valgt')}</span>
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
                  title={t('transactions.cancel', 'Annuller')}
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
            <h3 className="text-xl font-bold mb-2">{t('transactions.rememberRuleTitle', 'Husk denne fremover?')}</h3>
            <p className="text-muted text-sm mb-6">
              {t('transactions.rememberRuleBody', {
                description: rulePrompt.description,
                category: rulePrompt.categoryName.replace('-', ' '),
                defaultValue: `Vil du automatisk kategorisere fremtidige og tidligere betalinger til "${rulePrompt.description}" som ${rulePrompt.categoryName.replace('-', ' ')}?`
              })}
            </p>
            <div className="flex justify-end gap-3">
              <Button 
                variant="outline" 
                onClick={() => setRulePrompt({ ...rulePrompt, isOpen: false })}
                disabled={createRuleMutation.isPending}
              >
                {t('transactions.noThanks', 'Nej tak')}
              </Button>
              <Button 
                onClick={handleCreateRule}
                disabled={createRuleMutation.isPending}
                className="bg-[hsl(var(--brand-primary))] text-white"
              >
                {createRuleMutation.isPending ? t('common.saving', 'Gemmer...') : t('transactions.yesRememberIt', 'Ja, husk det')}
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

      <DuplicateReviewModal
        isOpen={isDuplicateReviewOpen}
        onClose={() => setIsDuplicateReviewOpen(false)}
        onFilterTransactions={() => setFilterType('Mulige dubletter')}
      />
    </div>
  );
}
