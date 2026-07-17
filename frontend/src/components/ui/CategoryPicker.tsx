import React, { useState, useMemo, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, ChevronDown, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { API_BASE, getHeaders } from '../../api/client';

export interface Category {
  id: string;
  name: string;
  mainCategoryName: string;
  icon: string;
}

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/categories`, { headers: getHeaders() });
      if (!res.ok) throw new Error('Failed to fetch categories');
      const data = await res.json();
      
      // Transform the response into a flat list of subcategories
      const categories: Category[] = (data.categories || []).map((cat: any) => ({
        id: cat.id,
        name: cat.categoryName,
        mainCategoryName: cat.mainCategoryName,
        icon: '📄'
      }));
      return categories;
    }
  });
}

interface CategoryPickerProps {
  selectedCategoryId?: string;
  onSelect?: (categoryId: string) => void;
  value?: string;
  onChange?: (categoryId: string) => void;
  className?: string;
  filterMainCategory?: string;
}

export default function CategoryPicker({ selectedCategoryId, onSelect, value, onChange, className = "", filterMainCategory }: CategoryPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const { data: categories = [], isLoading } = useCategories();
  const { t } = useTranslation();

  const activeValue = value !== undefined ? value : selectedCategoryId;
  const activeOnChange = onChange || onSelect || (() => {});

  const selectedCategory = useMemo(() => {
    return categories.find(c => c.id === activeValue);
  }, [categories, activeValue]);

  const filteredCategories = useMemo(() => {
    let cats = categories;
    if (filterMainCategory) {
      cats = cats.filter(c => c.mainCategoryName === filterMainCategory);
    }
    if (!search) return cats;
    const lowerSearch = search.toLowerCase();
    return cats.filter(c => 
      c.name.toLowerCase().includes(lowerSearch) || 
      c.mainCategoryName.toLowerCase().includes(lowerSearch)
    );
  }, [categories, search, filterMainCategory]);

  const groupedCategories = useMemo(() => {
    const groups: Record<string, Category[]> = {};
    filteredCategories.forEach(c => {
      if (!groups[c.mainCategoryName]) groups[c.mainCategoryName] = [];
      groups[c.mainCategoryName].push(c);
    });
    return groups;
  }, [filteredCategories]);

  const buttonRef = useRef<HTMLButtonElement>(null);
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;
      const popoverWidth = 256;
      
      // Prevent popover from overflowing the right edge of the screen
      const leftPos = Math.max(8, Math.min(rect.left, window.innerWidth - popoverWidth - 8));
      
      // If there's less than 300px below and more space above, open upwards
      if (spaceBelow < 300 && spaceAbove > spaceBelow) {
        setPopoverStyle({
          position: 'fixed',
          bottom: window.innerHeight - rect.top + 8,
          left: leftPos,
          width: popoverWidth, // 16rem = w-64
          maxHeight: Math.min(spaceAbove - 16, 384) // max 384px (h-96)
        });
      } else {
        // Open downwards
        setPopoverStyle({
          position: 'fixed',
          top: rect.bottom + 8,
          left: leftPos,
          width: popoverWidth,
          maxHeight: Math.min(spaceBelow - 16, 384)
        });
      }
    }
  }, [isOpen]);

  return (
    <div className={`relative min-w-0 max-w-full ${className}`}>
      {/* Trigger */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full bg-[hsla(var(--border-color),0.3)] hover:bg-[hsla(var(--border-color),0.6)] transition-colors border border-[hsla(var(--border-color),0.5)] max-w-full shrink-0"
      >
        <span className="truncate max-w-[150px] sm:max-w-[200px] capitalize">
          {selectedCategory ? selectedCategory.name.replace('-', ' ') : t('transactions.uncategorized')}
        </span>
        <ChevronDown size={14} className="opacity-50 shrink-0" />
      </button>

      {/* Popover */}
      {isOpen && typeof document !== 'undefined' && createPortal(
        <>
          <div className="fixed inset-0 z-[100]" onClick={() => setIsOpen(false)} />
          <div 
            style={popoverStyle}
            className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-xl shadow-xl z-[100] overflow-hidden flex flex-col"
          >
            
            {/* Search */}
            <div className="p-3 border-b border-[hsl(var(--border-color))] flex items-center gap-2 bg-[hsl(var(--bg-primary))]">
              <Search size={16} className="text-muted shrink-0" />
              <input 
                type="text"
                placeholder={t('app.search') + "..."}
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full bg-transparent outline-none text-sm"
                autoFocus
              />
            </div>

            {/* List */}
            <div className="overflow-y-auto flex-1 p-2 space-y-4">
              {isLoading && <p className="text-center text-sm text-muted p-4">Henter...</p>}
              
              {!isLoading && Object.keys(groupedCategories).length === 0 && (
                <p className="text-center text-sm text-muted p-4">Ingen kategorier fundet</p>
              )}

              {Object.entries(groupedCategories).map(([mainCatName, subs]) => (
                <div key={mainCatName} className="space-y-1">
                  <div className="text-[10px] font-bold text-muted uppercase tracking-wider px-2 pt-1">
                    {mainCatName.replace('-', ' ')}
                  </div>
                  {subs.map(sub => (
                    <button
                      key={sub.id}
                      onClick={() => {
                        activeOnChange(sub.id);
                        setIsOpen(false);
                      }}
                      className="w-full text-left flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-[hsl(var(--brand-primary))] hover:text-white group transition-colors"
                    >
                      <span className="text-sm capitalize truncate">{sub.name.replace('-', ' ')}</span>
                      {selectedCategoryId === sub.id && (
                        <Check size={14} className="text-[hsl(var(--brand-primary))] group-hover:text-white" />
                      )}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
}
