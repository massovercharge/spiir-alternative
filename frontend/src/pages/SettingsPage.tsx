import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useTheme } from '../theme/ThemeProvider';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { SUPPORTED_BANKS } from '../api/constants';
import {
  Moon,
  Sun,
  Monitor,
  Languages,
  Building2,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  CheckCircle,
  ListFilter,
  Link as LinkIcon,
  ShoppingBag,
  FileText,
  Copy,
  Check,
  Inbox,
  RotateCcw,
  Send,
  AlertCircle,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import {
  useBankConnections,
  useConnectBank,
  useDeleteBankConnection,
  useStartSync,
  useSyncStatus,
  useUploadSpiirExport,
  useRules,
  useDeleteRule,
  useHouseholdMembers,
  useInviteHouseholdMember,
  useCreateHousehold,
  useUpdateHousehold,
  useUploadStoreboxFile,
  useUploadCoopFile,
  useImportStoreboxLink,
  useRemoveHouseholdMember,
  useDeleteHousehold,
  useRestoreHousehold,
  useUpdateHouseholdMemberRole,
  useInboundConfig,
  useInboundEmails,
  useSimulateInboundEmail,
  useRetryInboundEmail,
  useRegenerateInboundToken,
  useDeleteInboundEmail,
  useClearInboundEmails,
} from '../api/client';
import { buildCoopBookmarkletHref } from '../features/receipts/coopBookmarklet';
import { ReceiptsOverviewCard } from '../features/receipts/ReceiptsOverviewCard';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '../components/ui/Button';
import { useHousehold } from '../context/HouseholdContext';
import { Users, Mail } from 'lucide-react';

export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();

  const { data: bankConnections, isLoading: isLoadingBanks } = useBankConnections();
  const connectBankMutation = useConnectBank();
  const deleteBankConnectionMutation = useDeleteBankConnection();
  const startSyncMutation = useStartSync();
  const queryClient = useQueryClient();
  const [isPollingSync, setIsPollingSync] = React.useState(false);

  const { data: syncStatus } = useSyncStatus(isPollingSync);

  React.useEffect(() => {
    if (isPollingSync && syncStatus) {
      if (
        syncStatus.status === 'succeeded' ||
        syncStatus.status === 'completed_with_errors' ||
        syncStatus.status === 'failed'
      ) {
        setIsPollingSync(false);

        if (syncStatus.status === 'succeeded' || syncStatus.status === 'completed_with_errors') {
          queryClient.invalidateQueries({ queryKey: ['transactions'] });
          queryClient.invalidateQueries({ queryKey: ['accounts'] });
          queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
          queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });

          if (syncStatus.error || syncStatus.status === 'completed_with_errors') {
            toast.warning(syncStatus.error || 'Synkronisering fuldført med fejl på nogle konti');
          } else {
            toast.success('Synkronisering fuldført!');
          }
        } else {
          toast.error(syncStatus.error || 'Synkronisering fejlede');
        }
      }
    }
  }, [syncStatus, isPollingSync, queryClient]);

  const uploadSpiirExportMutation = useUploadSpiirExport();

  const { data: userRules = [], isLoading: isLoadingRules } = useRules('user');
  const deleteRuleMutation = useDeleteRule();

  const { activeHouseholdId, households, deletedHouseholds, setActiveHousehold } = useHousehold();
  const currentHousehold = households.find((h: any) => h.id === activeHouseholdId);
  const { data: members = [] } = useHouseholdMembers(activeHouseholdId || '');
  const inviteMemberMutation = useInviteHouseholdMember();
  const removeMemberMutation = useRemoveHouseholdMember();
  const updateRoleMutation = useUpdateHouseholdMemberRole();
  const deleteHouseholdMutation = useDeleteHousehold();
  const restoreHouseholdMutation = useRestoreHousehold();
  const createHouseholdMutation = useCreateHousehold();
  const updateHouseholdMutation = useUpdateHousehold();

  const [activeTab, setActiveTab] = React.useState<'general' | 'households' | 'rules'>('general');
  const [inviteEmail, setInviteEmail] = React.useState('');
  const [inviteRole, setInviteRole] = React.useState('member');
  const [newHouseholdName, setNewHouseholdName] = React.useState('');
  const [renameHouseholdName, setRenameHouseholdName] = React.useState('');
  const [selectedBank, setSelectedBank] = React.useState('Sparekassen Danmark');

  React.useEffect(() => {
    if (currentHousehold?.name) {
      setRenameHouseholdName(currentHousehold.name);
    }
  }, [currentHousehold?.name]);
  const [importResult, setImportResult] = React.useState<any>(null);
  const [storeboxImportResult, setStoreboxImportResult] = React.useState<any>(null);
  const [coopImportResult, setCoopImportResult] = React.useState<any>(null);

  const uploadStoreboxMutation = useUploadStoreboxFile();
  const uploadCoopMutation = useUploadCoopFile();
  const importStoreboxLinkMutation = useImportStoreboxLink();
  const [storeboxLink, setStoreboxLink] = React.useState('');
  const [copiedBookmarklet, setCopiedBookmarklet] = React.useState(false);

  // Inbound Email hooks & state
  const { data: inboundConfig, isLoading: isLoadingInboundConfig } = useInboundConfig(
    currentHousehold?.id
  );
  const { data: inboundEmails, isLoading: isLoadingInboundEmails } = useInboundEmails(
    currentHousehold?.id
  );
  const simulateInboundMutation = useSimulateInboundEmail();
  const retryInboundMutation = useRetryInboundEmail();
  const regenerateInboundTokenMutation = useRegenerateInboundToken();
  const deleteInboundEmailMutation = useDeleteInboundEmail();
  const clearInboundEmailsMutation = useClearInboundEmails();

  const [copiedEmail, setCopiedEmail] = React.useState(false);
  const [showSimulateBox, setShowSimulateBox] = React.useState(false);
  const [simulateContent, setSimulateContent] = React.useState('');

  const coopBookmarkletHref = React.useMemo(() => {
    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    const token = inboundConfig?.inbound_token || currentHousehold?.inbound_email_token || '';
    return buildCoopBookmarkletHref(origin, token);
  }, [inboundConfig?.inbound_token, currentHousehold?.inbound_email_token]);
  const [retryingEmailId, setRetryingEmailId] = React.useState<string | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    uploadSpiirExportMutation.mutate(file, {
      onSuccess: (data) => {
        setImportResult(data);
      },
    });
  };

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    localStorage.setItem('peng-lang', lang);
  };

  const handleConnectBank = () => {
    connectBankMutation.mutate(
      { redirectUrl: window.location.origin + '/dashboard', bankName: selectedBank },
      {
        onSuccess: (data) => {
          if (data.auth_url) {
            window.location.href = data.auth_url;
          }
        },
      }
    );
  };

  const handleSync = () => {
    startSyncMutation.mutate(undefined, {
      onSuccess: () => {
        setIsPollingSync(true);
        toast.info('Synkronisering startet...');
      },
      onError: (error) => {
        toast.error('Kunne ikke starte synkronisering: ' + error.message);
      },
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-4 md:p-8 max-w-4xl mx-auto space-y-6 pb-28 md:pb-8"
    >
      <div className="mb-8">
        <motion.h1
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="text-3xl font-bold text-[hsl(var(--text-primary))]"
        >
          {t('app.settings')}
        </motion.h1>
        <motion.p
          initial={{ y: -5, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="text-muted mt-2"
        >
          {t('settings.description')}
        </motion.p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sun size={20} className="text-[hsl(var(--brand-primary))]" />
                {t('settings.appearance')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <button
                  onClick={() => setTheme('light')}
                  className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-lg border ${theme === 'light' ? 'border-[hsl(var(--brand-primary))] bg-[hsla(var(--brand-primary),0.05)] text-[hsl(var(--brand-primary))]' : 'border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))] text-muted'}`}
                >
                  <Sun size={24} />
                  <span className="text-sm font-medium">{t('settings.light')}</span>
                </button>
                <button
                  onClick={() => setTheme('dark')}
                  className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-lg border ${theme === 'dark' ? 'border-[hsl(var(--brand-primary))] bg-[hsla(var(--brand-primary),0.05)] text-[hsl(var(--brand-primary))]' : 'border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))] text-muted'}`}
                >
                  <Moon size={24} />
                  <span className="text-sm font-medium">{t('settings.dark')}</span>
                </button>
                <button
                  onClick={() => setTheme('system')}
                  className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-lg border ${theme === 'system' ? 'border-[hsl(var(--brand-primary))] bg-[hsla(var(--brand-primary),0.05)] text-[hsl(var(--brand-primary))]' : 'border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))] text-muted'}`}
                >
                  <Monitor size={24} />
                  <span className="text-sm font-medium">{t('settings.system')}</span>
                </button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Languages size={20} className="text-[hsl(var(--brand-primary))]" />
                {t('settings.language')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <button
                  onClick={() => handleLanguageChange('da')}
                  className={`flex-1 p-3 rounded-lg border text-sm font-medium transition-colors ${i18n.language === 'da' ? 'border-[hsl(var(--brand-primary))] bg-[hsla(var(--brand-primary),0.05)] text-[hsl(var(--brand-primary))]' : 'border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))] text-muted'}`}
                >
                  {t('settings.danish')}
                </button>
                <button
                  onClick={() => handleLanguageChange('en')}
                  className={`flex-1 p-3 rounded-lg border text-sm font-medium transition-colors ${i18n.language === 'en' ? 'border-[hsl(var(--brand-primary))] bg-[hsla(var(--brand-primary),0.05)] text-[hsl(var(--brand-primary))]' : 'border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))] text-muted'}`}
                >
                  {t('settings.english')}
                </button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.22 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText size={20} className="text-[hsl(var(--brand-primary))]" />
                {t('settings.releaseNotes')}
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[calc(100%-4rem)] flex items-center justify-center">
              <Link to="/settings/release-notes" className="w-full">
                <Button className="w-full flex items-center justify-center gap-2" variant="outline">
                  <FileText size={18} />
                  {t('settings.releaseNotes')}
                </Button>
              </Link>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users size={20} className="text-[hsl(var(--brand-primary))]" />
              {t('settings.household')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {activeHouseholdId && (
              <div>
                <h3 className="text-sm font-medium mb-3">{t('settings.renameHousehold')}</h3>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder={t('settings.householdNamePlaceholder')}
                    className="flex-1 px-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-transparent"
                    value={renameHouseholdName}
                    onChange={(e) => setRenameHouseholdName(e.target.value)}
                  />
                  <Button
                    onClick={() => {
                      if (activeHouseholdId && renameHouseholdName.trim()) {
                        updateHouseholdMutation.mutate(
                          { householdId: activeHouseholdId, name: renameHouseholdName.trim() },
                          {
                            onSuccess: () => {
                              toast.success(t('settings.householdUpdated'));
                            },
                            onError: (err: any) => {
                              toast.error(err?.message || t('settings.failedToUpdate'));
                            },
                          }
                        );
                      }
                    }}
                    disabled={
                      !renameHouseholdName.trim() ||
                      updateHouseholdMutation.isPending ||
                      renameHouseholdName.trim() === currentHousehold?.name
                    }
                    className="flex items-center gap-2"
                  >
                    {t('settings.saveName')}
                  </Button>
                </div>
              </div>
            )}

            <div className="pt-4 border-t border-[hsl(var(--border-color))]">
              <h3 className="text-sm font-medium mb-3">{t('settings.members')}</h3>
              <div className="space-y-2">
                {members.map((member: any, i: number) => {
                  const isMe = member.is_me;
                  const youLabel = t('common.you');
                  let mainText = member.name || member.email;
                  if (isMe) {
                    mainText = mainText ? `${mainText} (${youLabel})` : youLabel;
                  } else if (!mainText) {
                    mainText = t('settings.member', 'Medlem');
                  }

                  return (
                    <div
                      key={i}
                      className="flex items-center justify-between p-3 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-tertiary))]"
                    >
                      <div>
                        <p className="font-semibold text-sm text-[hsl(var(--text-primary))]">
                          {mainText}
                        </p>
                        {member.email && member.email !== mainText && (
                          <p className="text-xs text-muted">{member.email}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {currentHousehold?.role === 'owner' && !isMe && member.id ? (
                          <select
                            value={member.role}
                            onChange={(e) => {
                              const newRole = e.target.value;
                              if (member.role === 'owner' && newRole === 'member') {
                                if (
                                  !window.confirm(
                                    t(
                                      'settings.demoteOwnerConfirm',
                                      'Er du sikker på, at du vil ændre denne ejers rolle til medlem? De vil miste muligheden for at administrere husstanden.'
                                    )
                                  )
                                ) {
                                  return;
                                }
                              }
                              updateRoleMutation.mutate(
                                {
                                  householdId: activeHouseholdId!,
                                  userId: member.id!,
                                  role: newRole,
                                },
                                {
                                  onSuccess: () =>
                                    toast.success(t('settings.roleUpdated', 'Rolle opdateret!')),
                                  onError: (err: any) =>
                                    toast.error(
                                      err?.message ||
                                        t(
                                          'settings.failedToUpdateRole',
                                          'Kunne ikke opdatere rolle'
                                        )
                                    ),
                                }
                              );
                            }}
                            disabled={updateRoleMutation.isPending}
                            className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--brand-primary))] px-2.5 py-1 rounded-md bg-[hsla(var(--brand-primary),0.08)] border border-[hsla(var(--brand-primary),0.2)] hover:border-[hsla(var(--brand-primary),0.4)] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--brand-primary))] cursor-pointer transition-colors"
                          >
                            <option
                              value="owner"
                              className="bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))]"
                            >
                              {t('settings.roleOwner', 'Ejer')}
                            </option>
                            <option
                              value="member"
                              className="bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))]"
                            >
                              {t('settings.roleMember', 'Medlem')}
                            </option>
                          </select>
                        ) : (
                          <span className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--brand-primary))] px-2 py-1 rounded bg-[hsla(var(--brand-primary),0.1)]">
                            {member.role === 'owner'
                              ? t('settings.roleOwner', 'Ejer')
                              : t('settings.roleMember', 'Medlem')}
                          </span>
                        )}
                        {currentHousehold?.role === 'owner' && !isMe && member.id && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="bg-red-500/10 text-red-500 hover:bg-red-500/20 hover:text-red-400"
                            onClick={() => {
                              if (
                                window.confirm(
                                  t(
                                    'settings.removeMemberConfirm',
                                    'Er du sikker på, at du vil fjerne dette medlem?'
                                  )
                                )
                              ) {
                                removeMemberMutation.mutate(
                                  { householdId: activeHouseholdId!, userId: member.id },
                                  {
                                    onSuccess: () =>
                                      toast.success(t('settings.memberRemoved', 'Medlem fjernet!')),
                                    onError: (err: any) => toast.error(err?.message || 'Error'),
                                  }
                                );
                              }
                            }}
                            disabled={removeMemberMutation.isPending}
                          >
                            <Trash2 size={16} />
                          </Button>
                        )}
                        {currentHousehold?.role !== 'owner' && isMe && member.id && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-red-500 border-red-500/20 hover:bg-red-500/10 text-xs px-2.5 py-1 h-auto"
                            onClick={() => {
                              if (
                                window.confirm(
                                  t(
                                    'settings.leaveHouseholdConfirm',
                                    'Er du sikker på, at du vil forlade denne husstand?'
                                  )
                                )
                              ) {
                                removeMemberMutation.mutate(
                                  { householdId: activeHouseholdId!, userId: member.id },
                                  {
                                    onSuccess: () =>
                                      toast.success(
                                        t('settings.leftHousehold', 'Du har forladt husstanden')
                                      ),
                                    onError: (err: any) => toast.error(err?.message || 'Error'),
                                  }
                                );
                              }
                            }}
                            disabled={removeMemberMutation.isPending}
                          >
                            {t('settings.leaveHousehold', 'Forlad husstand')}
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="pt-4 border-t border-[hsl(var(--border-color))]">
              <h3 className="text-sm font-medium mb-3">{t('settings.inviteToHousehold')}</h3>
              <div className="flex gap-2">
                <input
                  type="email"
                  placeholder={t('settings.invitePlaceholder')}
                  className="flex-1 px-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-transparent"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                />
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="px-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-transparent text-sm cursor-pointer"
                >
                  <option value="member">{t('settings.roleMember', 'Medlem')}</option>
                  <option value="owner">{t('settings.roleOwner', 'Ejer')}</option>
                </select>
                <Button
                  onClick={() => {
                    if (activeHouseholdId && inviteEmail) {
                      inviteMemberMutation.mutate(
                        { householdId: activeHouseholdId, email: inviteEmail, role: inviteRole },
                        {
                          onSuccess: () => {
                            setInviteEmail('');
                            setInviteRole('member');
                            toast.success(t('settings.householdInvited'));
                          },
                          onError: (err: any) => {
                            toast.error(err?.message || t('settings.failedToInvite'));
                          },
                        }
                      );
                    }
                  }}
                  disabled={!inviteEmail || inviteMemberMutation.isPending}
                  className="flex items-center gap-2"
                >
                  <Mail size={16} />
                  {t('settings.inviteButton')}
                </Button>
              </div>
              {inviteMemberMutation.isError && (
                <p className="text-red-500 text-xs mt-2">{inviteMemberMutation.error?.message}</p>
              )}
            </div>

            <div className="pt-4 border-t border-[hsl(var(--border-color))]">
              <h3 className="text-sm font-medium mb-3">{t('settings.createHousehold')}</h3>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder={t('settings.householdNamePlaceholder')}
                  className="flex-1 px-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-transparent"
                  value={newHouseholdName}
                  onChange={(e) => setNewHouseholdName(e.target.value)}
                />
                <Button
                  onClick={() => {
                    if (newHouseholdName) {
                      createHouseholdMutation.mutate(newHouseholdName, {
                        onSuccess: (data: any) => {
                          setNewHouseholdName('');
                          if (data?.id) {
                            setActiveHousehold(data.id);
                          }
                          toast.success(t('settings.householdCreated'));
                        },
                        onError: (err: any) => {
                          toast.error(err?.message || t('settings.failedToCreate'));
                        },
                      });
                    }
                  }}
                  disabled={!newHouseholdName || createHouseholdMutation.isPending}
                  className="flex items-center gap-2"
                >
                  <Plus size={16} />
                  {t('settings.createButton')}
                </Button>
              </div>
            </div>

            {households.length > 1 && (
              <div className="pt-4 border-t border-[hsl(var(--border-color))]">
                <h3 className="text-sm font-medium mb-3">
                  {t('settings.switchHousehold', 'Skift aktiv husstand')}
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {households.map((hh: any) => (
                    <button
                      key={hh.id}
                      onClick={() => setActiveHousehold(hh.id)}
                      className={`flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                        activeHouseholdId === hh.id
                          ? 'border-[hsl(var(--brand-primary))] bg-[hsla(var(--brand-primary),0.08)] text-[hsl(var(--brand-primary))] font-semibold'
                          : 'border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-primary))]'
                      }`}
                    >
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                          activeHouseholdId === hh.id
                            ? 'bg-[hsl(var(--brand-primary))] text-white'
                            : 'bg-[hsl(var(--bg-tertiary))]'
                        }`}
                      >
                        <Users size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{hh.name}</p>
                        <p className="text-xs text-muted capitalize">
                          {hh.role === 'owner'
                            ? t('settings.roleOwner', 'Ejer')
                            : t('settings.roleMember', 'Medlem')}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {activeHouseholdId && currentHousehold?.role === 'owner' && (
              <div className="pt-4 border-t border-[hsl(var(--border-color))]">
                <Button
                  variant="outline"
                  className="w-full text-red-500 border-red-500/20 hover:bg-red-500/10 flex items-center justify-center gap-2"
                  onClick={() => {
                    if (
                      window.confirm(
                        t('settings.deleteHouseholdConfirm', {
                          name: currentHousehold?.name || '',
                          defaultValue: `Er du sikker på, at du vil slette husstanden '${currentHousehold?.name || ''}'? Al data vil gå tabt efter 2 timer.`,
                        })
                      )
                    ) {
                      deleteHouseholdMutation.mutate(activeHouseholdId, {
                        onSuccess: () =>
                          toast.success(
                            t('settings.householdDeleted', 'Husstanden er markeret til sletning')
                          ),
                        onError: (err: any) => toast.error(err?.message || 'Error'),
                      });
                    }
                  }}
                  disabled={deleteHouseholdMutation.isPending}
                >
                  <Trash2 size={16} />
                  {t('settings.deleteHousehold', 'Slet husstand')}
                </Button>
              </div>
            )}

            {deletedHouseholds && deletedHouseholds.length > 0 && (
              <div className="pt-4 border-t border-[hsl(var(--border-color))]">
                <h3 className="text-sm font-medium mb-3 text-red-500">
                  {t('settings.deletedHouseholds', 'Nyligt slettede husstande (Kan fortrydes)')}
                </h3>
                <div className="space-y-2">
                  {deletedHouseholds.map((hh: any) => (
                    <div
                      key={hh.id}
                      className="flex items-center justify-between p-3 rounded-lg border border-red-500/20 bg-red-500/5"
                    >
                      <div>
                        <p className="text-sm font-semibold">{hh.name}</p>
                        <p className="text-xs text-muted">
                          {t('settings.deletedAt', {
                            time: new Date(
                              new Date(hh.deleted_at).getTime() + 2 * 60 * 60 * 1000
                            ).toLocaleString(),
                            defaultValue:
                              'Slettes permanent: ' +
                              new Date(
                                new Date(hh.deleted_at).getTime() + 2 * 60 * 60 * 1000
                              ).toLocaleString(),
                          })}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          restoreHouseholdMutation.mutate(hh.id, {
                            onSuccess: () =>
                              toast.success(
                                t('settings.householdRestored', 'Sletning af husstand fortrudt!')
                              ),
                            onError: (err: any) => toast.error(err?.message || 'Error'),
                          });
                        }}
                        disabled={restoreHouseholdMutation.isPending}
                        className="text-green-600 border-green-600/20 hover:bg-green-600/10"
                      >
                        <RefreshCw size={14} className="mr-2" />
                        {t('settings.restoreHousehold', 'Fortryd sletning')}
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListFilter size={20} className="text-[hsl(var(--brand-primary))]" />
              {t('settings.categorizationRules', 'Dine Kategoriseringsregler')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingRules ? (
              <p className="text-sm text-muted">{t('settings.loadingRules', 'Henter regler...')}</p>
            ) : userRules.length === 0 ? (
              <p className="text-sm text-muted">
                {t('settings.noRulesYet', 'Du har ikke oprettet nogen personlige regler endnu.')}
              </p>
            ) : (
              <div className="space-y-3">
                {userRules.map((rule: any) => {
                  const catParts = (rule.category_id || '').split('|');
                  const catName = catParts[1] ? catParts[1] : catParts[0];
                  return (
                    <div
                      key={rule.id}
                      className="flex items-center justify-between p-3 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-tertiary))]"
                    >
                      <div>
                        <p className="font-medium">"{rule.match_pattern}"</p>
                        <p className="text-xs text-muted capitalize mt-0.5">
                          → {catName.replace('-', ' ')}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-error hover:bg-[hsla(var(--error),0.1)]"
                        onClick={() => {
                          if (
                            confirm(
                              t(
                                'settings.confirmDeleteRule',
                                'Er du sikker på du vil slette denne regel? (Allerede ændrede transaktioner ændres ikke tilbage)'
                              )
                            )
                          ) {
                            deleteRuleMutation.mutate(rule.id);
                          }
                        }}
                        disabled={deleteRuleMutation.isPending}
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card>
          <CardHeader>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Building2 size={20} className="text-[hsl(var(--brand-primary))]" />
                  {t('settings.bankConnections', 'Bankforbindelser')}
                </CardTitle>
                <p className="text-sm text-muted">
                  {t(
                    'settings.connectBankDescription',
                    'Forbind dine bankkonti for automatisk import af transaktioner'
                  )}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleSync}
                  disabled={startSyncMutation.isPending || isPollingSync}
                  className="flex items-center gap-2 px-3 py-2 text-sm font-medium border border-[hsl(var(--border-color))] rounded-lg hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
                >
                  <RefreshCw
                    size={16}
                    className={startSyncMutation.isPending || isPollingSync ? 'animate-spin' : ''}
                  />
                  {isPollingSync
                    ? t('settings.syncing', 'Synkroniserer...')
                    : t('settings.sync', 'Synkroniser')}
                </button>
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-2">
                    <select
                      className="px-3 py-2 h-[38px] text-sm rounded-lg border border-[hsl(var(--border-color))] bg-transparent"
                      value={selectedBank}
                      onChange={(e) => setSelectedBank(e.target.value)}
                    >
                      {SUPPORTED_BANKS.map((bank) => (
                        <option
                          key={bank}
                          value={bank}
                          className="bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))]"
                        >
                          {bank}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={handleConnectBank}
                      disabled={connectBankMutation.isPending}
                      className="btn btn-primary disabled:opacity-50"
                    >
                      <Plus size={16} />
                      {t('settings.connectBank', 'Forbind til bank')}
                    </button>
                  </div>
                  {connectBankMutation.isError && (
                    <span className="text-xs text-red-500">
                      {t('common.error', 'Fejl')}: {connectBankMutation.error?.message}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingBanks ? (
              <div className="py-8 text-center text-muted animate-pulse">
                {t('settings.loadingConnections', 'Henter forbindelser...')}
              </div>
            ) : bankConnections?.length === 0 ? (
              <div className="py-8 text-center text-muted border-2 border-dashed border-[hsl(var(--border-color))] rounded-lg">
                {t('settings.noActiveConnections', 'Ingen aktive bankforbindelser endnu.')}
              </div>
            ) : (
              <div className="space-y-4">
                {bankConnections?.map((conn: any) => (
                  <div
                    key={conn.id}
                    className="flex items-center justify-between p-4 border border-[hsl(var(--border-color))] rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-[hsl(var(--bg-tertiary))] rounded-full">
                        <Building2 size={20} className="text-[hsl(var(--text-secondary))]" />
                      </div>
                      <div>
                        <div className="font-medium text-[hsl(var(--text-primary))]">
                          {conn.bank_name}
                        </div>
                        <div className="text-xs text-muted">
                          Forbundet: {new Date(conn.created_at).toLocaleDateString()} &middot;
                          Status: {conn.status}
                        </div>
                      </div>
                    </div>
                    <button
                      className="p-2 text-[hsl(var(--text-secondary))] hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                      disabled={deleteBankConnectionMutation.isPending}
                      title={t('settings.deleteBankConnection', 'Fjern bankforbindelse')}
                      onClick={() => {
                        if (
                          window.confirm(
                            t(
                              'settings.deleteBankConnectionConfirm',
                              'Er du sikker på, at du vil fjerne denne bankforbindelse?'
                            )
                          )
                        ) {
                          deleteBankConnectionMutation.mutate(conn.id, {
                            onSuccess: () =>
                              toast.success(
                                t('settings.bankConnectionDeleted', 'Bankforbindelse fjernet')
                              ),
                            onError: (err: any) =>
                              toast.error(err?.message || t('common.error', 'Der skete en fejl')),
                          });
                        }
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Spiir Import Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="text-[hsl(var(--brand-primary))]" size={24} />
              Importér Spiir-data
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted leading-relaxed">
              Upload dit historiske CSV-udtræk fra Spiir. Vi fletter dine gamle transaktioner sammen
              med de nye og bevarer dine eksisterende kategoriseringer uden at skabe dubletter.
            </p>

            {importResult ? (
              <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-lg flex items-start gap-3">
                <CheckCircle className="text-green-500 shrink-0 mt-0.5" size={20} />
                <div>
                  <h4 className="font-semibold text-green-700 dark:text-green-400">
                    Import fuldført!
                  </h4>
                  <ul className="text-sm text-green-600 dark:text-green-300 mt-1 space-y-1">
                    <li>Læste {importResult.total_rows} transaktioner</li>
                    <li>Importerede {importResult.imported_new} nye transaktioner</li>
                    <li>Opdaterede/flettede {importResult.merged_existing} transaktioner</li>
                    <li>Sprang {importResult.skipped} over</li>
                    {importResult.accounts_created > 0 && (
                      <li>Oprettede {importResult.accounts_created} historiske konti</li>
                    )}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="relative">
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileUpload}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                  disabled={uploadSpiirExportMutation.isPending}
                />
                <button
                  className={`w-full py-3 px-4 border-2 border-dashed border-[hsl(var(--border-color))] rounded-xl font-medium flex items-center justify-center gap-2 transition-colors ${uploadSpiirExportMutation.isPending ? 'opacity-50 cursor-not-allowed' : 'hover:border-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary))]/5'}`}
                >
                  {uploadSpiirExportMutation.isPending ? (
                    <>
                      <RefreshCw className="animate-spin" size={18} />
                      Importerer data...
                    </>
                  ) : (
                    <>
                      <Upload size={18} />
                      Vælg Spiir CSV-fil
                    </>
                  )}
                </button>
              </div>
            )}
          </CardContent>
        </Card>
        {/* Receipts Overall Status & Sync Overview */}
        <ReceiptsOverviewCard />

        {/* Storebox & Receipt Email Ingestion Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShoppingBag className="text-[hsl(var(--brand-primary))]" size={24} />
              {t('settings.storebox.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-sm text-muted leading-relaxed">
              {t('settings.storebox.description')}
            </p>

            {storeboxImportResult && (
              <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-xl flex items-start gap-3">
                <CheckCircle className="text-green-500 shrink-0 mt-0.5" size={20} />
                <div className="flex-1">
                  <h4 className="font-semibold text-green-700 dark:text-green-400">
                    {t('settings.storebox.importSuccess')}
                  </h4>
                  <ul className="text-sm text-green-600 dark:text-green-300 mt-1 space-y-1">
                    <li>
                      {t('settings.storebox.rawReceiptsCount', {
                        count: storeboxImportResult.raw_receipt_count,
                      })}
                    </li>
                    <li>
                      {t('settings.storebox.deduplicatedCount', {
                        count: storeboxImportResult.deduplicated_receipt_count,
                      })}
                    </li>
                    <li>
                      {t('settings.storebox.duplicatesSkipped', {
                        count: storeboxImportResult.duplicate_receipt_count,
                      })}
                    </li>
                    <li>
                      {t('settings.storebox.itemClustersCount', {
                        count: storeboxImportResult.item_cluster_count,
                      })}
                    </li>
                    <li>
                      {t('settings.storebox.merchantsCount', {
                        count: storeboxImportResult.merchant_count,
                      })}
                    </li>
                    {storeboxImportResult.auto_linked > 0 && (
                      <li className="font-medium">
                        {t('settings.storebox.autoLinkedSuccess', {
                          count: storeboxImportResult.auto_linked,
                        })}
                      </li>
                    )}
                  </ul>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 border-green-500/20 text-green-700 dark:text-green-400 hover:bg-green-500/10"
                    onClick={() => setStoreboxImportResult(null)}
                  >
                    {t('settings.storebox.importMore')}
                  </Button>
                </div>
              </div>
            )}

            {/* Option 1: Automatic Email Forwarding */}
            <div className="p-4 rounded-xl border border-[hsl(var(--brand-primary))]/20 bg-[hsl(var(--brand-primary))]/5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Mail className="text-[hsl(var(--brand-primary))]" size={18} />
                  <h4 className="font-medium text-sm text-[hsl(var(--text-color))]">
                    {t('settings.storebox.forwardEmail')}
                  </h4>
                </div>
                {inboundConfig?.imap_enabled && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-medium">
                    IMAP Poller Aktiv
                  </span>
                )}
              </div>

              <p className="text-xs text-muted leading-relaxed">
                {t('settings.storebox.forwardEmailDesc')}
              </p>

              {/* Email Address Display & Copy */}
              <div className="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
                <div className="flex-1 bg-[hsl(var(--card-bg))] border border-[hsl(var(--border-color))] px-3 py-2 rounded-lg font-mono text-sm select-all flex items-center justify-between">
                  <span className="truncate">
                    {inboundConfig?.email_address || 'Indlæser adresse...'}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (inboundConfig?.email_address) {
                      navigator.clipboard.writeText(inboundConfig.email_address);
                      setCopiedEmail(true);
                      toast.success(t('settings.storebox.addressCopied'));
                      setTimeout(() => setCopiedEmail(false), 2500);
                    }
                  }}
                  disabled={!inboundConfig?.email_address}
                  className="flex items-center gap-2"
                >
                  {copiedEmail ? (
                    <Check size={16} className="text-green-500" />
                  ) : (
                    <Copy size={16} />
                  )}
                  {copiedEmail
                    ? t('settings.storebox.addressCopied')
                    : t('settings.storebox.copyAddress')}
                </Button>
                {currentHousehold?.role === 'owner' && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      if (
                        currentHousehold?.id &&
                        confirm(t('settings.storebox.regenerateTokenConfirm'))
                      ) {
                        regenerateInboundTokenMutation.mutate(currentHousehold.id, {
                          onSuccess: () => toast.success('Ny e-mailadresse genereret'),
                          onError: (err: any) => toast.error('Fejl: ' + err.message),
                        });
                      }
                    }}
                    disabled={regenerateInboundTokenMutation.isPending}
                    className="text-xs text-muted hover:text-[hsl(var(--text-color))]"
                  >
                    <RotateCcw
                      size={14}
                      className={regenerateInboundTokenMutation.isPending ? 'animate-spin' : ''}
                    />
                  </Button>
                )}
              </div>

              {/* Test / Simulation Accordion */}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowSimulateBox(!showSimulateBox)}
                  className="text-xs font-medium text-[hsl(var(--brand-primary))] hover:underline flex items-center gap-1"
                >
                  <Sparkles size={14} />
                  {showSimulateBox ? 'Skjul test-panel' : t('settings.storebox.simulateTitle')}
                </button>

                {showSimulateBox && (
                  <div className="mt-3 p-3 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--card-bg))] space-y-3">
                    <p className="text-xs text-muted">{t('settings.storebox.simulateDesc')}</p>
                    <textarea
                      rows={3}
                      value={simulateContent}
                      onChange={(e) => setSimulateContent(e.target.value)}
                      placeholder={t('settings.storebox.pasteContentPlaceholder')}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-[hsl(var(--border-color))] bg-transparent resize-y font-mono"
                    />
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        onClick={() => {
                          if (currentHousehold?.id && simulateContent.trim()) {
                            simulateInboundMutation.mutate(
                              {
                                householdId: currentHousehold.id,
                                payload: { raw_content: simulateContent.trim() },
                              },
                              {
                                onSuccess: (data) => {
                                  if (data.success) {
                                    toast.success('Test gennemført! Kvitteringer blev importeret.');
                                    setStoreboxImportResult(data);
                                    setSimulateContent('');
                                    setShowSimulateBox(false);
                                  } else {
                                    toast.error('Test fejlede: ' + (data.error || 'Ukendt fejl'));
                                  }
                                },
                                onError: (err: any) => {
                                  toast.error('Fejl under test: ' + err.message);
                                },
                              }
                            );
                          }
                        }}
                        disabled={!simulateContent.trim() || simulateInboundMutation.isPending}
                        className="flex items-center gap-2 text-xs"
                      >
                        {simulateInboundMutation.isPending ? (
                          <RefreshCw className="animate-spin" size={14} />
                        ) : (
                          <Send size={14} />
                        )}
                        {simulateInboundMutation.isPending
                          ? t('settings.storebox.simulating')
                          : t('settings.storebox.simulateButton')}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Inbound Email History */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold flex items-center gap-2">
                  <Inbox size={16} className="text-[hsl(var(--brand-primary))]" />
                  {t('settings.storebox.inboundHistory')}
                </h4>
                {inboundEmails && inboundEmails.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted">{inboundEmails.length} modtaget</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        if (
                          currentHousehold?.id &&
                          confirm(t('settings.storebox.clearHistoryConfirm'))
                        ) {
                          clearInboundEmailsMutation.mutate(currentHousehold.id, {
                            onSuccess: () => toast.success(t('settings.storebox.clearHistory')),
                            onError: (err: any) => toast.error(err.message),
                          });
                        }
                      }}
                      disabled={clearInboundEmailsMutation.isPending}
                      className="text-xs text-muted hover:text-red-500 h-6 px-2 py-0"
                    >
                      <Trash2 size={12} className="mr-1" />
                      {t('settings.storebox.clearHistory')}
                    </Button>
                  </div>
                )}
              </div>

              {isLoadingInboundEmails ? (
                <div className="p-4 text-center text-xs text-muted">
                  <RefreshCw className="animate-spin mx-auto mb-2" size={16} />
                  Indlæser historik...
                </div>
              ) : !inboundEmails || inboundEmails.length === 0 ? (
                <div className="p-4 text-center text-xs text-muted border border-dashed border-[hsl(var(--border-color))] rounded-xl">
                  {t('settings.storebox.noEmailsYet')}
                </div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {inboundEmails.map((log) => {
                    const isSuccess = log.status === 'success';
                    const isFailed = log.status === 'failed';
                    const isNoLink = log.status === 'no_link';
                    const isInfo = log.status === 'info';

                    let statusBadgeClass =
                      'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20';
                    let statusLabel = t('settings.storebox.statusPending');

                    if (isSuccess) {
                      statusBadgeClass =
                        'bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20';
                      statusLabel = t('settings.storebox.statusSuccess');
                    } else if (isFailed) {
                      statusBadgeClass =
                        'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20';
                      statusLabel = t('settings.storebox.statusFailed');
                    } else if (isInfo) {
                      statusBadgeClass =
                        'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20';
                      statusLabel = t('settings.storebox.statusInfo');
                    } else if (isNoLink) {
                      statusBadgeClass =
                        'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
                      statusLabel = t('settings.storebox.statusNoLink');
                    }

                    const formattedDate = new Date(log.received_at).toLocaleString(
                      i18n.language === 'da' ? 'da-DK' : 'en-US',
                      { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }
                    );

                    // Extract link if any in error_message
                    const urlMatch = log.error_message
                      ? log.error_message.match(/(https?:\/\/[^\s<>]+)/)
                      : null;
                    const extractedUrl = urlMatch
                      ? urlMatch[1].replace(/[.,;:!?)\]'"]+$/, '')
                      : null;
                    const textBeforeUrl =
                      log.error_message && extractedUrl
                        ? log.error_message
                            .replace(urlMatch![0], '')
                            .replace(/\bLinks?:\s*$/i, '')
                            .trim()
                        : log.error_message;

                    const isConfirmationEmail =
                      isInfo ||
                      Boolean(
                        log.subject?.toLowerCase().includes('confirm') ||
                        log.sender?.toLowerCase().includes('proton') ||
                        extractedUrl?.includes('forwarding') ||
                        extractedUrl?.includes('verify')
                      );

                    return (
                      <div
                        key={log.id}
                        className="p-3 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--card-bg))] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                      >
                        <div className="space-y-1 min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium truncate">
                              {log.subject || '(Intet emne)'}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold ${statusBadgeClass}`}
                            >
                              {statusLabel}
                            </span>
                          </div>
                          <div className="text-muted text-[11px] flex items-center gap-2 truncate">
                            <span>{log.sender}</span>
                            <span>•</span>
                            <span>{formattedDate}</span>
                          </div>

                          {/* Clean Link / Message Display */}
                          {extractedUrl ? (
                            <div className="pt-1 flex flex-wrap items-center gap-2">
                              {textBeforeUrl && (
                                <span
                                  className={
                                    isFailed
                                      ? 'text-red-500 dark:text-red-400 text-[11px]'
                                      : 'text-muted dark:text-zinc-400 text-[11px]'
                                  }
                                >
                                  {textBeforeUrl}
                                </span>
                              )}
                              <a
                                href={extractedUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-[hsl(var(--brand-primary))/10] text-[hsl(var(--brand-primary))] border border-[hsl(var(--brand-primary))/20] font-medium hover:bg-[hsl(var(--brand-primary))/20] transition-colors text-[11px]"
                              >
                                <ExternalLink size={11} />
                                {isConfirmationEmail
                                  ? t('settings.storebox.openConfirmationLink')
                                  : extractedUrl.length > 35
                                    ? extractedUrl.slice(0, 30) + '...'
                                    : extractedUrl}
                              </a>
                            </div>
                          ) : log.error_message ? (
                            <p
                              className={`text-[11px] mt-0.5 ${isFailed ? 'text-red-500 dark:text-red-400' : 'text-muted dark:text-zinc-400'}`}
                            >
                              {log.error_message}
                            </p>
                          ) : null}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {isSuccess && (
                            <span className="text-muted text-[11px]">
                              {t('settings.storebox.receiptsImported', {
                                count: log.deduplicated_receipt_count,
                              })}
                              {log.auto_linked_count > 0 &&
                                ` (${t('settings.storebox.autoLinkedCount', { count: log.auto_linked_count })})`}
                            </span>
                          )}

                          {isFailed && log.download_url && currentHousehold?.id && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setRetryingEmailId(log.id);
                                retryInboundMutation.mutate(
                                  { householdId: currentHousehold.id, emailId: log.id },
                                  {
                                    onSuccess: (data) => {
                                      if (data.success) {
                                        toast.success(t('settings.storebox.retrySuccess'));
                                      } else {
                                        toast.error(
                                          t('settings.storebox.retryFailed') + (data.error || '')
                                        );
                                      }
                                      setRetryingEmailId(null);
                                    },
                                    onError: (err: any) => {
                                      toast.error(t('settings.storebox.retryFailed') + err.message);
                                      setRetryingEmailId(null);
                                    },
                                  }
                                );
                              }}
                              disabled={retryingEmailId === log.id}
                              className="text-[11px] h-7 px-2"
                            >
                              <RefreshCw
                                size={12}
                                className={
                                  retryingEmailId === log.id ? 'animate-spin mr-1' : 'mr-1'
                                }
                              />
                              {t('settings.storebox.retry')}
                            </Button>
                          )}

                          {/* Delete single log button */}
                          {currentHousehold?.id && (
                            <button
                              type="button"
                              onClick={() => {
                                deleteInboundEmailMutation.mutate(
                                  { householdId: currentHousehold.id, emailId: log.id },
                                  {
                                    onSuccess: () =>
                                      toast.success(t('settings.storebox.deleteLog')),
                                    onError: (err: any) => toast.error(err.message),
                                  }
                                );
                              }}
                              disabled={deleteInboundEmailMutation.isPending}
                              className="p-1 rounded text-muted hover:text-red-500 dark:hover:text-red-400 transition-colors"
                              title={t('settings.storebox.deleteLog')}
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Manual Options: Link or File */}
            <div className="space-y-4 pt-4 border-t border-[hsl(var(--border-color))]">
              {/* Option 2: Paste download link directly */}
              <div>
                <h4 className="text-sm font-medium mb-2">{t('settings.storebox.optionLink')}</h4>
                <div className="flex gap-2">
                  <input
                    type="url"
                    placeholder="https://..."
                    className="flex-1 px-3 py-2 text-sm rounded-lg border border-[hsl(var(--border-color))] bg-transparent"
                    value={storeboxLink}
                    onChange={(e) => setStoreboxLink(e.target.value)}
                  />
                  <Button
                    onClick={() => {
                      if (storeboxLink) {
                        importStoreboxLinkMutation.mutate(storeboxLink, {
                          onSuccess: (data) => {
                            toast.success(t('settings.storebox.importSuccess'));
                            setStoreboxImportResult(data);
                            setStoreboxLink('');
                          },
                          onError: (err) => {
                            toast.error('Kunne ikke importere fra link: ' + err.message);
                          },
                        });
                      }
                    }}
                    disabled={!storeboxLink || importStoreboxLinkMutation.isPending}
                    className="flex items-center gap-2 shrink-0"
                  >
                    {importStoreboxLinkMutation.isPending ? (
                      <RefreshCw className="animate-spin" size={16} />
                    ) : (
                      <LinkIcon size={16} />
                    )}
                    {t('settings.storebox.fetchFromLink')}
                  </Button>
                </div>
              </div>

              {/* Option 3: Upload ZIP or JSON file */}
              <div className="relative pt-2">
                <h4 className="text-sm font-medium mb-2">{t('settings.storebox.optionUpload')}</h4>
                <div className="relative">
                  <input
                    type="file"
                    accept=".zip,.json"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      uploadStoreboxMutation.mutate(file, {
                        onSuccess: (data) => {
                          toast.success(t('settings.storebox.importSuccess'));
                          setStoreboxImportResult(data);
                        },
                        onError: (err) => {
                          toast.error('Kunne ikke importere fil: ' + err.message);
                        },
                      });
                    }}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                    disabled={uploadStoreboxMutation.isPending}
                  />
                  <button
                    className={`w-full py-3 px-4 border-2 border-dashed border-[hsl(var(--border-color))] rounded-xl font-medium flex items-center justify-center gap-2 transition-colors ${uploadStoreboxMutation.isPending ? 'opacity-50 cursor-not-allowed' : 'hover:border-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary))]/5'}`}
                  >
                    {uploadStoreboxMutation.isPending ? (
                      <>
                        <RefreshCw className="animate-spin" size={18} />
                        {t('settings.storebox.uploading')}
                      </>
                    ) : (
                      <>
                        <Upload size={18} />
                        {t('settings.storebox.uploadFile')}
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Coop Receipts Card (Beta) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShoppingBag className="text-[hsl(var(--brand-primary))]" size={24} />
                {t('settings.coop.title')}
              </div>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-[hsl(var(--brand-primary))]/10 text-[hsl(var(--brand-primary))] font-semibold border border-[hsl(var(--brand-primary))]/20">
                BETA
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-sm text-muted leading-relaxed">{t('settings.coop.description')}</p>

            {coopImportResult && (
              <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-xl flex items-start gap-3">
                <CheckCircle className="text-green-500 shrink-0 mt-0.5" size={20} />
                <div className="flex-1">
                  <h4 className="font-semibold text-green-700 dark:text-green-400">
                    {t('settings.coop.importSuccess')}
                  </h4>
                  <ul className="text-sm text-green-600 dark:text-green-300 mt-1 space-y-1">
                    <li>
                      {t('settings.coop.rawReceiptsCount', {
                        count: coopImportResult.raw_receipt_count,
                      })}
                    </li>
                    <li>
                      {t('settings.coop.deduplicatedCount', {
                        count: coopImportResult.deduplicated_receipt_count,
                      })}
                    </li>
                    <li>
                      {t('settings.coop.duplicatesSkipped', {
                        count: coopImportResult.duplicate_receipt_count,
                      })}
                    </li>
                    <li>
                      {t('settings.coop.itemClustersCount', {
                        count: coopImportResult.item_cluster_count,
                      })}
                    </li>
                    <li>
                      {t('settings.coop.merchantsCount', {
                        count: coopImportResult.merchant_count,
                      })}
                    </li>
                    {coopImportResult.auto_linked > 0 && (
                      <li className="font-medium">
                        {t('settings.coop.autoLinkedSuccess', {
                          count: coopImportResult.auto_linked,
                        })}
                      </li>
                    )}
                  </ul>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 border-green-500/20 text-green-700 dark:text-green-400 hover:bg-green-500/10"
                    onClick={() => setCoopImportResult(null)}
                  >
                    {t('settings.coop.importMore')}
                  </Button>
                </div>
              </div>
            )}

            {/* Step-by-Step Bookmarklet Guide */}
            <div className="p-4 rounded-xl border border-[hsl(var(--brand-primary))]/20 bg-[hsl(var(--brand-primary))]/5 space-y-4">
              <div className="flex items-center gap-2">
                <Sparkles className="text-[hsl(var(--brand-primary))]" size={18} />
                <h4 className="font-medium text-sm text-[hsl(var(--text-color))]">
                  {t('settings.coop.bookmarkletTitle')}
                </h4>
              </div>

              <p className="text-xs text-muted leading-relaxed">
                {t('settings.coop.bookmarkletDesc')}
              </p>

              {/* Bookmarklet Drag Button & Copy Action */}
              <div className="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
                <a
                  href={coopBookmarkletHref}
                  onClick={(e) => {
                    e.preventDefault();
                    toast.info('Træk denne knap op på din browsers bogmærkelinje!');
                  }}
                  className="flex-1 px-4 py-2.5 bg-[hsl(var(--brand-primary))] text-white rounded-lg font-medium text-sm text-center shadow hover:opacity-90 transition-opacity cursor-grab active:cursor-grabbing flex items-center justify-center gap-2"
                  title="Træk op på din bogmærkelinje"
                >
                  <ShoppingBag size={16} />
                  {t('settings.coop.dragBookmarklet')}
                </a>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(coopBookmarkletHref);
                    setCopiedBookmarklet(true);
                    toast.success(t('settings.coop.bookmarkletCopied'));
                    setTimeout(() => setCopiedBookmarklet(false), 2000);
                  }}
                  className="flex items-center gap-1.5 shrink-0"
                >
                  {copiedBookmarklet ? (
                    <Check size={14} className="text-green-500" />
                  ) : (
                    <Copy size={14} />
                  )}
                  {copiedBookmarklet
                    ? t('settings.coop.bookmarkletCopied')
                    : t('settings.coop.copyBookmarklet')}
                </Button>
              </div>

              <div className="space-y-1.5 pt-2 text-xs text-muted border-t border-[hsl(var(--border-color))]/50">
                <div className="flex items-center gap-1.5">
                  <span>{t('settings.coop.step1')}</span>
                  <a
                    href="https://medlem.coop.dk/"
                    target="_blank"
                    rel="noreferrer"
                    className="text-[hsl(var(--brand-primary))] font-medium inline-flex items-center gap-0.5 hover:underline"
                  >
                    {t('settings.coop.step1Link')} <ExternalLink size={11} />
                  </a>
                </div>
                <p>{t('settings.coop.step2')}</p>
                <p className="font-medium text-[hsl(var(--text-color))]">
                  {t('settings.coop.step3')}
                </p>
              </div>

              {/* Upload Dropzone */}
              <div className="relative pt-1">
                <div className="relative">
                  <input
                    type="file"
                    accept=".json"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      uploadCoopMutation.mutate(file, {
                        onSuccess: (data) => {
                          toast.success(t('settings.coop.importSuccess'));
                          setCoopImportResult(data);
                        },
                        onError: (err) => {
                          toast.error('Kunne ikke importere Coop fil: ' + err.message);
                        },
                      });
                    }}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                    disabled={uploadCoopMutation.isPending}
                  />
                  <button
                    className={`w-full py-3 px-4 border-2 border-dashed border-[hsl(var(--border-color))] rounded-xl font-medium flex items-center justify-center gap-2 transition-colors ${uploadCoopMutation.isPending ? 'opacity-50 cursor-not-allowed' : 'hover:border-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary))]/5'}`}
                  >
                    {uploadCoopMutation.isPending ? (
                      <>
                        <RefreshCw className="animate-spin" size={18} />
                        {t('settings.coop.uploading')}
                      </>
                    ) : (
                      <>
                        <Upload size={18} />
                        {t('settings.coop.uploadFile')}
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
