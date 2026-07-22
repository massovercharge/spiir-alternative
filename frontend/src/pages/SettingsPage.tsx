import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useTheme } from '../theme/ThemeProvider';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Moon, Sun, Monitor, Languages, Building2, Plus, RefreshCw, Trash2, Upload, CheckCircle, ListFilter, Link as LinkIcon, ShoppingBag, FileText } from 'lucide-react';
import { useBankConnections, useConnectBank, useStartSync, useSyncStatus, useUploadSpiirExport, useRules, useDeleteRule, useHouseholdMembers, useInviteHouseholdMember, useCreateHousehold, useUpdateHousehold, useUploadStoreboxFile, useImportStoreboxLink } from '../api/client';
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
  const startSyncMutation = useStartSync();
  const queryClient = useQueryClient();
  const [isPollingSync, setIsPollingSync] = React.useState(false);
  
  const { data: syncStatus } = useSyncStatus(isPollingSync);
  
  React.useEffect(() => {
    if (isPollingSync && syncStatus) {
      if (syncStatus.status === 'succeeded' || syncStatus.status === 'completed_with_errors' || syncStatus.status === 'failed') {
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
  
  const { activeHouseholdId, households, setActiveHousehold } = useHousehold();
  const currentHousehold = households.find((h: any) => h.id === activeHouseholdId);
  const { data: members = [] } = useHouseholdMembers(activeHouseholdId || '');
  const inviteMemberMutation = useInviteHouseholdMember();
  const createHouseholdMutation = useCreateHousehold();
  const updateHouseholdMutation = useUpdateHousehold();
  
  const [inviteEmail, setInviteEmail] = React.useState('');
  const [newHouseholdName, setNewHouseholdName] = React.useState('');
  const [renameHouseholdName, setRenameHouseholdName] = React.useState('');

  React.useEffect(() => {
    if (currentHousehold?.name) {
      setRenameHouseholdName(currentHousehold.name);
    }
  }, [currentHousehold?.name]);
  const [importResult, setImportResult] = React.useState<any>(null);
  const [storeboxImportResult, setStoreboxImportResult] = React.useState<any>(null);

  const uploadStoreboxMutation = useUploadStoreboxFile();
  const importStoreboxLinkMutation = useImportStoreboxLink();
  const [storeboxLink, setStoreboxLink] = React.useState('');

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    uploadSpiirExportMutation.mutate(file, {
      onSuccess: (data) => {
        setImportResult(data);
      }
    });
  };

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    localStorage.setItem('peng-lang', lang);
  };

  const handleConnectBank = () => {
    connectBankMutation.mutate(window.location.origin + '/dashboard', {
      onSuccess: (data) => {
        if (data.auth_url) {
          window.location.href = data.auth_url;
        }
      }
    });
  };

  const handleSync = () => {
    startSyncMutation.mutate(undefined, {
      onSuccess: () => {
        setIsPollingSync(true);
        toast.info('Synkronisering startet...');
      },
      onError: (error) => {
        toast.error('Kunne ikke starte synkronisering: ' + error.message);
      }
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
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
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

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
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
        
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.22 }}>
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

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
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
                        updateHouseholdMutation.mutate({ householdId: activeHouseholdId, name: renameHouseholdName.trim() }, {
                          onSuccess: () => {
                            toast.success(t('settings.householdUpdated'));
                          },
                          onError: (err: any) => {
                            toast.error(err?.message || t('settings.failedToUpdate'));
                          }
                        });
                      }
                    }}
                    disabled={!renameHouseholdName.trim() || updateHouseholdMutation.isPending || renameHouseholdName.trim() === currentHousehold?.name}
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
                    <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-tertiary))]">
                      <div>
                        <p className="font-semibold text-sm text-[hsl(var(--text-primary))]">
                          {mainText}
                        </p>
                        {member.email && member.email !== mainText && (
                          <p className="text-xs text-muted">{member.email}</p>
                        )}
                      </div>
                      <span className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--brand-primary))] px-2 py-1 rounded bg-[hsla(var(--brand-primary),0.1)]">
                        {member.role}
                      </span>
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
                <Button 
                  onClick={() => {
                    if (activeHouseholdId && inviteEmail) {
                      inviteMemberMutation.mutate({ householdId: activeHouseholdId, email: inviteEmail }, {
                        onSuccess: () => {
                          setInviteEmail('');
                          toast.success(t('settings.householdInvited'));
                        },
                        onError: (err: any) => {
                          toast.error(err?.message || t('settings.failedToInvite'));
                        }
                      });
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
                        }
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
                <h3 className="text-sm font-medium mb-3">{t('settings.switchHousehold', 'Skift aktiv husstand')}</h3>
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
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                        activeHouseholdId === hh.id ? 'bg-[hsl(var(--brand-primary))] text-white' : 'bg-[hsl(var(--bg-tertiary))]'
                      }`}>
                        <Users size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{hh.name}</p>
                        <p className="text-xs text-muted capitalize">{hh.role === 'owner' ? t('settings.roleOwner', 'Ejer') : t('settings.roleMember', 'Medlem')}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListFilter size={20} className="text-[hsl(var(--brand-primary))]" />
              Dine Kategoriseringsregler
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingRules ? (
              <p className="text-sm text-muted">Henter regler...</p>
            ) : userRules.length === 0 ? (
              <p className="text-sm text-muted">Du har ikke oprettet nogen personlige regler endnu.</p>
            ) : (
              <div className="space-y-3">
                {userRules.map((rule: any) => {
                  const catParts = (rule.category_id || '').split('|');
                  const catName = catParts[1] ? catParts[1] : catParts[0];
                  return (
                    <div key={rule.id} className="flex items-center justify-between p-3 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-tertiary))]">
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
                          if (confirm('Er du sikker på du vil slette denne regel? (Allerede ændrede transaktioner ændres ikke tilbage)')) {
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

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
        <Card>
          <CardHeader>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Building2 size={20} className="text-[hsl(var(--brand-primary))]" />
                  Bankforbindelser
                </CardTitle>
                <p className="text-sm text-muted">
                  Forbind dine bankkonti for automatisk import af transaktioner
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleSync}
                  disabled={startSyncMutation.isPending || isPollingSync}
                  className="flex items-center gap-2 px-3 py-2 text-sm font-medium border border-[hsl(var(--border-color))] rounded-lg hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
                >
                  <RefreshCw size={16} className={startSyncMutation.isPending || isPollingSync ? 'animate-spin' : ''} />
                  {isPollingSync ? 'Synkroniserer...' : 'Synkroniser'}
                </button>
                <div className="flex flex-col items-end gap-1">
                  <button
                    onClick={handleConnectBank}
                    disabled={connectBankMutation.isPending}
                    className="btn btn-primary disabled:opacity-50"
                  >
                    <Plus size={16} />
                    Forbind til bank
                  </button>
                  {connectBankMutation.isError && (
                    <span className="text-xs text-red-500">
                      Fejl: {connectBankMutation.error?.message}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingBanks ? (
              <div className="py-8 text-center text-muted animate-pulse">Henter forbindelser...</div>
            ) : bankConnections?.length === 0 ? (
              <div className="py-8 text-center text-muted border-2 border-dashed border-[hsl(var(--border-color))] rounded-lg">
                Ingen aktive bankforbindelser endnu.
              </div>
            ) : (
              <div className="space-y-4">
                {bankConnections?.map((conn: any) => (
                  <div key={conn.id} className="flex items-center justify-between p-4 border border-[hsl(var(--border-color))] rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-[hsl(var(--bg-tertiary))] rounded-full">
                        <Building2 size={20} className="text-[hsl(var(--text-secondary))]" />
                      </div>
                      <div>
                        <div className="font-medium text-[hsl(var(--text-primary))]">{conn.bank_name}</div>
                        <div className="text-xs text-muted">Forbundet: {new Date(conn.created_at).toLocaleDateString()} &middot; Status: {conn.status}</div>
                      </div>
                    </div>
                    <button className="p-2 text-[hsl(var(--text-secondary))] hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-colors">
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
              Upload dit historiske CSV-udtræk fra Spiir. Vi fletter dine gamle transaktioner sammen med de nye og bevarer dine eksisterende kategoriseringer uden at skabe dubletter.
            </p>
            
            {importResult ? (
              <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-lg flex items-start gap-3">
                <CheckCircle className="text-green-500 shrink-0 mt-0.5" size={20} />
                <div>
                  <h4 className="font-semibold text-green-700 dark:text-green-400">Import fuldført!</h4>
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
        {/* Storebox Import Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShoppingBag className="text-[hsl(var(--brand-primary))]" size={24} />
              Importér Storebox-data
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-sm text-muted leading-relaxed">
              Importér dine digitale kvitteringer fra Storebox (Nexi). Du kan enten uploade den ZIP- eller JSON-fil, du har fået, eller indsætte det "DOWNLOAD DATA"-link du har modtaget i din e-mail.
            </p>

            {storeboxImportResult ? (
              <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-lg flex items-start gap-3">
                <CheckCircle className="text-green-500 shrink-0 mt-0.5" size={20} />
                <div>
                  <h4 className="font-semibold text-green-700 dark:text-green-400">Storebox import fuldført!</h4>
                  <ul className="text-sm text-green-600 dark:text-green-300 mt-1 space-y-1">
                    <li>Læste {storeboxImportResult.raw_receipt_count} kvitteringer fra filen</li>
                    <li>Importerede {storeboxImportResult.deduplicated_receipt_count} unikke kvitteringer</li>
                    <li>Sprang {storeboxImportResult.duplicate_receipt_count} dubletter over</li>
                    <li>Registrerede {storeboxImportResult.item_cluster_count} vare-produkter</li>
                    <li>Fandt {storeboxImportResult.merchant_count} butikker</li>
                    {storeboxImportResult.auto_linked > 0 && (
                      <li>Autokoblede automatisk {storeboxImportResult.auto_linked} kvitteringer til dine bankposteringer!</li>
                    )}
                  </ul>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="mt-4 border-green-500/20 text-green-700 dark:text-green-400 hover:bg-green-500/10"
                    onClick={() => setStoreboxImportResult(null)}
                  >
                    Importér flere
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 pt-2">

              <div>
                <h4 className="text-sm font-medium mb-2">Mulighed 1: Indsæt download-link</h4>
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
                            toast.success('Storebox kvitteringer blev importeret!');
                            setStoreboxImportResult(data);
                            setStoreboxLink('');
                          },
                          onError: (err) => {
                            toast.error('Kunne ikke importere fra link: ' + err.message);
                          }
                        });
                      }
                    }}
                    disabled={!storeboxLink || importStoreboxLinkMutation.isPending}
                    className="flex items-center gap-2"
                  >
                    {importStoreboxLinkMutation.isPending ? <RefreshCw className="animate-spin" size={16} /> : <LinkIcon size={16} />}
                    Hent fra link
                  </Button>
                </div>
              </div>

              <div className="relative pt-4 border-t border-[hsl(var(--border-color))]">
                <h4 className="text-sm font-medium mb-2">Mulighed 2: Upload ZIP eller JSON</h4>
                <div className="relative">
                  <input 
                    type="file" 
                    accept=".zip,.json"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      uploadStoreboxMutation.mutate(file, {
                        onSuccess: (data) => {
                          toast.success('Storebox kvitteringer blev importeret!');
                          setStoreboxImportResult(data);
                        },
                        onError: (err) => {
                          toast.error('Kunne ikke importere fil: ' + err.message);
                        }
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
                        Importerer fil...
                      </>
                    ) : (
                      <>
                        <Upload size={18} />
                        Vælg Storebox export (ZIP/JSON)
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
