import React, { useState, useMemo, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/Card';
import { motion, AnimatePresence } from 'framer-motion';
import { useAccounts, useConnectBank, useUpdateAccount, useAccountBalanceHistory } from '../api/client';
import { Skeleton } from '../components/ui/Skeleton';
import { Button } from '../components/ui/Button';
import { Plus, Building2, Loader2, Pencil, ChevronDown, ChevronUp, Save, X } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

function AccountHistoryChart({ uid }: { uid: string }) {
  const { data: history, isLoading } = useAccountBalanceHistory(uid, 365);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  
  if (isLoading) return <Skeleton className="h-48 w-full mt-4" />;
  if (!history || history.length === 0) return <div className="p-4 text-center text-muted">Ingen historik fundet.</div>;

  return (
    <div className="h-48 w-full mt-6 pt-6 border-t border-[hsl(var(--border-color))]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={history} margin={{ top: 5, right: 5, left: isMobile ? -10 : 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border-color))" />
          <XAxis 
            dataKey="date" 
            tickFormatter={(val) => new Date(val).toLocaleDateString('da-DK', { month: 'short' })}
            minTickGap={30}
            stroke="hsl(var(--text-secondary))"
            fontSize={12}
          />
          <YAxis 
            tickFormatter={(val) => (val / 100).toLocaleString('da-DK')} 
            domain={['auto', 'auto']}
            stroke="hsl(var(--text-secondary))"
            width={isMobile ? 50 : 70}
            fontSize={12}
          />
          <Tooltip 
            formatter={(value: any) => [(value / 100).toLocaleString('da-DK', { style: 'currency', currency: 'DKK' }), 'Saldo']}
            labelFormatter={(label) => new Date(label).toLocaleDateString('da-DK', { dateStyle: 'long' })}
            contentStyle={{ backgroundColor: 'hsl(var(--bg-secondary))', borderColor: 'hsl(var(--border-color))', borderRadius: '8px', color: 'hsl(var(--text-primary))' }}
            itemStyle={{ color: 'hsl(var(--text-primary))' }}
          />
          <Line 
            type="stepAfter" 
            dataKey="balance_minor" 
            stroke="hsl(var(--brand-primary))" 
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

import CategoryPicker from '../components/ui/CategoryPicker';

export default function AccountsPage() {
  const { t } = useTranslation();
  const { data: accounts, isLoading } = useAccounts();
  const connectBank = useConnectBank();
  const updateAccount = useUpdateAccount();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState("Indlån");
  const [editSavingsCat, setEditSavingsCat] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleEdit = (acc: any, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(acc.uid);
    setEditName(acc.name);
    setEditType(acc.account_type || "Indlån");
    setEditSavingsCat(acc.savings_category_id || null);
  };

  const handleSave = (uid: string, e?: React.FormEvent) => {
    e?.preventDefault();
    if (editName.trim()) {
      updateAccount.mutate({ 
        uid, 
        name: editName.trim(), 
        account_type: editType,
        savings_category_id: editType === 'Opsparing' ? editSavingsCat : null
      });
    }
    setEditingId(null);
  };

  const handleConnectBank = () => {
    connectBank.mutate(window.location.origin + '/dashboard', {
      onSuccess: (data) => {
        if (data.auth_url) {
          window.location.href = data.auth_url;
        }
      }
    });
  };

  const groupedAccounts = useMemo(() => {
    if (!accounts) return {};
    const groups: Record<string, any[]> = {};
    accounts.forEach((acc: any) => {
      const type = acc.account_type || "Indlån";
      if (!groups[type]) groups[type] = [];
      groups[type].push(acc);
    });
    return groups;
  }, [accounts]);

  const groupOrder = ["Indlån", "Opsparing", "Kredit", "Pension"];

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-4 md:p-8 max-w-4xl mx-auto space-y-6"
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <motion.h1 
            initial={{ y: -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="text-3xl font-bold text-[hsl(var(--text-primary))]"
          >
            {t('app.accounts')}
          </motion.h1>
          <motion.p 
            initial={{ y: -5, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-muted mt-2"
          >
            Få et overblik over dine konti og deres historiske udvikling.
          </motion.p>
        </div>
        <Button 
          onClick={handleConnectBank} 
          disabled={connectBank.isPending}
          className="flex items-center gap-2"
        >
          {connectBank.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
          {t('accounts.add_bank')}
        </Button>
      </div>

      <div className="space-y-8">
        {isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {!isLoading && (!accounts || accounts.length === 0) && (
          <Card className="bg-[hsla(var(--bg-tertiary),0.5)] border-dashed border-2">
            <CardContent className="flex flex-col items-center justify-center p-12 text-center text-muted">
              <Building2 size={48} className="mb-4 text-[hsl(var(--text-secondary))] opacity-50" />
              <h3 className="text-lg font-semibold mb-2">{t('accounts.no_accounts')}</h3>
              <p className="max-w-md mb-6">{t('accounts.no_accounts_desc')}</p>
              <Button onClick={handleConnectBank} disabled={connectBank.isPending} className="flex items-center gap-2">
                {connectBank.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                {t('accounts.connect_bank')}
              </Button>
            </CardContent>
          </Card>
        )}

        {!isLoading && groupOrder.map((group) => {
          const groupAccs = groupedAccounts[group] || [];
          if (groupAccs.length === 0) return null;
          
          const groupTotal = groupAccs.reduce((sum, a) => sum + (a.balance_minor || 0), 0);
          
          return (
            <div key={group} className="space-y-4">
              <div className="flex items-center justify-between px-2">
                <h2 className="text-xl font-semibold text-[hsl(var(--text-secondary))]">{group}</h2>
                <span className={`font-semibold ${groupTotal < 0 ? 'text-[hsl(var(--brand-danger))]' : 'text-[hsl(var(--text-primary))]'}`}>
                  {(groupTotal / 100).toLocaleString('da-DK', { style: 'currency', currency: 'DKK' })}
                </span>
              </div>
              
              <div className="grid gap-4">
                {groupAccs.map((acc: any, index: number) => (
                  <motion.div 
                    key={acc.uid}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <Card 
                      className={`transition-colors cursor-pointer group border ${expandedId === acc.uid ? 'border-[hsl(var(--brand-primary))] shadow-sm' : 'border-[hsl(var(--border-color))] hover:border-[hsl(var(--text-secondary))]'}`}
                      onClick={() => setExpandedId(expandedId === acc.uid ? null : acc.uid)}
                    >
                      <CardContent className="p-5">
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            {editingId === acc.uid ? (
                                <div className="flex flex-col gap-2 w-full md:w-auto">
                                  <div className="flex flex-col md:flex-row items-start md:items-center gap-2" onClick={e => e.stopPropagation()}>
                                    <input
                                      autoFocus
                                      value={editName}
                                      onChange={(e) => setEditName(e.target.value)}
                                      onKeyDown={(e) => {
                                        if (e.key === 'Enter') handleSave(acc.uid, e as any);
                                        if (e.key === 'Escape') setEditingId(null);
                                      }}
                                      className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded px-2 py-1 outline-none focus:border-[hsl(var(--brand-primary))]"
                                    />
                                    <select 
                                      value={editType} 
                                      onChange={(e) => setEditType(e.target.value)}
                                      className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded px-2 py-1 outline-none focus:border-[hsl(var(--brand-primary))]"
                                    >
                                      {groupOrder.map(g => <option key={g} value={g}>{g}</option>)}
                                    </select>
                                    <div className="flex gap-1 mt-2 md:mt-0">
                                      <Button size="sm" onClick={(e) => handleSave(acc.uid, e as any)}><Save size={14} className="mr-1" /> Gem</Button>
                                      <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}><X size={14} /></Button>
                                    </div>
                                  </div>
                                  {editType === 'Opsparing' && (
                                    <div className="mt-2 w-full max-w-sm" onClick={e => e.stopPropagation()}>
                                      <label className="text-xs text-muted block mb-1">Opsparingskategori (valgfri)</label>
                                      <CategoryPicker 
                                        value={editSavingsCat || undefined} 
                                        onChange={setEditSavingsCat}
                                        filterMainCategory="Pension & Opsparing"
                                      />
                                    </div>
                                  )}
                                </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-lg">{acc.name}</span>
                                <button onClick={(e) => handleEdit(acc, e)} className="p-1 rounded-md text-muted hover:text-[hsl(var(--brand-primary))] hover:bg-[hsla(var(--brand-primary),0.1)] opacity-0 group-hover:opacity-100 transition-all">
                                  <Pencil size={14} />
                                </button>
                              </div>
                            )}
                            <p className="text-sm text-muted mt-1">{acc.bank_connection?.bank_name || t('accounts.unknown_bank')} &middot; {acc.currency || 'DKK'}</p>
                          </div>
                          
                          <div className="flex items-center gap-4 text-right">
                            <div>
                              <p className={`font-bold text-xl ${acc.balance_minor < 0 ? 'text-[hsl(var(--brand-danger))]' : 'text-[hsl(var(--text-primary))]'}`}>
                                {acc.balance_minor ? (acc.balance_minor / 100).toLocaleString('da-DK', { style: 'currency', currency: 'DKK' }) : '0,00 kr.'}
                              </p>
                            </div>
                            <div className="text-muted">
                              {expandedId === acc.uid ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                            </div>
                          </div>
                        </div>

                        <AnimatePresence>
                          {expandedId === acc.uid && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <AccountHistoryChart uid={acc.uid} />
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
