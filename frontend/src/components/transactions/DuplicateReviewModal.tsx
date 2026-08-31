import React from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  X,
  CheckCheck,
  ShieldCheck,
  Info,
  Layers,
  ArrowRight,
  ExternalLink,
  Receipt,
  FileText,
  EyeOff,
  Check,
} from 'lucide-react';
import {
  useDuplicatePreview,
  useResolveDuplicates,
  useDismissDuplicate,
  useDismissAllDuplicates,
  DuplicateGroupPreview,
  DuplicatePostingItem,
} from '../../api/client';
import { toast } from 'sonner';

interface DuplicateReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  onFilterTransactions?: () => void;
}

export default function DuplicateReviewModal({
  isOpen,
  onClose,
  onFilterTransactions,
}: DuplicateReviewModalProps) {
  const { t, i18n } = useTranslation();
  const { data, isLoading, refetch } = useDuplicatePreview(isOpen);
  const resolveDuplicatesMutation = useResolveDuplicates();
  const dismissDuplicateMutation = useDismissDuplicate();
  const dismissAllMutation = useDismissAllDuplicates();

  if (!isOpen) return null;

  const groups = data?.groups || [];
  const mergeableCount = data?.mergeable_groups_count || 0;
  const totalGroups = data?.total_groups || 0;
  const sameAccountCount = totalGroups - mergeableCount;

  const handleResolve = () => {
    resolveDuplicatesMutation.mutate(undefined, {
      onSuccess: (res: any) => {
        toast.success(
          t('duplicates.resolveSuccess', '{{count}} dubletter blev løst og konsolideret!', {
            count: res?.resolved_duplicates_count || 0,
          })
        );
        refetch();
      },
      onError: () => {
        toast.error(t('duplicates.resolveError', 'Kunne ikke løse dubletter automatisk'));
      },
    });
  };

  const handleDismissGroup = (group: DuplicateGroupPreview) => {
    const ids = group.postings.map((p) => p.id);
    dismissDuplicateMutation.mutate(
      { transaction_ids: ids },
      {
        onSuccess: () => {
          toast.success(t('duplicates.dismissSuccess', 'Markeret som separate posteringer'));
          refetch();
        },
        onError: () => {
          toast.error(t('duplicates.dismissError', 'Kunne ikke afvise dublet'));
        },
      }
    );
  };

  const handleDismissAllSameAccount = () => {
    dismissAllMutation.mutate(undefined, {
      onSuccess: (res: any) => {
        toast.success(
          t('duplicates.dismissAllSuccess', '{{count}} posteringer markeret som separate', {
            count: res?.dismissed_count || 0,
          })
        );
        refetch();
      },
      onError: () => {
        toast.error(t('duplicates.dismissError', 'Kunne ikke afvise dubletter'));
      },
    });
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-xs"
        />

        {/* Modal Window */}
        <motion.div
          initial={{ scale: 0.95, opacity: 0, y: 15 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.95, opacity: 0, y: 15 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="relative w-full max-w-2xl max-h-[85vh] bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-2xl shadow-2xl overflow-hidden flex flex-col z-10"
        >
          {/* Header */}
          <div className="p-5 border-b border-[hsl(var(--border-color))] flex items-center justify-between bg-[hsl(var(--bg-secondary))]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500 shrink-0">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-[hsl(var(--text-primary))] leading-tight">
                  {t('duplicates.modalTitle', 'Gennemgå mulige dubletter')}
                </h3>
                <p className="text-xs text-muted mt-0.5">
                  {t('duplicates.modalSubtitle', 'Forskellen på reelle køb og arkiv-overlap')}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Content Body */}
          <div className="p-5 overflow-y-auto space-y-4 flex-1">
            {/* Educational Info Box */}
            <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs space-y-2.5 text-[hsl(var(--text-primary))]">
              <div className="flex items-center gap-2 font-semibold text-blue-600 dark:text-blue-400">
                <ShieldCheck size={16} />
                <span>{t('duplicates.howItWorksTitle', 'Sådan beskytter Peng dine data')}</span>
              </div>
              <p className="leading-relaxed text-[hsl(var(--text-secondary))]">
                {t(
                  'duplicates.howItWorksBody',
                  'Peng advarer, hvis to posteringer har samme dato og beløb. Hvis du har købt to ting i samme forretning samme dag på samme konto, er det reelle køb og skal IKKE slettes. Automatisk sammenlægning fletter KUN posteringer mellem en gammel Spiir/CSV-arkivkonto og en aktiv bankkonto.'
                )}
              </p>
            </div>

            {/* Candidate List */}
            {isLoading && (
              <div className="py-8 text-center text-sm text-muted">
                {t('common.loading', 'Henter mulige dubletter...')}
              </div>
            )}

            {!isLoading && groups.length === 0 && (
              <div className="py-10 text-center space-y-2">
                <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
                  <CheckCheck size={24} />
                </div>
                <div className="font-semibold text-sm text-[hsl(var(--text-primary))]">
                  {t('duplicates.noneFound', 'Ingen dubletter fundet')}
                </div>
                <div className="text-xs text-muted">
                  {t(
                    'duplicates.noneFoundDesc',
                    'Dine transaktioner har ingen uafklarede overlap.'
                  )}
                </div>
              </div>
            )}

            {!isLoading && groups.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold text-muted uppercase tracking-wider px-1">
                  <span>
                    {t('duplicates.detectedGroups', 'Fundne grupper ({{count}})', {
                      count: totalGroups,
                    })}
                  </span>
                  {mergeableCount > 0 && (
                    <span className="text-emerald-600 dark:text-emerald-400">
                      {t('duplicates.mergeableCount', '{{count}} kan flettes', {
                        count: mergeableCount,
                      })}
                    </span>
                  )}
                </div>

                {groups.map((group: DuplicateGroupPreview) => (
                  <div
                    key={group.group_id}
                    className="p-3.5 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] space-y-3"
                  >
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <div>
                        <div className="font-semibold text-sm text-[hsl(var(--text-primary))]">
                          {group.description || t('transactions.noDescription', 'Uden beskrivelse')}
                        </div>
                        <div className="text-xs text-muted mt-0.5">
                          {group.date} • {group.amount} kr.
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {group.can_auto_merge ? (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                            <Layers size={11} />
                            {t('duplicates.archiveOverlap', 'Arkiv-overlap (kan flettes)')}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30 flex items-center gap-1">
                            <Info size={11} />
                            {t('duplicates.sameAccountSeparate', 'Samme konto (2 separate køb)')}
                          </span>
                        )}

                        <button
                          onClick={() => handleDismissGroup(group)}
                          disabled={dismissDuplicateMutation.isPending}
                          className="px-2 py-0.5 rounded-lg text-[11px] font-semibold text-muted hover:text-[hsl(var(--text-primary))] bg-[hsl(var(--bg-tertiary))] hover:bg-[hsl(var(--border-color))] border border-[hsl(var(--border-color))] flex items-center gap-1 transition-colors disabled:opacity-50"
                          title={t(
                            'duplicates.dismissTooltip',
                            'Marker disse posteringer som separate køb (skjul advarsel)'
                          )}
                        >
                          <EyeOff size={11} />
                          <span>{t('duplicates.markAsNotDuplicate', 'Ikke en dublet')}</span>
                        </button>
                      </div>
                    </div>

                    {/* Postings inside this group */}
                    <div className="space-y-1.5 pt-1 border-t border-[hsl(var(--border-color))]">
                      {group.postings.map((p: DuplicatePostingItem) => (
                        <div
                          key={p.id}
                          className="flex items-center justify-between text-xs p-2.5 rounded-lg bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))]"
                        >
                          <div className="flex flex-col min-w-0 flex-1 mr-3">
                            <div className="font-medium text-[hsl(var(--text-primary))] truncate text-[13px]">
                              {p.original_description ||
                                group.description ||
                                t('transactions.noDescription', 'Uden beskrivelse')}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5 text-[11px] text-muted">
                              <span>{p.account_name}</span>
                              <span>•</span>
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-black/10 dark:bg-white/10 uppercase font-mono">
                                {p.account_source}
                              </span>
                              {p.note && (
                                <>
                                  <span>•</span>
                                  <span className="italic truncate max-w-[200px]">
                                    &quot;{p.note}&quot;
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                          <div className="font-mono text-xs shrink-0 font-semibold text-[hsl(var(--text-primary))]">
                            {p.amount} kr.
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="p-4 border-t border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  onClose();
                  if (onFilterTransactions) onFilterTransactions();
                }}
                className="px-3 py-2 text-xs font-semibold text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] rounded-lg transition-colors flex items-center gap-1.5"
              >
                <ExternalLink size={14} />
                <span>{t('duplicates.viewInTransactions', 'Vis i transaktionslisten')}</span>
              </button>

              {sameAccountCount > 0 && (
                <button
                  onClick={handleDismissAllSameAccount}
                  disabled={dismissAllMutation.isPending}
                  className="px-3 py-2 text-xs font-semibold text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] rounded-lg transition-colors flex items-center gap-1.5 border border-dashed border-[hsl(var(--border-color))]"
                  title={t(
                    'duplicates.dismissAllTooltip',
                    'Skjul advarsler for alle separate posteringer på samme konto'
                  )}
                >
                  <EyeOff size={13} />
                  <span>
                    {t(
                      'duplicates.dismissAllSameAccount',
                      'Afvis alle som ikke-dubletter ({{count}})',
                      { count: sameAccountCount }
                    )}
                  </span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] rounded-lg transition-colors"
              >
                {t('common.close', 'Luk')}
              </button>

              {mergeableCount > 0 && (
                <button
                  onClick={handleResolve}
                  disabled={resolveDuplicatesMutation.isPending}
                  className="px-4 py-2 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white rounded-lg shadow-sm flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  <CheckCheck size={14} />
                  <span>
                    {resolveDuplicatesMutation.isPending
                      ? t('duplicates.resolving', 'Løser...')
                      : t('duplicates.mergeArchivePairs', 'Flet arkiv-dupletter ({{count}})', {
                          count: mergeableCount,
                        })}
                  </span>
                </button>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
