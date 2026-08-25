import React, { useState, useEffect } from 'react';
import { X, Calendar, Edit3, Tag as TagIcon, SplitSquareHorizontal, Check, AlertCircle, Plus, Trash2, Search, Sparkles, Receipt, ChevronDown, ChevronUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { da, enUS } from 'date-fns/locale';
import { Button } from './Button';
import CategoryPicker from './CategoryPicker';
import { useUpdateTransactions, useSplitTransaction, useLinkReceiptToTransaction, useSuggestedReceipts } from '../../api/client';

interface TransactionDetailsSidebarProps {
  transaction: any;
  onClose: () => void;
  onFindSimilar?: (description: string) => void;
}

export function TransactionDetailsSidebar({ transaction, onClose, onFindSimilar }: TransactionDetailsSidebarProps) {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'da' ? da : enUS;
  
  const [customDate, setCustomDate] = useState(transaction.custom_date || transaction.booking_date);
  const [note, setNote] = useState(transaction.note || '');
  const [isExtraordinary, setIsExtraordinary] = useState(transaction.is_extraordinary || false);
  const [tags, setTags] = useState<string[]>(transaction.tags || []);
  const [tagInput, setTagInput] = useState('');
  
  // Receipt linking state
  const [isLinkingReceipt, setIsLinkingReceipt] = useState(false);
  const [showManualReceiptInput, setShowManualReceiptInput] = useState(false);
  const [receiptIdInput, setReceiptIdInput] = useState('');
  
  // Split state
  const isInitiallySplit = transaction.allocations && transaction.allocations.length > 1;
  const [isSplitMode, setIsSplitMode] = useState(isInitiallySplit);
  const [splits, setSplits] = useState<{ id?: string, amount_minor: number, amount_input: string, category_id: string | null, item_name?: string }[]>([]);
  
  const updateMutation = useUpdateTransactions();
  const splitMutation = useSplitTransaction();
  const linkMutation = useLinkReceiptToTransaction();
  const { data: suggestions, isLoading: isLoadingSuggestions } = useSuggestedReceipts(transaction?.id, isLinkingReceipt);

  useEffect(() => {
    setCustomDate(transaction.custom_date || transaction.booking_date);
    setNote(transaction.note || '');
    setIsExtraordinary(transaction.is_extraordinary || false);
    setTags(transaction.tags || []);
    
    const initiallySplit = transaction.allocations && transaction.allocations.length > 1;
    setIsSplitMode(initiallySplit);
    
    if (transaction.allocations) {
      const mult = transaction.amount_minor < 0 ? -1 : 1;
      setSplits(transaction.allocations.map((a: any) => ({
        id: a.id,
        amount_minor: a.amount_minor,
        amount_input: ((a.amount_minor * mult) / 100).toString().replace('.', ','),
        category_id: a.category_id,
        item_name: a.item_name
      })));
    } else {
      setSplits([{
        amount_minor: transaction.amount_minor,
        amount_input: (Math.abs(transaction.amount_minor) / 100).toString().replace('.', ','),
        category_id: transaction.category_id,
        item_name: undefined
      }]);
    }
  }, [transaction]);

  const handleSave = () => {
    const patch: any = {};
    if (customDate !== transaction.booking_date) patch.custom_date = customDate;
    if (note !== (transaction.note || '')) patch.custom_note = note;
    if (isExtraordinary !== (transaction.is_extraordinary || false)) patch.is_extraordinary = isExtraordinary;
    patch.tags = tags;

    if (isSplitMode) {
      const mult = transaction.amount_minor < 0 ? -1 : 1;
      const parsedSplits = splits.map(s => {
        let val = Math.round(parseFloat(s.amount_input.replace(',', '.')) * 100);
        if (isNaN(val)) val = 0;
        return {
          ...s,
          amount_minor: val * mult
        };
      });
      
      let sum = parsedSplits.reduce((acc, curr) => acc + curr.amount_minor, 0);
      if (sum !== transaction.amount_minor) {
        const missing = transaction.amount_minor - sum;
        parsedSplits.push({
          amount_minor: missing,
          amount_input: '',
          category_id: transaction.category_id
        });
      }
      
      splitMutation.mutate(
        { transactionId: transaction.id, splits: parsedSplits.map(s => ({ amount_minor: s.amount_minor, category_id: s.category_id })) },
        { 
          onSuccess: () => {
            // Apply tags, notes, etc. after splitting
            if (Object.keys(patch).length > 0) {
              updateMutation.mutate(
                { transactionIds: [transaction.id], patch },
                { onSuccess: onClose }
              );
            } else {
              onClose();
            }
          }
        }
      );
    } else {
      if (splits[0] && splits[0].category_id !== transaction.category_id) {
        patch.category_id = splits[0].category_id;
      }
      updateMutation.mutate(
        { transactionIds: [transaction.id], patch },
        { onSuccess: onClose }
      );
    }
  };

  const addTag = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && tagInput.trim()) {
      const newTag = tagInput.trim().toLowerCase();
      if (!tags.includes(newTag)) {
        setTags([...tags, newTag]);
      }
      setTagInput('');
    }
  };

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter(t => t !== tagToRemove));
  };

  const addSplit = () => {
    const missingAmount = targetSum - currentSum;
    const amountStr = Math.abs(missingAmount) > 0.01 ? missingAmount.toFixed(2).replace('.', ',') : '';
    setSplits([...splits, { amount_minor: 0, amount_input: amountStr, category_id: null }]);
  };

  const removeSplit = (index: number) => {
    if (splits.length > 1) {
      setSplits(splits.filter((_, i) => i !== index));
    }
  };

  const updateSplit = (index: number, field: string, value: any) => {
    const newSplits = [...splits];
    newSplits[index] = { ...newSplits[index], [field]: value };
    setSplits(newSplits);
  };

  // Calculate current split sum for feedback
  const currentSum = splits.reduce((acc, curr) => {
    const val = parseFloat(curr.amount_input.replace(',', '.'));
    return acc + (isNaN(val) ? 0 : val);
  }, 0);
  const targetSum = Math.abs(transaction.amount_minor) / 100;
  const isSumValid = Math.abs(currentSum - targetSum) < 0.01; // Allow minor float inaccuracies
  
  const isPending = updateMutation.isPending || splitMutation.isPending || linkMutation.isPending;

  const handleLinkReceipt = () => {
    if (!receiptIdInput.trim()) return;
    linkMutation.mutate(
      { transactionId: transaction.id, receiptId: receiptIdInput.trim() },
      { 
        onSuccess: () => {
          setIsLinkingReceipt(false);
          setReceiptIdInput('');
          onClose(); // Close the sidebar, or maybe reload it. Usually easier to close it to see changes on list.
        }
      }
    );
  };

  // Helper to generate a better search term for "Find lignende"
  const getSearchTerm = (desc: string) => {
    let term = desc;

    // 1. Remove anything after '*' (common billing reference separator, e.g., UBER* TRIP, AMAZON.COM*XYZ)
    const starIndex = term.indexOf('*');
    if (starIndex !== -1) {
      term = term.substring(0, starIndex);
    }

    // 2. Clean common card prefixes
    term = term.replace(/dankort[- ]?køb/ig, '');
    term = term.replace(/dankort[- ]?nota/ig, '');
    term = term.replace(/visa\/dankort/ig, '');
    term = term.replace(/\bkontaktløs\b/ig, '');
    term = term.replace(/\bvisa\b/ig, '');
    term = term.replace(/\bdankort\b/ig, '');
    term = term.replace(/\bmastercard\b/ig, '');
    term = term.replace(/\bmobilepay\b|\bmobilpay\b/ig, '');
    term = term.replace(/\bn\*\d+\b/ig, '');
    term = term.replace(/\bnet\d+\b/ig, '');

    // 3. Remove nota / notanr and associated receipt/transaction reference codes
    term = term.replace(/\b(?:dankort[- ]?|visa(?:[/-]dankort)?[- ]?)?nota(?:\s*nr\.?|\.nr\.?|\.|\:)?\s*[a-z0-9]+\b/ig, '');
    term = term.replace(/\bnotanr\.?\s*[a-z0-9]+\b/ig, '');
    term = term.replace(/\b(?:dankort[- ]?|visa(?:[/-]dankort)?[- ]?)?nota\b/ig, '');
    term = term.replace(/\bnotanr\.?\b/ig, '');

    // 4. Remove common transaction filler words
    term = term.replace(/betaling til/ig, '');
    term = term.replace(/køb dkk/ig, '');
    term = term.replace(/køb/ig, '');

    // 5. Remove date pattern (e.g. 24.12, 12/03/2026)
    term = term.replace(/\b\d{1,2}[./-]\d{1,2}([./-]\d{2,4})?\b/g, '');

    // 6. Remove standalone long numbers unless preceded by aftalenr or aftale nr
    term = term.replace(/(?<!aftalenr\s*)(?<!aftale\s*nr\s*)\b\d{4,}\b/ig, '');

    // 7. Split by comma or semicolon and take the first part
    const sepIndex = term.search(/[,;]/);
    if (sepIndex !== -1) {
      term = term.substring(0, sepIndex);
    }

    // 7. Collapse whitespace and trim
    term = term.replace(/\s+/g, ' ').trim();

    // 8. If the term is still very long, restrict to first 3 words to keep the query broad and matching
    const words = term.split(' ');
    if (words.length > 3) {
      term = words.slice(0, 3).join(' ');
    }

    return term || desc;
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-[60]" onClick={onClose} />
      <div className="fixed top-0 right-0 h-full w-full max-w-md bg-[hsl(var(--bg-primary))] border-l border-[hsl(var(--border-color))] shadow-2xl z-[70] overflow-y-auto flex flex-col animate-slide-in-right">
        
        <div className="p-6 border-b border-[hsl(var(--border-color))] flex justify-between items-start gap-4">
          <div className="flex-1">
            <h2 className="text-lg font-bold">{transaction.description}</h2>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-sm text-muted">
                {transaction.amount} {transaction.currency} &bull; {transaction.account_name}
              </p>
              {onFindSimilar && (
                <button 
                  onClick={() => onFindSimilar(getSearchTerm(transaction.description))}
                  className="text-xs flex items-center gap-1 text-[hsl(var(--brand-primary))] hover:underline bg-[hsl(var(--brand-primary))]/10 px-2 py-0.5 rounded-full"
                >
                  <Search size={12} />
                  {t('transactions.find_similar', 'Find lignende')}
                </button>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-[hsl(var(--bg-secondary))] rounded-full shrink-0">
            <X className="w-5 h-5 text-muted" />
          </button>
        </div>

        <div className="p-6 flex-1 space-y-6">
          
          {isSplitMode ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center mb-4">
                <label className="text-sm font-semibold text-muted uppercase tracking-wider">Split Transaktion</label>
                <Button variant="ghost" size="sm" onClick={() => setIsSplitMode(false)} className="text-xs h-7 py-0 px-2">Annuller split</Button>
              </div>
              
              <div className="bg-[hsl(var(--bg-secondary))] p-3 rounded-lg border border-[hsl(var(--border-color))] mb-4 flex justify-between items-center">
                <span className="text-sm text-muted">Total at fordele:</span>
                <span className="font-semibold">{targetSum.toFixed(2).replace('.', ',')}</span>
              </div>
              
              <div className="space-y-3">
                {splits.map((split, index) => (
                  <div key={index} className="flex gap-2 items-start flex-col sm:flex-row">
                    <div className="flex-1 w-full">
                      {split.item_name && (
                        <div className="text-xs font-semibold mb-1 text-[hsl(var(--text-primary))]">{split.item_name}</div>
                      )}
                      <CategoryPicker 
                        selectedCategoryId={split.category_id || undefined}
                        onSelect={(id) => updateSplit(index, 'category_id', id)}
                        className="w-full"
                      />
                    </div>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <div className="w-24">
                        <input 
                          type="text" 
                          value={split.amount_input}
                          onChange={(e) => updateSplit(index, 'amount_input', e.target.value)}
                          placeholder="Beløb"
                          className={`w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary h-[38px] ${split.item_name ? 'mt-0 sm:mt-[20px]' : ''}`}
                        />
                      </div>
                      {splits.length > 1 && (
                        <button onClick={() => removeSplit(index)} className={`p-2 text-red-500 hover:bg-red-500/10 rounded-lg mt-0.5 ${split.item_name ? 'mt-0 sm:mt-[20px]' : ''}`}>
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              
              <Button variant="outline" className="w-full mt-2" onClick={addSplit}>
                <Plus size={16} className="mr-2" /> Tilføj række
              </Button>
              
              <div className={`text-sm mt-4 p-3 rounded-lg flex items-center gap-2 ${isSumValid ? 'bg-green-500/10 text-green-600' : 'bg-yellow-500/10 text-yellow-600'}`}>
                {isSumValid ? <Check size={16} /> : <AlertCircle size={16} />}
                <div>
                  Fordelt: <span className="font-semibold">{currentSum.toFixed(2).replace('.', ',')}</span>
                  {!isSumValid && <span> (Mangler {(targetSum - currentSum).toFixed(2).replace('.', ',')})</span>}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <label className="text-sm font-semibold text-muted uppercase tracking-wider">{t('categories')}</label>
              <CategoryPicker 
                selectedCategoryId={splits[0]?.category_id || undefined}
                onSelect={(id) => updateSplit(0, 'category_id', id)}
                className="w-full"
              />
            </div>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-muted uppercase tracking-wider">{t('Dato')}</label>
              <div className="flex flex-col gap-2">
                <input 
                  type="date" 
                  value={customDate}
                  onChange={(e) => setCustomDate(e.target.value)}
                  className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
                {customDate !== transaction.booking_date && (
                  <p className="text-xs text-muted">Oprindelig bankdato: {format(new Date(transaction.booking_date), 'd. MMM yyyy', { locale: dateLocale })}</p>
                )}
              </div>
            </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-muted uppercase tracking-wider">{t('Note')}</label>
                <textarea 
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Skriv en note..."
                  className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary min-h-[80px]"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-muted uppercase tracking-wider">{t('Tags')}</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {tags.map(tag => (
                    <span key={tag} className="inline-flex items-center gap-1 bg-primary/10 text-primary px-2.5 py-1 rounded-full text-xs font-medium">
                      #{tag}
                      <button onClick={() => removeTag(tag)} className="hover:text-red-500">
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
                <input 
                  type="text" 
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={addTag}
                  placeholder="Tilføj tag og tryk Enter..."
                  className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="pt-2">
                <label className="flex items-center gap-3 cursor-pointer p-3 bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg hover:border-primary transition-colors">
                  <input 
                    type="checkbox" 
                    checked={isExtraordinary}
                    onChange={(e) => setIsExtraordinary(e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <div className="flex flex-col">
                    <span className="text-sm font-medium">Marker som ekstraordinær</span>
                    <span className="text-xs text-muted">Holdes udenfor det faste budget</span>
                  </div>
                </label>
              </div>

              {(transaction.booking_date_time || transaction.transaction_type || transaction.creditor_account || transaction.debtor_account || transaction.balance_after_transaction_minor != null) && (
                <div className="pt-4 border-t border-[hsl(var(--border-color))] space-y-2 text-sm text-muted">
                  <h3 className="font-semibold text-[hsl(var(--text-primary))] uppercase tracking-wider text-xs mb-3">Bankdetaljer (PSD2)</h3>
                  
                  {transaction.booking_date_time && (
                    <div className="flex justify-between">
                      <span>Tidspunkt:</span>
                      <span>{format(new Date(transaction.booking_date_time), 'HH:mm:ss', { locale: dateLocale })}</span>
                    </div>
                  )}
                  {transaction.transaction_type && (
                    <div className="flex justify-between">
                      <span>Type:</span>
                      <span>{transaction.transaction_type}</span>
                    </div>
                  )}
                  {(transaction.creditor_account || transaction.debtor_account) && (
                    <div className="flex justify-between">
                      <span>Modpartens konto:</span>
                      <span>{transaction.creditor_account || transaction.debtor_account}</span>
                    </div>
                  )}
                  {transaction.balance_after_transaction_minor != null && (
                    <div className="flex justify-between">
                      <span>Løbende saldo:</span>
                      <span>{(transaction.balance_after_transaction_minor / 100).toFixed(2).replace('.', ',')} {transaction.currency}</span>
                    </div>
                  )}
                </div>
              )}

              <div className="pt-4 border-t border-[hsl(var(--border-color))]">
                {isSplitMode ? (
                  <p className="text-xs text-center text-muted mt-2">Transaktionen er splittet. Summen skal matche totalbeløbet.</p>
                ) : (
                  <>
                    <Button variant="outline" className="w-full flex items-center justify-center gap-2" onClick={() => setIsSplitMode(true)}>
                      <SplitSquareHorizontal size={16} />
                      Split transaktion
                    </Button>
                    <p className="text-xs text-center text-muted mt-2">Del transaktionen op i flere kategorier</p>
                  </>
                )}
              </div>

              <div className="pt-4 border-t border-[hsl(var(--border-color))] space-y-3">
                {isLinkingReceipt ? (
                  <div className="space-y-3 bg-[hsl(var(--bg-secondary))] p-3 rounded-lg border border-[hsl(var(--border-color))]">
                    <div className="flex items-center justify-between pb-1 border-b border-[hsl(var(--border-color))]">
                      <div className="flex items-center gap-1.5 font-semibold text-xs text-primary uppercase tracking-wider">
                        <Sparkles size={14} />
                        <span>{t('transactions.suggestedReceipts', 'Matchende Storebox-kvitteringer')}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => {
                          setIsLinkingReceipt(false);
                          setShowManualReceiptInput(false);
                          setReceiptIdInput('');
                        }}
                      >
                        {t('common.cancel', 'Annuller')}
                      </Button>
                    </div>

                    {isLoadingSuggestions ? (
                      <p className="text-xs text-muted py-2 text-center">{t('transactions.searchingSuggestions', 'Søger efter kvitteringer...')}</p>
                    ) : suggestions && suggestions.length > 0 ? (
                      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                        {suggestions.map((sug) => (
                          <div
                            key={sug.receipt_id}
                            className="p-2.5 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] hover:border-primary/50 rounded-lg text-xs space-y-1.5 transition-colors"
                          >
                            <div className="flex items-center justify-between font-medium">
                              <span className="font-semibold text-sm text-[hsl(var(--text-primary))]">{sug.merchant_name}</span>
                              <span className="text-[hsl(var(--text-primary))]">
                                {(sug.total_price_minor / 100).toFixed(2).replace('.', ',')} {sug.currency}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-muted text-[11px]">
                              <span>{sug.purchase_date}</span>
                              {sug.confidence === 'high' && (
                                <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-medium text-[10px]">
                                  {t('transactions.exactMatch', 'Stærkt match')}
                                </span>
                              )}
                            </div>
                            {sug.items_preview && sug.items_preview.length > 0 && (
                              <div className="text-muted text-[11px] truncate pt-1 border-t border-[hsl(var(--border-color))]/50">
                                {sug.items_preview.map((it) => `${it.name} (${(it.amount_minor / 100).toFixed(2).replace('.', ',')} kr)`).join(' • ')}
                              </div>
                            )}
                            <Button
                              variant="primary"
                              size="sm"
                              className="w-full mt-1.5 flex items-center justify-center gap-1.5"
                              disabled={linkMutation.isPending}
                              onClick={() => {
                                linkMutation.mutate(
                                  { transactionId: transaction.id, receiptId: sug.receipt_id },
                                  {
                                    onSuccess: () => {
                                      setIsLinkingReceipt(false);
                                      onClose();
                                    }
                                  }
                                );
                              }}
                            >
                              <Check size={14} />
                              {linkMutation.isPending ? t('common.connecting', 'Forbinder...') : t('transactions.linkThisReceipt', 'Forbind denne kvittering')}
                            </Button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-muted py-2 text-center">{t('transactions.noReceiptsFound', 'Ingen matchende kvitteringer fundet automatisk.')}</p>
                    )}

                    <div className="pt-2 border-t border-[hsl(var(--border-color))] space-y-2">
                      <button
                        type="button"
                        className="text-[11px] text-muted hover:text-[hsl(var(--text-primary))] flex items-center justify-between w-full"
                        onClick={() => setShowManualReceiptInput(!showManualReceiptInput)}
                      >
                        <span>{t('transactions.orEnterManualId', 'Eller indtast Storebox Receipt ID manuelt:')}</span>
                        {showManualReceiptInput ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                      
                      {showManualReceiptInput && (
                        <div className="space-y-2 pt-1">
                          <input 
                            type="text" 
                            value={receiptIdInput}
                            onChange={(e) => setReceiptIdInput(e.target.value)}
                            placeholder="fx 08p9sixdiwk2a0pwf4s37zxea..."
                            className="w-full bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded p-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                          />
                          <Button variant="outline" size="sm" className="w-full" onClick={handleLinkReceipt} disabled={!receiptIdInput.trim() || linkMutation.isPending}>
                            {linkMutation.isPending ? 'Forbinder...' : 'Forbind manuel ID'}
                          </Button>
                        </div>
                      )}
                    </div>

                    {linkMutation.isError && (
                      <p className="text-xs text-red-500 mt-2">{(linkMutation.error as Error).message || 'Der opstod en fejl'}</p>
                    )}
                  </div>
                ) : (
                  <Button variant="outline" className="w-full flex items-center justify-center gap-2" onClick={() => setIsLinkingReceipt(true)}>
                    <Plus size={16} />
                    Forbind Storebox Kvittering
                  </Button>
                )}
              </div>
            </div>

        </div>

        <div className="p-6 pb-28 md:pb-6 border-t border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] flex gap-3">
          <Button 
            variant="primary" 
            className="flex-1" 
            onClick={handleSave} 
            disabled={isPending}
          >
            {isPending ? 'Gemmer...' : 'Gem ændringer'}
          </Button>
        </div>

      </div>
    </>
  );
}
