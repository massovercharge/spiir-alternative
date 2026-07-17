import React from 'react';
import { clsx } from 'clsx';

export type MonthState = 'active' | 'inactive' | 'over' | 'under';

interface MonthGridProps {
  states: MonthState[];
  startMonth?: number; // 1-indexed, usually 1 for Jan
  showOnlyPassedMonths?: boolean; // If true, only render up to the first 'active' or the length of provided valid states.
}

const MONTH_INITIALS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

export function MonthGrid({ states, startMonth = 1, showOnlyPassedMonths = false }: MonthGridProps) {
  // Ensure we always have exactly 12 states if not showOnlyPassedMonths
  const displayStates = showOnlyPassedMonths 
    ? states 
    : Array.from({ length: 12 }, (_, i) => states[i] || 'inactive');

  const getColor = (state: MonthState) => {
    switch (state) {
      case 'active':
        return 'bg-[hsl(var(--brand-primary))] ring-2 ring-[hsl(var(--brand-primary))] ring-offset-1 ring-offset-[hsl(var(--bg-primary))]';
      case 'under':
        // Spiir green for within budget
        return 'bg-green-500';
      case 'over':
        // Spiir red for exceeded
        return 'bg-red-500';
      case 'inactive':
      default:
        return 'bg-[hsl(var(--bg-tertiary))]';
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1">
        {displayStates.map((_, idx) => (
          <span key={idx} className="text-[9px] text-muted font-medium w-3 text-center uppercase">
            {MONTH_INITIALS[(startMonth - 1 + idx) % 12]}
          </span>
        ))}
      </div>
      <div className="flex items-center gap-1">
        {displayStates.map((state, idx) => (
          <div 
            key={idx} 
            className={clsx(
              "w-3 h-3 rounded-full transition-colors duration-200",
              getColor(state)
            )}
            title={state}
          />
        ))}
      </div>
    </div>
  );
}
