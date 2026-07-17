import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Users, ChevronDown, Check } from 'lucide-react';

export default function HouseholdSwitcher() {
  const { households, activeHouseholdId, setActiveHousehold } = useHousehold();
  const [isOpen, setIsOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  const activeHousehold = households.find(h => h.id === activeHouseholdId);

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (households.length <= 1) {
    return null; // Don't show switcher if only 1 household
  }

  return (
    <div className="relative mb-4 px-4" ref={menuRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 px-3 py-2 rounded-xl border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors w-full text-left"
      >
        <div className="w-8 h-8 rounded-full bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] flex items-center justify-center flex-shrink-0">
          <Users size={16} />
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-sm font-semibold text-[hsl(var(--text-primary))] truncate">
            {activeHousehold?.name || 'Vælger...'}
          </p>
          <p className="text-[10px] uppercase tracking-wider text-[hsl(var(--text-secondary))] font-medium">
            {activeHousehold?.role === 'owner' ? 'Ejer' : 'Medlem'}
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
                  <p className="text-xs text-[hsl(var(--text-secondary))] capitalize">{hh.role === 'owner' ? 'Ejer' : 'Medlem'}</p>
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
