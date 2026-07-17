import React from 'react';
import { clsx, type ClassValue } from 'clsx';

function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'outline';
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors",
        {
          "bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))]": variant === 'default',
          "bg-success text-success": variant === 'success',
          "bg-danger text-danger": variant === 'danger',
          "bg-[hsla(var(--brand-warning),0.1)] text-[hsl(var(--brand-warning))]": variant === 'warning',
          "border border-[hsl(var(--border-color))] text-[hsl(var(--text-secondary))]": variant === 'outline',
        },
        className
      )}
      {...props}
    />
  );
}
