import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Receipt,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Store,
  Layers,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Clock,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { useReceiptsStatus, useAutoLinkReceipts } from '../../api/domains/inbound';
import type { ImportRun } from '../../api/types';
import { toast } from 'sonner';

export function ReceiptsOverviewCard() {
  const { t } = useTranslation();
  const { data: status, isLoading, isError, refetch } = useReceiptsStatus();
  const autoLinkMutation = useAutoLinkReceipts();
  const [showHistory, setShowHistory] = React.useState(false);

  const handleAutoLink = () => {
    autoLinkMutation.mutate(undefined, {
      onSuccess: (data) => {
        toast.success(
          t('settings.receipts.relinkSuccess', {
            count: data.auto_linked_count,
            defaultValue: `Genkørsel fuldført! Matchede ${data.auto_linked_count} kvitteringer med dine posteringer.`,
          })
        );
      },
      onError: (err: any) => {
        toast.error('Kunne ikke matche kvitteringer: ' + (err?.message || 'Ukendt fejl'));
      },
    });
  };

  const formatTimestamp = (ts: string | null | undefined) => {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleString('da-DK', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  const getSourceLabel = (sourceType: string | undefined, sourcePath: string | undefined) => {
    const combined = `${sourceType || ''} ${sourcePath || ''}`.toLowerCase();
    if (combined.includes('coop')) return 'Coop';
    if (combined.includes('storebox')) return 'Storebox';
    if (combined.includes('mail') || combined.includes('inbound')) return 'E-mail';
    return 'Manuel import';
  };

  const matchRate = status?.match_rate_percent ?? 0;

  return (
    <Card className="overflow-hidden border border-[hsl(var(--border-color))] shadow-sm">
      <CardHeader className="bg-[hsl(var(--bg-secondary))]/30 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[hsl(var(--brand-primary))]/10 text-[hsl(var(--brand-primary))] flex items-center justify-center font-bold">
              <Receipt size={22} />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg">
                {t('settings.receipts.title', 'Kvitteringsoverblik & Synk-status')}
              </CardTitle>
              <p className="text-xs text-muted mt-0.5">
                {t(
                  'settings.receipts.description',
                  'Se samlet status for alle dine kvitteringer fra Storebox og Coop samt hvor mange der er koblet til dine bankposteringer.'
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Button
              size="sm"
              variant="outline"
              onClick={() => refetch()}
              disabled={isLoading}
              className="h-8 px-2.5 text-xs flex items-center gap-1.5"
              title="Opdater status"
            >
              <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
              <span className="hidden sm:inline">Opdater</span>
            </Button>
            <Button
              size="sm"
              onClick={handleAutoLink}
              disabled={autoLinkMutation.isPending || !status?.receipt_count}
              className="h-8 px-3 text-xs flex items-center gap-1.5 bg-[hsl(var(--brand-primary))] hover:opacity-90 text-white"
            >
              <Sparkles size={13} className={autoLinkMutation.isPending ? 'animate-spin' : ''} />
              <span>
                {autoLinkMutation.isPending
                  ? t('settings.receipts.relinking', 'Matcher kvitteringer...')
                  : t('settings.receipts.relinkButton', 'Genkør matching')}
              </span>
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-5">
        {isLoading && !status ? (
          <div className="py-8 flex items-center justify-center text-sm text-muted gap-2">
            <RefreshCw className="animate-spin" size={18} />
            Indlæser kvitteringsstatus...
          </div>
        ) : isError ? (
          <div className="py-6 text-center text-sm text-red-500">
            Kunne ikke hente kvitteringsstatus.
          </div>
        ) : (
          <>
            {/* Top Stat Badges Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Total Receipts */}
              <div className="p-3.5 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]/30 flex flex-col justify-between">
                <div className="flex items-center justify-between text-muted text-xs font-medium">
                  <span>{t('settings.receipts.totalReceipts', 'Total Kvitteringer')}</span>
                  <Receipt size={15} className="text-[hsl(var(--brand-primary))]" />
                </div>
                <div className="mt-2">
                  <div className="text-2xl font-bold text-[hsl(var(--text-color))]">
                    {status?.receipt_count ?? 0}
                  </div>
                  <div className="text-[11px] text-muted mt-0.5 flex items-center gap-1.5">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500" />
                    Storebox: <span className="font-semibold text-[hsl(var(--text-color))]">{status?.sources?.storebox ?? 0}</span>
                    <span className="mx-0.5">•</span>
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500" />
                    Coop: <span className="font-semibold text-[hsl(var(--text-color))]">{status?.sources?.coop ?? 0}</span>
                  </div>
                </div>
              </div>

              {/* Matched with Transactions */}
              <div className="p-3.5 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]/30 flex flex-col justify-between">
                <div className="flex items-center justify-between text-muted text-xs font-medium">
                  <span>{t('settings.receipts.matchedReceipts', 'Matchet med Bank')}</span>
                  <CheckCircle2 size={15} className="text-green-500" />
                </div>
                <div className="mt-2">
                  <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                    {status?.matched_receipt_count ?? 0}
                  </div>
                  <div className="text-[11px] text-muted mt-0.5">
                    {status?.matched_transaction_count ?? 0} matchede bankposteringer
                  </div>
                </div>
              </div>

              {/* Match Rate */}
              <div className="p-3.5 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]/30 flex flex-col justify-between">
                <div className="flex items-center justify-between text-muted text-xs font-medium">
                  <span>{t('settings.receipts.matchRate', 'Matchrate')}</span>
                  <span className="text-xs font-semibold text-[hsl(var(--brand-primary))]">
                    {matchRate}%
                  </span>
                </div>
                <div className="mt-2">
                  <div className="w-full bg-[hsl(var(--border-color))] h-2 rounded-full overflow-hidden mt-1.5 mb-2">
                    <div
                      className="bg-[hsl(var(--brand-primary))] h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.max(0, matchRate))}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-muted">
                    {status?.receipt_count
                      ? `${status.matched_receipt_count} af ${status.receipt_count} kvitteringer koblet`
                      : 'Ingen kvitteringer indlæst endnu'}
                  </div>
                </div>
              </div>

              {/* Products & Merchants */}
              <div className="p-3.5 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]/30 flex flex-col justify-between">
                <div className="flex items-center justify-between text-muted text-xs font-medium">
                  <span>{t('settings.receipts.itemClusters', 'Vare-produkter & Butikker')}</span>
                  <Layers size={15} className="text-purple-500" />
                </div>
                <div className="mt-2">
                  <div className="text-2xl font-bold text-[hsl(var(--text-color))]">
                    {status?.item_cluster_count ?? 0}
                  </div>
                  <div className="text-[11px] text-muted mt-0.5 flex items-center gap-1">
                    <Store size={12} className="inline" />
                    <span>{status?.merchant_count ?? 0} butikker genkendt</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Import & Sync History Section */}
            <div className="pt-2 border-t border-[hsl(var(--border-color))]/60">
              <button
                type="button"
                onClick={() => setShowHistory((prev) => !prev)}
                className="w-full flex items-center justify-between py-2 text-sm font-medium text-[hsl(var(--text-color))] hover:text-[hsl(var(--brand-primary))] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Clock size={16} className="text-[hsl(var(--brand-primary))]" />
                  <span>{t('settings.receipts.historyTitle', 'Seneste Importhistorik & Synkroniseringer')}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-[hsl(var(--bg-secondary))] text-muted border border-[hsl(var(--border-color))]">
                    {status?.recent_import_runs?.length ?? 0}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-xs text-muted">
                  <span>{showHistory ? 'Skjul' : 'Vis historik'}</span>
                  {showHistory ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </button>

              {showHistory && (
                <div className="mt-3 space-y-2">
                  {!status?.recent_import_runs || status.recent_import_runs.length === 0 ? (
                    <div className="p-4 text-center text-xs text-muted rounded-lg border border-dashed border-[hsl(var(--border-color))]">
                      {t('settings.receipts.noHistory', 'Ingen importhistorik endnu.')}
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left">
                        <thead>
                          <tr className="border-b border-[hsl(var(--border-color))] text-muted">
                            <th className="py-2 px-3 font-medium">Tidspunkt</th>
                            <th className="py-2 px-3 font-medium">Kilde</th>
                            <th className="py-2 px-3 font-medium">Status</th>
                            <th className="py-2 px-3 font-medium">Kvitteringer</th>
                            <th className="py-2 px-3 font-medium">Filer</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[hsl(var(--border-color))]/50">
                          {status.recent_import_runs.map((run: ImportRun) => (
                            <tr key={run.id} className="hover:bg-[hsl(var(--bg-secondary))]/40">
                              <td className="py-2 px-3 font-medium whitespace-nowrap">
                                {formatTimestamp(run.completed_at || run.started_at)}
                              </td>
                              <td className="py-2 px-3">
                                <span className="inline-flex items-center gap-1 font-medium">
                                  {getSourceLabel(run.source_type, run.source_path)}
                                </span>
                              </td>
                              <td className="py-2 px-3">
                                {run.status === 'completed' ? (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20">
                                    <CheckCircle2 size={10} />
                                    {t('settings.receipts.statusCompleted', 'Gennemført')}
                                  </span>
                                ) : run.status === 'running' ? (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                                    <RefreshCw size={10} className="animate-spin" />
                                    {t('settings.receipts.statusRunning', 'Kører')}
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
                                    <AlertCircle size={10} />
                                    {t('settings.receipts.statusFailed', 'Fejlet')}
                                  </span>
                                )}
                              </td>
                              <td className="py-2 px-3 font-semibold">
                                {run.deduplicated_receipt_count} kvitteringer
                              </td>
                              <td className="py-2 px-3 text-muted">
                                {run.source_file_count} fil{run.source_file_count === 1 ? '' : 'er'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
