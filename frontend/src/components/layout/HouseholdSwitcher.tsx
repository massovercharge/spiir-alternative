import React from 'react';
import { createPortal } from 'react-dom';
import { useHousehold } from '../../context/HouseholdContext';
import { Users, ChevronDown, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface HouseholdSwitcherProps {
  compact?: boolean;
  className?: string;
}

export default function HouseholdSwitcher({ compact = false, className = '' }: HouseholdSwitcherProps) {
  const { t } = useTranslation();
  const { households, activeHouseholdId, setActiveHousehold } = useHousehold();
  const [isOpen, setIsOpen] = React.useState(false);
  const buttonRef = React.useRef<HTMLButtonElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [popoverStyle, setPopoverStyle] = React.useState<React.CSSProperties>({});

  const activeHousehold = households.find(h => h.id === activeHouseholdId);

  React.useLayoutEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const popoverWidth = 240;
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

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (households.length <= 1) {
    if (compact && activeHousehold) {
      return (
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[hsla(var(--brand-primary),0.08)] border border-[hsla(var(--brand-primary),0.2)] text-xs font-semibold text-[hsl(var(--brand-primary))] max-w-[130px] sm:max-w-[160px] ${className}`}>
          <Users size={12} className="shrink-0 text-[hsl(var(--brand-primary))]" />
          <span className="truncate">{activeHousehold.name}</span>
        </div>
      );
    }
    return null;
  }

  const getRoleLabel = (role: string) => {
    return role === 'owner' ? t('settings.roleOwner', 'Ejer') : t('settings.roleMember', 'Medlem');
  };

  if (compact) {
    return (
      <div className={`relative ${className}`}>
        <button
          ref={buttonRef}
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-tertiary))] hover:bg-[hsl(var(--bg-primary))] text-xs font-semibold text-[hsl(var(--text-primary))] transition-colors max-w-[160px]"
        >
          <Users size={14} className="text-[hsl(var(--brand-primary))] shrink-0" />
          <span className="truncate">{activeHousehold?.name || t('common.loading')}</span>
          <ChevronDown size={14} className={`text-[hsl(var(--text-secondary))] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && typeof document !== 'undefined' && createPortal(
          <>
            <div className="fixed inset-0 z-[998]" onClick={() => setIsOpen(false)} />
            <div 
              style={popoverStyle}
              className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-xl shadow-2xl overflow-hidden z-[999] animate-in fade-in slide-in-from-top-2 duration-200"
            >
              <div className="p-2 space-y-1 max-h-64 overflow-y-auto">
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
        className="flex items-center gap-3 px-3 py-2 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors w-full text-left"
      >
        <div className="w-8 h-8 rounded-full bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] flex items-center justify-center flex-shrink-0">
          <Users size={16} />
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-sm font-semibold text-[hsl(var(--text-primary))] truncate">
            {activeHousehold?.name || t('common.loading')}
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
          </div>
        </div>
      )}
    </div>
  );
}
