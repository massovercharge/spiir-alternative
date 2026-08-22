import React from 'react';
import { clsx, type ClassValue } from 'clsx';

function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg' | 'icon';
}

export function Button({ 
  className, 
  variant = 'primary', 
  size = 'md', 
  ...props 
}: ButtonProps) {
  return (
    <button
      className={cn(
        'btn',
        {
          'btn-primary': variant === 'primary',
          'btn-outline': variant === 'outline',
          'hover:bg-[hsl(var(--bg-tertiary))]': variant === 'ghost',
          'px-3 py-1.5 text-sm': size === 'sm',
          'px-4 py-2': size === 'md',
          'px-6 py-3 text-lg': size === 'lg',
          'h-8 w-8 p-0': size === 'icon',
        },
        className
      )}
      {...props}
    />
  );
}
