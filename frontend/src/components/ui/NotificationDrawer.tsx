import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  X,
  CheckCheck,
  Check,
  AlertTriangle,
  Landmark,
  Sparkles,
  Lightbulb,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  Inbox,
  Filter,
} from 'lucide-react';
import { useNotifications, useCreateCustomRule, AppNotification } from '../../api/client';
import { useQueryClient } from '@tanstack/react-query';

interface NotificationDrawerProps {
  compact?: boolean;
}

const STORAGE_KEY = 'peng_read_notifications';

export default function NotificationDrawer({ compact = false }: NotificationDrawerProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isOpen, setIsOpen] = useState(false);
  const [readIds, setReadIds] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [activeTab, setActiveTab] = useState<'all' | 'warnings' | 'suggestions' | 'info'>('all');
  const [ruleCreationSuccess, setRuleCreationSuccess] = useState<Record<string, boolean>>({});

  const { data, isLoading } = useNotifications();
  const createRuleMutation = useCreateCustomRule();

  const notifications = data?.notifications || [];

  // Persist readIds to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(readIds)));
    } catch (e) {
      console.error('Failed to save read notifications', e);
    }
  }, [readIds]);

  // Calculate unread count
  const unreadCount = useMemo(() => {
    return notifications.filter((n) => !readIds.has(n.id)).length;
  }, [notifications, readIds]);

  const markAsRead = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setReadIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  };

  const markAllAsRead = () => {
    setReadIds(new Set(notifications.map((n) => n.id)));
  };

  const handleCreateRule = (notif: AppNotification, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!notif.action_payload) return;

    createRuleMutation.mutate(
      {
        matchPattern: notif.action_payload.match_pattern,
        categoryId: notif.action_payload.category_id,
      },
      {
        onSuccess: () => {
          setRuleCreationSuccess((prev) => ({ ...prev, [notif.id]: true }));
          markAsRead(notif.id);
          queryClient.invalidateQueries({ queryKey: ['rules'] });
          queryClient.invalidateQueries({ queryKey: ['transactions'] });
          queryClient.invalidateQueries({ queryKey: ['notifications'] });
        },
      }
    );
  };

  const handleNotificationClick = (notif: AppNotification) => {
    markAsRead(notif.id);

    if (notif.type === 'duplicate_payment') {
      const search = notif.metadata?.description || '';
      navigate('/transactions', { state: { search } });
      setIsOpen(false);
    } else if (notif.type === 'consent_expiring') {
      navigate('/accounts');
      setIsOpen(false);
    } else if (notif.type === 'receipts_linked') {
      navigate('/transactions');
      setIsOpen(false);
    }
  };

  const filteredNotifications = useMemo(() => {
    if (activeTab === 'warnings') {
      return notifications.filter((n) => n.severity === 'warning' || n.severity === 'danger');
    }
    if (activeTab === 'suggestions') {
      return notifications.filter((n) => n.severity === 'suggestion');
    }
    if (activeTab === 'info') {
      return notifications.filter((n) => n.severity === 'info');
    }
    return notifications;
  }, [notifications, activeTab]);

  return (
    <>
      {/* Trigger Bell Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="relative p-2 rounded-full hover:bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] transition-all shrink-0"
        title={t('notifications.title', 'Notifikationer')}
        aria-label={t('notifications.title', 'Notifikationer')}
      >
        <Bell size={compact ? 18 : 20} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-[hsl(var(--brand-danger))] text-white text-[10px] font-bold rounded-full flex items-center justify-center shadow-md animate-pulse">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Slide-over Drawer & Backdrop */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-xs z-[80]"
            />

            {/* Slide-in Panel */}
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 26, stiffness: 280 }}
              className="fixed top-0 right-0 h-full w-full max-w-md bg-[hsl(var(--bg-primary))] border-l border-[hsl(var(--border-color))] shadow-2xl z-[90] flex flex-col overflow-hidden"
            >
              {/* Header */}
              <div className="p-5 border-b border-[hsl(var(--border-color))] flex items-center justify-between bg-[hsl(var(--bg-secondary))]">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-[hsla(var(--brand-primary),0.1)] flex items-center justify-center text-[hsl(var(--brand-primary))]">
                    <Bell size={18} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-[hsl(var(--text-primary))] leading-none">
                      {t('notifications.title', 'Notifikationer')}
                    </h2>
                    {unreadCount > 0 ? (
                      <span className="text-xs text-[hsl(var(--brand-primary))] font-medium">
                        {t('notifications.unreadCount', { count: unreadCount, defaultValue: `${unreadCount} ulæste` })}
                      </span>
                    ) : (
                      <span className="text-xs text-muted">
                        {notifications.length} {t('notifications.all', 'i alt').toLowerCase()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllAsRead}
                      className="text-xs text-muted hover:text-[hsl(var(--text-primary))] flex items-center gap-1 p-1.5 px-2.5 rounded-lg hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
                      title={t('notifications.markAllAsRead', 'Marker alle som læst')}
                    >
                      <CheckCheck size={14} />
                      <span className="hidden sm:inline">{t('notifications.markAllAsRead', 'Marker alle som læst')}</span>
                    </button>
                  )}
                  <button
                    onClick={() => setIsOpen(false)}
                    className="p-2 rounded-full hover:bg-[hsl(var(--bg-tertiary))] text-muted hover:text-[hsl(var(--text-primary))] transition-colors"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              {/* Filter Tabs */}
              {notifications.length > 0 && (
                <div className="flex items-center gap-1 p-3 border-b border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]/50 overflow-x-auto">
                  <button
                    onClick={() => setActiveTab('all')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 ${
                      activeTab === 'all'
                        ? 'bg-[hsl(var(--brand-primary))] text-white shadow-sm'
                        : 'text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))]'
                    }`}
                  >
                    {t('notifications.all', 'Alle')} ({notifications.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('warnings')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 ${
                      activeTab === 'warnings'
                        ? 'bg-[hsl(var(--brand-primary))] text-white shadow-sm'
                        : 'text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))]'
                    }`}
                  >
                    {t('notifications.warnings', 'Advarsler')} (
                    {notifications.filter((n) => n.severity === 'warning' || n.severity === 'danger').length})
                  </button>
                  <button
                    onClick={() => setActiveTab('suggestions')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 ${
                      activeTab === 'suggestions'
                        ? 'bg-[hsl(var(--brand-primary))] text-white shadow-sm'
                        : 'text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))]'
                    }`}
                  >
                    {t('notifications.suggestions', 'Forslag')} (
                    {notifications.filter((n) => n.severity === 'suggestion').length})
                  </button>
                  <button
                    onClick={() => setActiveTab('info')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 ${
                      activeTab === 'info'
                        ? 'bg-[hsl(var(--brand-primary))] text-white shadow-sm'
                        : 'text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))]'
                    }`}
                  >
                    {t('notifications.info', 'Info')} (
                    {notifications.filter((n) => n.severity === 'info').length})
                  </button>
                </div>
              )}

              {/* Notification List Content */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {isLoading ? (
                  <div className="space-y-3 py-4">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-24 bg-[hsl(var(--bg-secondary))] animate-pulse rounded-xl" />
                    ))}
                  </div>
                ) : filteredNotifications.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
                    <div className="w-16 h-16 rounded-full bg-[hsla(var(--brand-primary),0.1)] flex items-center justify-center text-[hsl(var(--brand-primary))] mb-2">
                      <Inbox size={32} />
                    </div>
                    <h3 className="font-bold text-base text-[hsl(var(--text-primary))]">
                      {t('notifications.empty', 'Ingen nye notifikationer')}
                    </h3>
                    <p className="text-sm text-muted max-w-xs">
                      {t('notifications.emptyDesc', 'Alt ser godt ud i din økonomi!')}
                    </p>
                  </div>
                ) : (
                  filteredNotifications.map((notif) => {
                    const isRead = readIds.has(notif.id);
                    const isRuleCreated = ruleCreationSuccess[notif.id];

                    // Styling tokens per severity
                    const isWarning = notif.severity === 'warning' || notif.severity === 'danger';
                    const isSuggestion = notif.severity === 'suggestion';
                    const isInfo = notif.severity === 'info';

                    let cardBorder = 'border-[hsl(var(--border-color))]';
                    let iconBg = 'bg-blue-500/10 text-blue-500';
                    let IconComponent = Sparkles;

                    if (isWarning) {
                      cardBorder = isRead
                        ? 'border-[hsl(var(--border-color))]'
                        : 'border-amber-500/40 bg-amber-500/5';
                      iconBg = 'bg-amber-500/15 text-amber-500';
                      IconComponent = notif.type === 'consent_expiring' ? ShieldAlert : AlertTriangle;
                    } else if (isSuggestion) {
                      cardBorder = isRead
                        ? 'border-[hsl(var(--border-color))]'
                        : 'border-purple-500/40 bg-purple-500/5';
                      iconBg = 'bg-purple-500/15 text-purple-500';
                      IconComponent = Lightbulb;
                    } else if (isInfo) {
                      iconBg = 'bg-blue-500/15 text-blue-500';
                      IconComponent = Sparkles;
                    }

                    return (
                      <motion.div
                        key={notif.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        onClick={() => handleNotificationClick(notif)}
                        className={`group relative p-4 rounded-xl border transition-all cursor-pointer bg-[hsl(var(--bg-secondary))] hover:border-[hsl(var(--brand-primary))] hover:shadow-md ${cardBorder}`}
                      >
                        {/* Unread indicator dot */}
                        {!isRead && (
                          <span className="absolute top-4 right-4 w-2.5 h-2.5 rounded-full bg-[hsl(var(--brand-primary))] ring-4 ring-[hsl(var(--bg-secondary))]" />
                        )}

                        <div className="flex items-start gap-3">
                          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${iconBg}`}>
                            <IconComponent size={18} />
                          </div>

                          <div className="flex-1 min-w-0 pr-4">
                            <div className="flex items-center gap-2 mb-1">
                              <h4 className="text-sm font-bold text-[hsl(var(--text-primary))] truncate">
                                {notif.title}
                              </h4>
                            </div>

                            <p className="text-xs text-muted leading-relaxed mb-3">
                              {notif.message}
                            </p>

                            {/* Specific Actions */}
                            {notif.type === 'rule_suggestion' && (
                              <div className="pt-1">
                                {isRuleCreated ? (
                                  <div className="inline-flex items-center gap-1 text-xs font-semibold text-green-500 bg-green-500/10 px-3 py-1.5 rounded-lg">
                                    <Check size={14} /> Regel oprettet!
                                  </div>
                                ) : (
                                  <button
                                    onClick={(e) => handleCreateRule(notif, e)}
                                    disabled={createRuleMutation.isPending}
                                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary-dark))] px-3 py-1.5 rounded-lg shadow-sm transition-all"
                                  >
                                    <Sparkles size={13} />
                                    {createRuleMutation.isPending
                                      ? t('common.saving', 'Gemmer...')
                                      : t('notifications.createRule', 'Opret regel')}
                                  </button>
                                )}
                              </div>
                            )}

                            {notif.type === 'duplicate_payment' && (
                              <div className="pt-1 flex items-center gap-2">
                                <span className="inline-flex items-center gap-1 text-xs font-semibold text-[hsl(var(--brand-primary))] group-hover:underline">
                                  {t('notifications.viewTransactions', 'Gå til posteringer')}
                                  <ChevronRight size={14} />
                                </span>
                              </div>
                            )}

                            {notif.type === 'consent_expiring' && (
                              <div className="pt-1 flex items-center gap-2">
                                <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-500 group-hover:underline">
                                  {t('notifications.renewConsent', 'Forny samtykke')}
                                  <ChevronRight size={14} />
                                </span>
                              </div>
                            )}

                            {notif.type === 'receipts_linked' && (
                              <div className="pt-1 flex items-center gap-2">
                                <span className="inline-flex items-center gap-1 text-xs font-semibold text-[hsl(var(--brand-primary))] group-hover:underline">
                                  {t('notifications.viewTransactions', 'Gå til posteringer')}
                                  <ChevronRight size={14} />
                                </span>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Mark read button on hover */}
                        {!isRead && (
                          <button
                            onClick={(e) => markAsRead(notif.id, e)}
                            className="absolute bottom-3 right-3 p-1.5 rounded-lg text-muted hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] opacity-0 group-hover:opacity-100 transition-opacity"
                            title={t('notifications.markAsRead', 'Marker som læst')}
                          >
                            <Check size={14} />
                          </button>
                        )}
                      </motion.div>
                    );
                  })
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
