import React, { useState, useMemo, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, ChevronDown, Check, X } from 'lucide-react';
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
  placeholder?: string;
}

export default function CategoryPicker({ selectedCategoryId, onSelect, value, onChange, className = "", filterMainCategory, placeholder }: CategoryPickerProps) {
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

  const wrapperRef = useRef<HTMLDivElement>(null);
  const portalRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Auto-scroll list to top when search query changes or dropdown opens
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [search, isOpen]);

  // Click / touch outside handler
  useEffect(() => {
    function handleClickOutside(event: MouseEvent | TouchEvent) {
      const target = event.target as Node;
      if (
        (wrapperRef.current && wrapperRef.current.contains(target)) ||
        (portalRef.current && portalRef.current.contains(target))
      ) {
        return;
      }
      setIsOpen(false);
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('touchstart', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [isOpen]);

  const [isMobile, setIsMobile] = useState(() => 
    typeof window !== 'undefined' ? window.innerWidth < 768 : false
  );
  
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Track visual viewport height on mobile to adapt dynamically above software keyboard
  const [viewportHeight, setViewportHeight] = useState<number | null>(null);

  useEffect(() => {
    if (!isOpen || !isMobile) return;

    const updateHeight = () => {
      if (window.visualViewport) {
        setViewportHeight(window.visualViewport.height);
      }
    };

    updateHeight();
    window.visualViewport?.addEventListener('resize', updateHeight);
    window.visualViewport?.addEventListener('scroll', updateHeight);

    return () => {
      window.visualViewport?.removeEventListener('resize', updateHeight);
      window.visualViewport?.removeEventListener('scroll', updateHeight);
    };
  }, [isOpen, isMobile]);

  // Desktop screen-bounded positioning
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({});

  useLayoutEffect(() => {
    if (isOpen && buttonRef.current && !isMobile) {
      const updatePosition = () => {
        if (!buttonRef.current) return;
        const rect = buttonRef.current.getBoundingClientRect();
        const popoverWidth = 280;
        const padding = 12;

        // Keep horizontal position strictly within viewport
        let left = rect.left;
        if (left + popoverWidth > window.innerWidth - padding) {
          left = window.innerWidth - popoverWidth - padding;
        }
        if (left < padding) {
          left = padding;
        }

        // Keep vertical position and maxHeight strictly within viewport
        const spaceBelow = window.innerHeight - rect.bottom - padding;
        const spaceAbove = rect.top - padding;

        let top: number;
        let maxHeight: number;

        if (spaceBelow >= 260 || spaceBelow >= spaceAbove) {
          top = rect.bottom + 6;
          maxHeight = Math.min(384, Math.max(160, spaceBelow));
        } else {
          maxHeight = Math.min(384, Math.max(160, spaceAbove));
          top = Math.max(padding, rect.top - maxHeight - 6);
        }

        setPopoverStyle({
          position: 'fixed',
          top: `${top}px`,
          left: `${left}px`,
          width: `${popoverWidth}px`,
          maxHeight: `${maxHeight}px`,
          zIndex: 9999,
        });
      };

      updatePosition();
      window.addEventListener('resize', updatePosition);
      window.addEventListener('scroll', updatePosition, true);
      return () => {
        window.removeEventListener('resize', updatePosition);
        window.removeEventListener('scroll', updatePosition, true);
      };
    }
  }, [isOpen, isMobile]);

  return (
    <div ref={wrapperRef} className={`relative min-w-0 max-w-full ${className}`}>
      {/* Trigger */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full bg-[hsla(var(--border-color),0.3)] hover:bg-[hsla(var(--border-color),0.6)] transition-colors border border-[hsla(var(--border-color),0.5)] max-w-full shrink-0"
      >
        <span className="truncate max-w-[150px] sm:max-w-[200px] capitalize">
          {selectedCategory ? selectedCategory.name.replace('-', ' ') : (placeholder || t('transactions.uncategorized', 'Ukategoriseret'))}
        </span>
        <ChevronDown size={14} className="opacity-50 shrink-0" />
      </button>

      {/* Popover */}
      {isOpen && typeof document !== 'undefined' && (
        isMobile ? createPortal(
          <div ref={portalRef} className="fixed inset-0 z-[100] flex flex-col">
            <div 
              className="fixed inset-0 bg-black/60 z-[100]" 
              onClick={() => setIsOpen(false)} 
            />
            <div 
              style={{
                height: viewportHeight ? `${viewportHeight}px` : '100dvh',
                maxHeight: viewportHeight ? `${viewportHeight}px` : '100dvh',
              }}
              className="relative w-full bg-[hsl(var(--bg-secondary))] z-[101] overflow-hidden flex flex-col animate-in fade-in duration-150"
            >
              {/* Mobile Header with notch safe area */}
              <div className="pt-safe px-4 py-3 border-b border-[hsl(var(--border-color))] flex justify-between items-center bg-[hsl(var(--bg-secondary))] shrink-0">
                <h3 className="font-semibold text-base">{t('categories.selectCategory', 'Vælg kategori')}</h3>
                <button 
                  type="button"
                  onClick={() => setIsOpen(false)} 
                  className="text-sm text-muted hover:text-[hsl(var(--text-primary))] font-medium py-1 px-2"
                >
                  {t('common.close', 'Luk')}
                </button>
              </div>

              {/* Search input with 16px text-base to prevent iOS browser auto-zoom */}
              <div className="p-3 border-b border-[hsl(var(--border-color))] flex items-center gap-2 bg-[hsl(var(--bg-primary))] shrink-0">
                <Search size={18} className="text-muted shrink-0" />
                <input 
                  type="text"
                  placeholder={t('app.search', { defaultValue: 'Søg' }) + "..."}
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full bg-transparent outline-none text-base"
                  autoFocus
                />
                {search && (
                  <button 
                    type="button"
                    onClick={() => setSearch('')}
                    className="p-1 text-muted hover:text-[hsl(var(--text-primary))] shrink-0"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              {/* List starts immediately below search box and scrolls within available viewport height */}
              <div ref={listRef} className="overflow-y-auto flex-1 min-h-0 p-3 space-y-4">
                {isLoading && <p className="text-center text-sm text-muted p-4">{t('common.loading', 'Henter...')}</p>}
                
                {!isLoading && Object.keys(groupedCategories).length === 0 && (
                  <p className="text-center text-sm text-muted p-4">{t('categories.noCategoriesFound', 'Ingen kategorier fundet')}</p>
                )}

                {Object.entries(groupedCategories).map(([mainCatName, subs]) => (
                  <div key={mainCatName} className="space-y-1">
                    <div className="text-[10px] font-bold text-muted uppercase tracking-wider px-2 pt-1">
                      {mainCatName.replace('-', ' ')}
                    </div>
                    {subs.map(sub => (
                      <button
                        key={sub.id}
                        type="button"
                        onClick={() => {
                          activeOnChange(sub.id);
                          setIsOpen(false);
                        }}
                        className="w-full text-left flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-[hsl(var(--brand-primary))] hover:text-white group transition-colors"
                      >
                        <span className="text-sm capitalize truncate">{sub.name.replace('-', ' ')}</span>
                        {activeValue === sub.id && (
                          <Check size={16} className="text-[hsl(var(--brand-primary))] group-hover:text-white shrink-0 ml-2" />
                        )}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>,
          document.body
        ) : createPortal(
          <div 
            ref={portalRef}
            style={popoverStyle}
            className="bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in duration-150"
          >
            {/* Search */}
            <div className="p-3 border-b border-[hsl(var(--border-color))] flex items-center gap-2 bg-[hsl(var(--bg-primary))] shrink-0">
              <Search size={16} className="text-muted shrink-0" />
              <input 
                type="text"
                placeholder={t('app.search', { defaultValue: 'Søg' }) + "..."}
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full bg-transparent outline-none text-sm"
                autoFocus
              />
              {search && (
                <button 
                  type="button"
                  onClick={() => setSearch('')}
                  className="p-1 text-muted hover:text-[hsl(var(--text-primary))] shrink-0"
                >
                  <X size={16} />
                </button>
              )}
            </div>

            {/* List */}
            <div ref={listRef} className="overflow-y-auto flex-1 p-2 space-y-4">
              {isLoading && <p className="text-center text-sm text-muted p-4">{t('common.loading', 'Henter...')}</p>}
              
              {!isLoading && Object.keys(groupedCategories).length === 0 && (
                <p className="text-center text-sm text-muted p-4">{t('categories.noCategoriesFound', 'Ingen kategorier fundet')}</p>
              )}

              {Object.entries(groupedCategories).map(([mainCatName, subs]) => (
                <div key={mainCatName} className="space-y-1">
                  <div className="text-[10px] font-bold text-muted uppercase tracking-wider px-2 pt-1">
                    {mainCatName.replace('-', ' ')}
                  </div>
                  {subs.map(sub => (
                    <button
                      key={sub.id}
                      type="button"
                      onClick={() => {
                        activeOnChange(sub.id);
                        setIsOpen(false);
                      }}
                      className="w-full text-left flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-[hsl(var(--brand-primary))] hover:text-white group transition-colors"
                    >
                      <span className="text-sm capitalize truncate">{sub.name.replace('-', ' ')}</span>
                      {activeValue === sub.id && (
                        <Check size={14} className="text-[hsl(var(--brand-primary))] group-hover:text-white" />
                      )}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>,
          document.body
        )
      )}
    </div>
  );
}
