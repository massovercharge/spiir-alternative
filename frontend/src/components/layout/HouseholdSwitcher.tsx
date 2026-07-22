import React, { useState, useRef, useLayoutEffect, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useHousehold } from '../../context/HouseholdContext';
import { useCreateHousehold } from '../../api/client';
import { Users, ChevronDown, Check, Plus, Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

interface HouseholdSwitcherProps {
  compact?: boolean;
  className?: string;
}

export default function HouseholdSwitcher({ compact = false, className = '' }: HouseholdSwitcherProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { households, activeHouseholdId, setActiveHousehold } = useHousehold();
  const createHouseholdMutation = useCreateHousehold();

  const [isOpen, setIsOpen] = useState(false);
  const [isCreatingInline, setIsCreatingInline] = useState(false);
  const [newHouseholdName, setNewHouseholdName] = useState('');

  const buttonRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});

  const activeHousehold = households.find(h => h.id === activeHouseholdId);

  useLayoutEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const popoverWidth = 260;
      const leftPos = Math.max(12, Math.min(rect.left, window.innerWidth - popoverWidth - 12));
      
      setPopoverStyle({
        position: 'fixed',
        top: rect.bottom + 8,
        left: leftPos,
        width: popoverWidth,
        zIndex: 999,
      });
    }
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setIsCreatingInline(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const getRoleLabel = (role: string) => {
    return role === 'owner' ? t('settings.roleOwner', 'Ejer') : t('settings.roleMember', 'Medlem');
  };

  const handleCreateHousehold = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newHouseholdName.trim()) return;

    createHouseholdMutation.mutate(newHouseholdName.trim(), {
      onSuccess: (data: any) => {
        setNewHouseholdName('');
        setIsCreatingInline(false);
        setIsOpen(false);
        if (data?.id) {
          setActiveHousehold(data.id);
        }
        toast.success(t('settings.householdCreated', 'Ny husstand oprettet!'));
      },
      onError: (err: any) => {
        toast.error(err?.message || t('settings.failedToCreate', 'Kunne ikke oprette husstand'));
      }
    });
  };

  if (compact) {
    return (
      <div className={`relative ${className}`}>
        <button
          ref={buttonRef}
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-tertiary))] hover:bg-[hsl(var(--bg-primary))] text-xs font-semibold text-[hsl(var(--text-primary))] transition-colors max-w-[160px] cursor-pointer"
        >
          <Users size={14} className="text-[hsl(var(--brand-primary))] shrink-0" />
          <span className="truncate">{activeHousehold?.name || households[0]?.name || t('common.loading')}</span>
          <ChevronDown size={14} className={`text-[hsl(var(--text-secondary))] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && typeof document !== 'undefined' && createPortal(
          <>
            <div className="fixed inset-0 z-[998]" onClick={() => { setIsOpen(false); setIsCreatingInline(false); }} />
            <div 
              style={popoverStyle}
              className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-xl shadow-2xl overflow-hidden z-[999] animate-in fade-in slide-in-from-top-2 duration-200"
            >
              <div className="p-2 space-y-1 max-h-72 overflow-y-auto">
                {households.map((hh) => (
                  <button
                    key={hh.id}
                    onClick={() => {
                      setActiveHousehold(hh.id);
                      setIsOpen(false);
                    }}
                    className={`flex items-center gap-2.5 w-full p-2 rounded-lg text-left transition-colors ${
                      activeHouseholdId === hh.id 
                        ? 'bg-[hsla(var(--brand-primary),0.1)]' 
                        : 'hover:bg-[hsl(var(--bg-tertiary))]'
                    }`}
                  >
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                      activeHouseholdId === hh.id 
                        ? 'bg-[hsl(var(--brand-primary))] text-white' 
                        : 'bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))]'
                    }`}>
                      <Users size={14} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs font-medium truncate ${
                        activeHouseholdId === hh.id ? 'text-[hsl(var(--brand-primary))]' : 'text-[hsl(var(--text-primary))]'
                      }`}>
                        {hh.name}
                      </p>
                      <p className="text-[10px] text-[hsl(var(--text-secondary))] capitalize">{getRoleLabel(hh.role)}</p>
                    </div>
                    {activeHouseholdId === hh.id && (
                      <Check size={14} className="text-[hsl(var(--brand-primary))]" />
                    )}
                  </button>
                ))}

                <div className="my-1 border-t border-[hsl(var(--border-color))]" />

                {isCreatingInline ? (
                  <form onSubmit={handleCreateHousehold} className="p-1 space-y-2">
                    <input
                      type="text"
                      autoFocus
                      placeholder={t('settings.householdNamePlaceholder', 'Navn på ny husstand')}
                      value={newHouseholdName}
                      onChange={(e) => setNewHouseholdName(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] outline-none text-[hsl(var(--text-primary))]"
                    />
                    <div className="flex gap-1.5">
                      <button
                        type="submit"
                        disabled={!newHouseholdName.trim() || createHouseholdMutation.isPending}
                        className="flex-1 text-xs py-1 rounded-md bg-[hsl(var(--brand-primary))] text-white font-medium hover:opacity-90 disabled:opacity-50"
                      >
                        {createHouseholdMutation.isPending ? 'Opretter...' : 'Opret'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setIsCreatingInline(false)}
                        className="px-2 text-xs py-1 rounded-md border border-[hsl(var(--border-color))] text-[hsl(var(--text-secondary))]"
                      >
                        Annuller
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    onClick={() => setIsCreatingInline(true)}
                    className="flex items-center gap-2.5 w-full p-2 rounded-lg text-left text-xs font-medium text-[hsl(var(--brand-primary))] hover:bg-[hsla(var(--brand-primary),0.08)] transition-colors"
                  >
                    <div className="w-7 h-7 rounded-full bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] flex items-center justify-center shrink-0">
                      <Plus size={14} />
                    </div>
                    <span>{t('settings.createHousehold', 'Opret ny husstand')}</span>
                  </button>
                )}

                <button
                  onClick={() => {
                    setIsOpen(false);
                    navigate('/settings');
                  }}
                  className="flex items-center gap-2.5 w-full p-2 rounded-lg text-left text-xs font-medium text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
                >
                  <div className="w-7 h-7 rounded-full bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] flex items-center justify-center shrink-0">
                    <Settings size={14} />
                  </div>
                  <span>{t('app.settings', 'Indstillinger')}</span>
                </button>
              </div>
            </div>
          </>,
          document.body
        )}
      </div>
    );
  }

  return (
    <div className={`relative mb-4 px-4 ${className}`} ref={containerRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 px-3 py-2 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors w-full text-left cursor-pointer"
      >
        <div className="w-8 h-8 rounded-full bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] flex items-center justify-center flex-shrink-0">
          <Users size={16} />
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-sm font-semibold text-[hsl(var(--text-primary))] truncate">
            {activeHousehold?.name || households[0]?.name || t('common.loading')}
          </p>
          <p className="text-[10px] uppercase tracking-wider text-[hsl(var(--text-secondary))] font-medium">
            {activeHousehold?.role ? getRoleLabel(activeHousehold.role) : ''}
          </p>
        </div>
        <ChevronDown size={16} className={`text-[hsl(var(--text-secondary))] transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-4 right-4 mt-2 bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-xl shadow-xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="p-2 space-y-1 max-h-64 overflow-y-auto">
            {households.map((hh) => (
              <button
                key={hh.id}
                onClick={() => {
                  setActiveHousehold(hh.id);
                  setIsOpen(false);
                }}
                className={`flex items-center gap-3 w-full p-2 rounded-lg text-left transition-colors ${
                  activeHouseholdId === hh.id 
                    ? 'bg-[hsla(var(--brand-primary),0.1)]' 
                    : 'hover:bg-[hsl(var(--bg-tertiary))]'
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  activeHouseholdId === hh.id 
                    ? 'bg-[hsl(var(--brand-primary))] text-white' 
                    : 'bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))]'
                }`}>
                  <Users size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${
                    activeHouseholdId === hh.id ? 'text-[hsl(var(--brand-primary))]' : 'text-[hsl(var(--text-primary))]'
                  }`}>
                    {hh.name}
                  </p>
                  <p className="text-xs text-[hsl(var(--text-secondary))] capitalize">{getRoleLabel(hh.role)}</p>
                </div>
                {activeHouseholdId === hh.id && (
                  <Check size={16} className="text-[hsl(var(--brand-primary))]" />
                )}
              </button>
            ))}

            <div className="my-1 border-t border-[hsl(var(--border-color))]" />

            {isCreatingInline ? (
              <form onSubmit={handleCreateHousehold} className="p-1 space-y-2">
                <input
                  type="text"
                  autoFocus
                  placeholder={t('settings.householdNamePlaceholder', 'Navn på ny husstand')}
                  value={newHouseholdName}
                  onChange={(e) => setNewHouseholdName(e.target.value)}
                  className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] outline-none text-[hsl(var(--text-primary))]"
                />
                <div className="flex gap-1.5">
                  <button
                    type="submit"
                    disabled={!newHouseholdName.trim() || createHouseholdMutation.isPending}
                    className="flex-1 text-xs py-1 rounded-md bg-[hsl(var(--brand-primary))] text-white font-medium hover:opacity-90 disabled:opacity-50"
                  >
                    {createHouseholdMutation.isPending ? 'Opretter...' : 'Opret'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsCreatingInline(false)}
                    className="px-2 text-xs py-1 rounded-md border border-[hsl(var(--border-color))] text-[hsl(var(--text-secondary))]"
                  >
                    Annuller
                  </button>
                </div>
              </form>
            ) : (
              <button
                onClick={() => setIsCreatingInline(true)}
                className="flex items-center gap-2.5 w-full p-2 rounded-lg text-left text-xs font-medium text-[hsl(var(--brand-primary))] hover:bg-[hsla(var(--brand-primary),0.08)] transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] flex items-center justify-center shrink-0">
                  <Plus size={16} />
                </div>
                <span>{t('settings.createHousehold', 'Opret ny husstand')}</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
