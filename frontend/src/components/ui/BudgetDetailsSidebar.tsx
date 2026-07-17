import React, { useState, useEffect } from 'react';
import { X, Save, RefreshCw, Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from './Button';
import { useBudgets, useUpsertBudget, useTransactions, useBudgetBills, useSaveBudgetBills } from '../../api/client';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, Cell } from 'recharts';
import { format, endOfMonth, parseISO } from 'date-fns';
import { da, enUS } from 'date-fns/locale';
import { useNavigate } from 'react-router-dom';

interface BudgetDetailsSidebarProps {
  category: any;
  year: number;
  onClose: () => void;
}

const MONTH_INITIALS = ['Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec'];

export function BudgetDetailsSidebar({ category, year, onClose }: BudgetDetailsSidebarProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  
  const labelParts = category.category_id.split('|');
  const label = labelParts[1] ? labelParts[1] : labelParts[0];

  const isFixedOrIncome = category.expense_type === 'Fixed' || category.category_type === 'Income';

  const { data: budgets, isLoading: isLoadingBudgets } = useBudgets(year, category.category_id);
  const { data: budgetBills, isLoading: isLoadingBills } = useBudgetBills(isFixedOrIncome ? category.category_id : null, year);
  
  const upsertMutation = useUpsertBudget();
  const saveBillsMutation = useSaveBudgetBills();

  const isLoading = isLoadingBudgets || isLoadingBills;

  // State for Variable budgets
  const [amountInput, setAmountInput] = useState('');
  const [rollover, setRollover] = useState(false);
  const [activeMonths, setActiveMonths] = useState<Set<number>>(new Set([1,2,3,4,5,6,7,8,9,10,11,12]));

  // State for Fixed budgets (bills)
  const [bills, setBills] = useState<any[]>([]);

  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);

  // For fetching transactions when a month is clicked
  const startDate = selectedMonth ? `${year}-${selectedMonth.toString().padStart(2, '0')}-01` : undefined;
  const endDate = selectedMonth ? format(endOfMonth(parseISO(startDate!)), 'yyyy-MM-dd') : undefined;
  
  const { data: monthTransactionsData, isLoading: isLoadingTx } = useTransactions(
    100, 0, undefined, undefined, startDate, endDate, undefined, undefined, undefined, selectedMonth ? category.category_id : undefined
  );
  
  const monthTransactions = monthTransactionsData?.transactions || [];

  useEffect(() => {
    if (isFixedOrIncome) {
      if (budgetBills) {
        setBills(budgetBills.map((b: any) => ({
          ...b,
          id: b.id || Math.random().toString(), // ensuring id exists for temp items
          amountInput: (b.amount_minor / 100).toString().replace('.', ','),
          activeMonths: new Set(b.months)
        })));
      }
    } else {
      if (budgets && budgets.length > 0) {
        const nonZeroBudget = budgets.find((b: any) => b.amount_minor !== 0) || budgets[0];
        setAmountInput((Math.abs(nonZeroBudget.amount_minor) / 100).toString().replace('.', ','));
        setRollover(budgets[0].rollover);
        
        const active = new Set<number>();
        budgets.forEach((b: any) => {
          if (b.amount_minor !== 0) {
            active.add(b.month);
          }
        });
        if (active.size === 0) {
          for (let i = 1; i <= 12; i++) active.add(i);
        }
        setActiveMonths(active);
      } else {
        setAmountInput('');
        setRollover(false);
        setActiveMonths(new Set([1,2,3,4,5,6,7,8,9,10,11,12]));
      }
    }
  }, [budgets, budgetBills, isFixedOrIncome]);

  const handleSave = () => {
    if (isFixedOrIncome) {
      const validBills = bills
        .map(b => {
          const parsed = parseFloat(b.amountInput.replace(',', '.'));
          return {
            name: b.name.trim(),
            amount_minor: isNaN(parsed) ? 0 : Math.round(parsed * 100),
            months: Array.from(b.activeMonths).sort((a: any, b: any) => a - b)
          };
        })
        .filter(b => b.name && b.amount_minor > 0 && b.months.length > 0);

      saveBillsMutation.mutateAsync({
        category_id: category.category_id,
        year,
        bills: validBills
      }).then(() => {
        onClose();
      });
    } else {
      const rawAmount = amountInput.replace(',', '.');
      const parsedAmount = parseFloat(rawAmount);
      
      if (isNaN(parsedAmount) || parsedAmount < 0) return;

      const promises = [];
      
      for (let month = 1; month <= 12; month++) {
        const amountMinor = activeMonths.has(month) ? Math.round(parsedAmount * 100) : 0;
        promises.push(upsertMutation.mutateAsync({
          category_id: category.category_id,
          year,
          month,
          amount_minor: amountMinor,
          rollover
        }));
      }

      Promise.all(promises).then(() => {
        onClose();
      });
    }
  };

  const chartData = Array.from({ length: 12 }, (_, i) => {
    const monthNum = i + 1;
    const mData = category.months?.find((m: any) => m.month === monthNum);
    return {
      name: MONTH_INITIALS[i],
      [t('budgets.budgeted', 'Budget')]: mData ? Math.abs(mData.budgeted_minor) / 100 : 0,
      [t('budgets.actual', 'Faktisk')]: mData ? Math.abs(mData.actual_minor) / 100 : 0,
    };
  });

  return (
    <>
      <div 
        className="fixed inset-0 bg-black/50 z-40 lg:hidden"
        onClick={onClose}
      />
      
      <div className="fixed inset-y-0 right-0 w-full md:w-[450px] bg-[hsl(var(--bg-secondary))] shadow-2xl z-50 flex flex-col border-l border-[hsl(var(--border-color))]">
        <div className="flex items-center justify-between p-4 border-b border-[hsl(var(--border-color))]">
          <h2 className="text-lg font-semibold capitalize truncate pr-4">{label.replace('-', ' ')}</h2>
          <button 
            onClick={onClose}
            className="p-2 text-muted hover:text-[hsl(var(--text-primary))] rounded-full hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-muted">{t('budgets.yearly_overview', 'Årsoversigt')} {year}</h3>
            <div className="bg-[hsl(var(--bg-primary))] p-4 rounded-lg border border-[hsl(var(--border-color))] h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border-color))" />
                  <XAxis 
                    dataKey="name" 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fontSize: 10, fill: 'hsl(var(--text-secondary))' }} 
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fontSize: 10, fill: 'hsl(var(--text-secondary))' }}
                    tickFormatter={(value) => `${value}`}
                  />
                  <Tooltip 
                    cursor={{ fill: 'hsl(var(--bg-tertiary))' }}
                    contentStyle={{ backgroundColor: 'hsl(var(--bg-secondary))', borderColor: 'hsl(var(--border-color))', borderRadius: '8px' }}
                    itemStyle={{ color: 'hsl(var(--text-primary))' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  <Bar dataKey={t('budgets.budgeted', 'Budget')} fill="hsl(var(--text-secondary))" radius={[2, 2, 0, 0]} opacity={0.3} />
                  <Bar 
                    dataKey={t('budgets.actual', 'Faktisk')} 
                    fill="hsl(var(--brand-primary))" 
                    radius={[2, 2, 0, 0]} 
                    onClick={(data, index) => setSelectedMonth(selectedMonth !== null && index === selectedMonth - 1 ? null : index + 1)}
                    cursor="pointer"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={selectedMonth === index + 1 ? "hsl(var(--brand-secondary))" : "hsl(var(--brand-primary))"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-center text-muted">
              Tip: Klik på en måned i grafen for at se transaktionerne
            </p>
          </div>
          
          {selectedMonth && (
            <div className="space-y-3 animate-fade-in border-t border-[hsl(var(--border-color))] pt-6">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-[hsl(var(--text-primary))]">
                  Transaktioner i {MONTH_INITIALS[selectedMonth - 1]} {year}
                </h3>
                <div className="flex items-center gap-3">
                  <span className="text-xs bg-[hsl(var(--bg-tertiary))] px-2 py-1 rounded-full">
                    {monthTransactions.length}
                  </span>
                  <button
                    onClick={() => {
                      onClose();
                      navigate('/transactions', { 
                        state: { 
                          startDate, 
                          endDate, 
                          categoryId: category.category_id 
                        } 
                      });
                    }}
                    className="text-xs font-medium text-[hsl(var(--brand-primary))] hover:underline"
                  >
                    Se på transaktionssiden
                  </button>
                </div>
              </div>
              
              {isLoadingTx ? (
                <div className="flex justify-center p-4"><div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full"></div></div>
              ) : monthTransactions.length === 0 ? (
                <p className="text-sm text-muted text-center p-4">Ingen transaktioner i denne måned</p>
              ) : (
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
                  {monthTransactions.map((tx: any) => (
                    <div key={tx.id} className="bg-[hsl(var(--bg-primary))] p-3 rounded-lg border border-[hsl(var(--border-color))] flex justify-between items-center">
                      <div className="flex flex-col min-w-0 pr-4">
                        <span className="text-sm font-medium truncate">{tx.description}</span>
                        <span className="text-xs text-muted">{format(parseISO(tx.booking_date), 'dd. MMM', { locale: i18n.language === 'en' ? enUS : da })}</span>
                      </div>
                      <span className="text-sm font-medium whitespace-nowrap">
                        {(tx.amount_minor / 100).toLocaleString('da-DK')} kr.
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {isFixedOrIncome ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-[hsl(var(--text-primary))]">
                  {t('budgets.bills', 'Regninger')}
                </label>
              </div>
              
              <div className="space-y-4 border-b border-[hsl(var(--border-color))] pb-4">
                {bills.map((bill, index) => (
                  <div key={bill.id} className="p-4 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-lg space-y-3">
                    <div className="flex justify-between items-start gap-2">
                      <div className="flex-1">
                        <input
                          type="text"
                          value={bill.name}
                          onChange={(e) => {
                            const newBills = [...bills];
                            newBills[index].name = e.target.value;
                            setBills(newBills);
                          }}
                          placeholder={t('budgets.bill_name', 'Navn på regning (fx DM)')}
                          className="w-full bg-transparent border-b border-[hsl(var(--border-color))] p-1 text-sm text-[hsl(var(--text-primary))] focus:outline-none focus:border-[hsl(var(--brand-primary))]"
                        />
                      </div>
                      <div className="w-24">
                        <input
                          type="text"
                          value={bill.amountInput}
                          onChange={(e) => {
                            const newBills = [...bills];
                            newBills[index].amountInput = e.target.value;
                            setBills(newBills);
                          }}
                          placeholder="0,00"
                          className="w-full bg-transparent border-b border-[hsl(var(--border-color))] p-1 text-sm text-right text-[hsl(var(--text-primary))] focus:outline-none focus:border-[hsl(var(--brand-primary))]"
                        />
                      </div>
                      <span className="text-sm pt-1 text-muted">kr</span>
                      <button 
                        onClick={() => {
                          const newBills = bills.filter((_, i) => i !== index);
                          setBills(newBills);
                        }}
                        className="p-1 text-muted hover:text-[hsl(var(--brand-danger))] transition-colors"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    
                    <div className="flex justify-between gap-1 pt-1">
                      {MONTH_INITIALS.map((m, idx) => {
                        const monthNum = idx + 1;
                        const isActive = bill.activeMonths.has(monthNum);
                        return (
                          <button
                            key={m}
                            onClick={() => {
                              const newBills = [...bills];
                              const newActive = new Set(newBills[index].activeMonths);
                              if (newActive.has(monthNum)) {
                                newActive.delete(monthNum);
                              } else {
                                newActive.add(monthNum);
                              }
                              newBills[index].activeMonths = newActive;
                              setBills(newBills);
                            }}
                            className={`flex-1 py-1 text-[10px] font-medium rounded transition-colors border ${
                              isActive 
                                ? 'bg-[hsl(var(--brand-primary))] text-white border-[hsl(var(--brand-primary))]' 
                                : 'bg-[hsl(var(--bg-secondary))] text-muted border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))]'
                            }`}
                          >
                            {m.charAt(0)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}

                <Button 
                  variant="outline" 
                  size="sm"
                  className="w-full flex items-center justify-center gap-2"
                  onClick={() => {
                    setBills([...bills, { id: Math.random().toString(), name: '', amountInput: '', activeMonths: new Set() }]);
                  }}
                >
                  <Plus size={16} />
                  {t('budgets.add_bill', 'Tilføj regning')}
                </Button>
              </div>

              <div className="flex justify-between items-center text-sm font-medium">
                <span className="text-[hsl(var(--text-primary))]">{t('budgets.yearly_total', 'Samlet (pr. år)')}</span>
                <span className="text-[hsl(var(--brand-primary))]">
                  {bills.reduce((sum, b) => {
                    const parsedAmount = parseFloat(b.amountInput.replace(',', '.')) || 0;
                    return sum + (parsedAmount * b.activeMonths.size);
                  }, 0).toLocaleString('da-DK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr
                </span>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <label className="block text-sm font-medium text-[hsl(var(--text-primary))]">
                {t('budgets.monthly_amount', 'Budget (kr. pr. måned)')}
              </label>
              <input
                type="text"
                value={amountInput}
                onChange={(e) => setAmountInput(e.target.value)}
                placeholder="0,00"
                className="w-full bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-lg p-3 text-[hsl(var(--text-primary))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--brand-primary))]"
                disabled={isLoading}
              />
              
              <div className="pt-2">
                <label className="block text-xs font-medium text-muted mb-2">
                  {t('budgets.active_months', 'Gælder for følgende måneder:')}
                </label>
                <div className="grid grid-cols-6 gap-1.5">
                  {MONTH_INITIALS.map((m, idx) => {
                    const monthNum = idx + 1;
                    const isActive = activeMonths.has(monthNum);
                    return (
                      <button
                        key={m}
                        onClick={() => {
                          const newActive = new Set(activeMonths);
                          if (newActive.has(monthNum)) {
                            newActive.delete(monthNum);
                          } else {
                            newActive.add(monthNum);
                          }
                          setActiveMonths(newActive);
                        }}
                        className={`py-2 text-xs font-semibold rounded-md transition-colors border text-center ${
                          isActive 
                            ? 'bg-[hsl(var(--brand-primary))] text-white border-[hsl(var(--brand-primary))]' 
                            : 'bg-[hsl(var(--bg-primary))] text-muted border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))]'
                        }`}
                      >
                        {m}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between p-4 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-lg">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-[hsl(var(--brand-primary))] bg-opacity-20 text-[hsl(var(--brand-primary))] rounded-lg">
                <RefreshCw size={20} />
              </div>
              <div>
                <p className="font-medium text-sm text-[hsl(var(--text-primary))]">{t('budgets.rollover', 'Løbende budget')}</p>
                <p className="text-xs text-muted">{t('budgets.rollover_desc', 'Overfør overskud/underskud til næste måned')}</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                className="sr-only peer" 
                checked={rollover}
                onChange={(e) => setRollover(e.target.checked)}
                disabled={isLoading}
              />
              <div className="w-11 h-6 bg-[hsl(var(--bg-tertiary))] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[hsl(var(--brand-primary))]"></div>
            </label>
          </div>
        </div>

        <div className="p-4 border-t border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] flex justify-end gap-3">
          <Button variant="outline" onClick={onClose}>
            {t('common.cancel', 'Annuller')}
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={upsertMutation.isPending || saveBillsMutation.isPending || isLoading}
            className="flex items-center gap-2"
          >
            <Save size={16} />
            {upsertMutation.isPending || saveBillsMutation.isPending ? t('common.loading', 'Gemmer...') : t('common.save', 'Gem')}
          </Button>
        </div>
      </div>
    </>
  );
}
