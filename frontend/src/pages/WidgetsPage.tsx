import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LayoutGrid, RefreshCw, SlidersHorizontal, PlusCircle, Sparkles } from 'lucide-react';
import { useActiveWidgetsData } from '../api/client';
import { WidgetCard } from '../features/widgets/WidgetCard';
import { WidgetGalleryModal } from '../features/widgets/WidgetGalleryModal';
import { Skeleton } from '../components/ui/Skeleton';
import { useQueryClient } from '@tanstack/react-query';

export default function WidgetsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const {
    data: widgets,
    isLoading,
    isRefetching,
    refetch,
    isError,
    error,
  } = useActiveWidgetsData();
  const [isGalleryOpen, setIsGalleryOpen] = useState(false);

  const handleRefreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['widgets', 'active-data'] });
    refetch();
  };

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[hsl(var(--border-color))]">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[hsl(var(--text-primary))]">
              {t('widgets.pageTitle', 'Analyser & Widgets')}
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] border border-[hsla(var(--brand-primary),0.2)] flex items-center gap-1">
              <Sparkles size={12} /> Beta
            </span>
          </div>
          <p className="text-sm text-[hsl(var(--text-secondary))] mt-1">
            {t(
              'widgets.pageSubtitle',
              'Brugerdefinerede analyser og moduler baseret på dine personlige scripts og SQL-forespørgsler'
            )}
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={handleRefreshAll}
            disabled={isLoading || isRefetching}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] hover:bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-primary))] text-sm font-medium transition-colors shadow-sm disabled:opacity-50"
          >
            <RefreshCw size={15} className={isRefetching ? 'animate-spin' : ''} />
            <span>{t('widgets.refreshAll', 'Genindlæs alle')}</span>
          </button>

          <button
            onClick={() => setIsGalleryOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary-dark))] text-white text-sm font-medium transition-colors shadow-sm hover:shadow-md"
          >
            <SlidersHorizontal size={15} />
            <span>{t('widgets.manageWidgets', 'Tilpas widgets')}</span>
          </button>
        </div>
      </div>

      {/* Loading Skeletons */}
      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-96 w-full rounded-2xl" />
          <Skeleton className="h-96 w-full rounded-2xl" />
        </div>
      ) : isError ? (
        <div className="p-6 rounded-2xl bg-[hsla(var(--brand-danger),0.1)] border border-[hsla(var(--brand-danger),0.2)] text-[hsl(var(--text-primary))] space-y-3">
          <div className="font-semibold text-[hsl(var(--brand-danger))] text-base">
            Kunne ikke hente analyser
          </div>
          <p className="text-sm text-[hsl(var(--text-secondary))]">
            {error ? String((error as any)?.message || error) : 'Ukendt netværksfejl'}
          </p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 rounded-xl bg-[hsl(var(--brand-primary))] text-white text-xs font-medium"
          >
            Prøv igen
          </button>
        </div>
      ) : !widgets || widgets.length === 0 ? (
        /* Empty State */
        <div className="text-center py-20 px-4 rounded-3xl border border-dashed border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]/50 space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--brand-primary))] mx-auto flex items-center justify-center shadow-inner">
            <LayoutGrid size={32} />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h3 className="text-lg font-bold text-[hsl(var(--text-primary))]">
              {t('widgets.emptyTitle', 'Ingen aktive widgets')}
            </h3>
            <p className="text-sm text-[hsl(var(--text-secondary))]">
              {t(
                'widgets.emptySubtitle',
                'Du har i øjeblikket ingen widgets slået til på dit dashboard. Åbn galleriet for at aktivere standard-widgets eller dine egne analyser.'
              )}
            </p>
          </div>
          <button
            onClick={() => setIsGalleryOpen(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary-dark))] text-white text-sm font-medium transition-colors shadow-md"
          >
            <PlusCircle size={18} />
            <span>{t('widgets.openGallery', 'Åbn widget galleri')}</span>
          </button>
        </div>
      ) : (
        /* Responsive Grid of Active Widgets */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {widgets.map((w) => (
            <div
              key={w.manifest.id}
              className={w.manifest.width === 'full' ? 'lg:col-span-2' : 'lg:col-span-1'}
            >
              <WidgetCard widget={w} />
            </div>
          ))}
        </div>
      )}

      {/* Gallery Modal */}
      <WidgetGalleryModal isOpen={isGalleryOpen} onClose={() => setIsGalleryOpen(false)} />
    </div>
  );
}
