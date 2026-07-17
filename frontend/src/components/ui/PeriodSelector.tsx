import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './Button';

interface PeriodSelectorProps {
  mode: 'month' | 'year';
  date: Date;
  onChange: (newDate: Date) => void;
}

export function PeriodSelector({ mode, date, onChange }: PeriodSelectorProps) {
  const handlePrev = () => {
    const newDate = new Date(date);
    if (mode === 'month') {
      newDate.setMonth(date.getMonth() - 1);
    } else {
      newDate.setFullYear(date.getFullYear() - 1);
    }
    onChange(newDate);
  };

  const handleNext = () => {
    const newDate = new Date(date);
    if (mode === 'month') {
      newDate.setMonth(date.getMonth() + 1);
    } else {
      newDate.setFullYear(date.getFullYear() + 1);
    }
    onChange(newDate);
  };

  const formattedLabel = mode === 'month' 
    ? date.toLocaleString('da-DK', { month: 'long', year: 'numeric' })
    : date.getFullYear().toString();

  return (
    <div className="flex items-center gap-4 bg-[hsl(var(--bg-tertiary))] rounded-lg p-1 border border-[hsl(var(--border-color))]">
      <Button variant="ghost" size="sm" onClick={handlePrev} className="px-2">
        <ChevronLeft size={18} />
      </Button>
      <span className="font-medium text-sm min-w-[120px] text-center capitalize">
        {formattedLabel}
      </span>
      <Button variant="ghost" size="sm" onClick={handleNext} className="px-2" disabled={date > new Date()}>
        <ChevronRight size={18} />
      </Button>
    </div>
  );
}
