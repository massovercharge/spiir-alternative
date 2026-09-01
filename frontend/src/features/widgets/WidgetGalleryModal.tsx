import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  X,
  Zap,
  ShoppingBag,
  BarChart3,
  TrendingUp,
  PieChart,
  Wallet,
  Calendar,
  ChevronUp,
  ChevronDown,
  FileCode,
  Database,
  FolderOpen,
  Loader2,
} from 'lucide-react';
import { useWidgets, useToggleWidget, useReorderWidget, useReloadWidgets } from '../../api/client';
import { WidgetListItem } from './types';

const ICON_MAP: Record<string, React.ReactNode> = {
  Zap: <Zap size={20} className="text-amber-500" />,
  ShoppingBag: <ShoppingBag size={20} className="text-emerald-500" />,
  BarChart3: <BarChart3 size={20} className="text-blue-500" />,
  TrendingUp: <TrendingUp size={20} className="text-emerald-500" />,
  PieChart: <PieChart size={20} className="text-indigo-500" />,
  Wallet: <Wallet size={20} className="text-purple-500" />,
  Calendar: <Calendar size={20} className="text-rose-500" />,
};

interface WidgetGalleryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const WidgetGalleryModal: React.FC<WidgetGalleryModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const { data: widgets, isLoading, refetch } = useWidgets();
  const toggleMutation = useToggleWidget();
  const reorderMutation = useReorderWidget();
  const reloadMutation = useReloadWidgets();

  if (!isOpen) return null;

  const handleToggle = (item: WidgetListItem) => {
    toggleMutation.mutate({ widgetId: item.manifest.id, enabled: !item.is_enabled });
  };

  const handleReorder = (item: WidgetListItem, direction: 'up' | 'down') => {
    reorderMutation.mutate({ widgetId: item.manifest.id, direction });
  };

  const handleReload = async () => {
    await reloadMutation.mutateAsync();
    refetch();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-[hsl(var(--border-color))]">
          <div>
            <h2 className="text-xl font-bold text-[hsl(var(--text-primary))]">
              {t('widgets.galleryTitle', 'Widget Galleri')}
            </h2>
            <p className="text-xs text-[hsl(var(--text-secondary))] mt-0.5">
              {t('widgets.gallerySubtitle', 'Aktivér eller skjul analyser på dit widget-dashboard')}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Info Box about custom widgets */}
        <div className="p-4 bg-[hsl(var(--bg-tertiary))] border-b border-[hsl(var(--border-color))] text-xs text-[hsl(var(--text-secondary))] flex items-start gap-3">
          <FolderOpen size={20} className="text-[hsl(var(--brand-primary))] shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1">
            <p className="font-semibold text-[hsl(var(--text-primary))]">
              {t('widgets.customFolderTip', 'Tilføj dine egne analyser')}
            </p>
            <p>
              {t(
                'widgets.customFolderDescription',
                'Opret en mappe i data/widgets/<navn>/ med en widget.json fil (og eventuelt et widget.py script). Widgets opdages automatisk.'
              )}
            </p>
          </div>
          <button
            onClick={handleReload}
            disabled={reloadMutation.isPending}
            className="px-2.5 py-1 text-xs rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] hover:bg-[hsl(var(--bg-tertiary))] font-medium text-[hsl(var(--text-primary))] transition-colors shrink-0"
          >
            {reloadMutation.isPending
              ? t('common.loading', 'Indlæser...')
              : t('widgets.scanNow', 'Genscan mappe')}
          </button>
        </div>

        {/* Widgets List */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3">
          {isLoading ? (
            <div className="flex h-40 items-center justify-center text-[hsl(var(--text-secondary))]">
              <Loader2 size={32} className="animate-spin text-[hsl(var(--brand-primary))]" />
            </div>
          ) : !widgets || widgets.length === 0 ? (
            <div className="text-center py-12 text-[hsl(var(--text-secondary))]">
              <p>{t('widgets.noWidgetsFound', 'Ingen widgets fundet i data/widgets/ mappen.')}</p>
            </div>
          ) : (
            widgets.map((item, idx) => {
              const iconComponent = ICON_MAP[item.manifest.icon] || (
                <BarChart3 size={20} className="text-[hsl(var(--brand-primary))]" />
              );

              return (
                <div
                  key={item.manifest.id}
                  className={`p-4 rounded-xl border transition-all flex items-center justify-between gap-4 ${
                    item.is_enabled
                      ? 'bg-[hsl(var(--bg-secondary))] border-[hsl(var(--border-color))] shadow-sm'
                      : 'bg-[hsl(var(--bg-tertiary))]/50 border-[hsl(var(--border-color))]/60 opacity-75'
                  }`}
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="p-2.5 rounded-xl bg-[hsl(var(--bg-tertiary))] shrink-0">
                      {iconComponent}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="font-bold text-sm sm:text-base text-[hsl(var(--text-primary))] truncate">
                          {item.manifest.name}
                        </h4>
                        <span className="text-[11px] px-2 py-0.5 rounded-full bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] font-medium">
                          {item.manifest.category}
                        </span>
                        <span className="text-[11px] px-2 py-0.5 rounded-full bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] font-mono flex items-center gap-1">
                          {item.manifest.type === 'script' ? (
                            <>
                              <FileCode size={11} /> Python
                            </>
                          ) : (
                            <>
                              <Database size={11} /> SQL
                            </>
                          )}
                        </span>
                      </div>
                      <p className="text-xs text-[hsl(var(--text-secondary))] mt-1 line-clamp-2">
                        {item.manifest.description}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {/* Reorder Buttons */}
                    <div className="flex flex-col gap-0.5 mr-1">
                      <button
                        onClick={() => handleReorder(item, 'up')}
                        disabled={idx === 0 || reorderMutation.isPending}
                        className="p-1 rounded text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] disabled:opacity-25"
                        title="Flyt op"
                      >
                        <ChevronUp size={14} />
                      </button>
                      <button
                        onClick={() => handleReorder(item, 'down')}
                        disabled={idx === widgets.length - 1 || reorderMutation.isPending}
                        className="p-1 rounded text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] disabled:opacity-25"
                        title="Flyt ned"
                      >
                        <ChevronDown size={14} />
                      </button>
                    </div>

                    {/* Toggle Switch */}
                    <button
                      onClick={() => handleToggle(item)}
                      disabled={toggleMutation.isPending}
                      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                        item.is_enabled
                          ? 'bg-[hsl(var(--brand-primary))]'
                          : 'bg-[hsl(var(--bg-tertiary))]'
                      }`}
                      role="switch"
                      aria-checked={item.is_enabled}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                          item.is_enabled ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-[hsl(var(--border-color))] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary-dark))] text-white font-medium text-sm transition-colors shadow-sm"
          >
            {t('common.done', 'Færdig')}
          </button>
        </div>
      </div>
    </div>
  );
};
