import React, { useState, useEffect } from 'react';
import { X, Calendar, Edit3, Tag as TagIcon, SplitSquareHorizontal, Check, AlertCircle, Plus, Trash2, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { da, enUS } from 'date-fns/locale';
import { Button } from './Button';
import CategoryPicker from './CategoryPicker';
import { useUpdateTransactions, useSplitTransaction } from '../../api/client';

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
  
  // Split state
  const isInitiallySplit = transaction.allocations && transaction.allocations.length > 1;
  const [isSplitMode, setIsSplitMode] = useState(isInitiallySplit);
  const [splits, setSplits] = useState<{ id?: string, amount_minor: number, amount_input: string, category_id: string | null }[]>([]);
  
  const updateMutation = useUpdateTransactions();
  const splitMutation = useSplitTransaction();

  useEffect(() => {
    setCustomDate(transaction.custom_date || transaction.booking_date);
    setNote(transaction.note || '');
    setIsExtraordinary(transaction.is_extraordinary || false);
    setTags(transaction.tags || []);
    
    const initiallySplit = transaction.allocations && transaction.allocations.length > 1;
    setIsSplitMode(initiallySplit);
    
    if (transaction.allocations) {
      setSplits(transaction.allocations.map((a: any) => ({
        id: a.id,
        amount_minor: a.amount_minor,
        amount_input: (Math.abs(a.amount_minor) / 100).toString().replace('.', ','),
        category_id: a.category_id
      })));
    } else {
      setSplits([{
        amount_minor: transaction.amount_minor,
        amount_input: (Math.abs(transaction.amount_minor) / 100).toString().replace('.', ','),
        category_id: transaction.category_id
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
      const isExpense = transaction.amount_minor < 0;
      const parsedSplits = splits.map(s => {
        let val = Math.round(parseFloat(s.amount_input.replace(',', '.')) * 100);
        if (isNaN(val)) val = 0;
        return {
          ...s,
          amount_minor: isExpense ? -Math.abs(val) : Math.abs(val)
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
    const missingAmount = Math.max(0, targetSum - currentSum);
    const amountStr = missingAmount > 0.01 ? missingAmount.toFixed(2).replace('.', ',') : '';
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
  
  const isPending = updateMutation.isPending || splitMutation.isPending;

  // Helper to generate a better search term for "Find lignende"
  const getSearchTerm = (desc: string) => {
    let term = desc;

    // 1. Remove anything after '*' (common billing reference separator, e.g., UBER* TRIP, AMAZON.COM*XYZ)
    const starIndex = term.indexOf('*');
    if (starIndex !== -1) {
      term = term.substring(0, starIndex);
    }

    // 2. Clean common card prefixes
    term = term.replace(/dankort[- ]?nota/i, '');
    term = term.replace(/visa\/dankort/i, '');
    term = term.replace(/visa/i, '');
    term = term.replace(/dankort/i, '');
    term = term.replace(/mastercard/i, '');
    term = term.replace(/mobilepay/i, '');
    term = term.replace(/mobilpay/i, '');
    term = term.replace(/\bn\*\d+\b/ig, '');
    term = term.replace(/\bnet\d+\b/ig, '');

    // 3. Remove common transaction filler words
    term = term.replace(/betaling til/i, '');
    term = term.replace(/køb dkk/i, '');
    term = term.replace(/køb/i, '');

    // 4. Remove date pattern (e.g. 24.12, 12/03/2026)
    term = term.replace(/\b\d{1,2}[./-]\d{1,2}([./-]\d{2,4})?\b/g, '');

    // 5. Remove long numbers (IDs, references)
    term = term.replace(/\b\d{4,}\b/g, '');

    // 6. Split by comma or semicolon and take the first part (removes location/branch details, e.g., "Netto, Aarhus")
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
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />
      <div className="fixed top-0 right-0 h-full w-full max-w-md bg-[hsl(var(--bg-primary))] border-l border-[hsl(var(--border-color))] shadow-2xl z-50 overflow-y-auto flex flex-col animate-slide-in-right">
        
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
                  <div key={index} className="flex gap-2 items-start">
                    <div className="flex-1">
                      <CategoryPicker 
                        selectedCategoryId={split.category_id || undefined}
                        onSelect={(id) => updateSplit(index, 'category_id', id)}
                        className="w-full"
                      />
                    </div>
                    <div className="w-24">
                      <input 
                        type="text" 
                        value={split.amount_input}
                        onChange={(e) => updateSplit(index, 'amount_input', e.target.value)}
                        placeholder="Beløb"
                        className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary h-[38px]"
                      />
                    </div>
                    {splits.length > 1 && (
                      <button onClick={() => removeSplit(index)} className="p-2 text-red-500 hover:bg-red-500/10 rounded-lg mt-0.5">
                        <Trash2 size={16} />
                      </button>
                    )}
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
            </div>

        </div>

        <div className="p-6 border-t border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] flex gap-3">
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
