import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, ChevronRight, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { format, subMonths, startOfMonth, endOfMonth, parseISO, isValid } from 'date-fns';
import { da, enUS } from 'date-fns/locale';
import { useCategories } from './CategoryPicker';

interface TransactionFiltersProps {
  filterType: string;
  setFilterType: (val: string) => void;
  startDate: string;
  setStartDate: (val: string) => void;
  endDate: string;
  setEndDate: (val: string) => void;
  search: string;
  setSearch: (val: string) => void;
  tags: any[];
  selectedTag: string;
  setSelectedTag: (val: string) => void;
  amountOp?: string;
  setAmountOp: (val: string) => void;
  amountVal?: number;
  setAmountVal: (val?: number) => void;
  categoryId?: string;
  setCategoryId: (val: string) => void;
}

export function TransactionFilters({
  filterType, setFilterType,
  startDate, setStartDate,
  endDate, setEndDate,
  search, setSearch,
  tags, selectedTag, setSelectedTag,
  amountOp, setAmountOp,
  amountVal, setAmountVal,
  categoryId, setCategoryId
}: TransactionFiltersProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === 'da' ? da : enUS;

  const [showTypeDropdown, setShowTypeDropdown] = useState(false);
  const [showPeriodDropdown, setShowPeriodDropdown] = useState(false);
  const [showTagDropdown, setShowTagDropdown] = useState(false);
  const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);
  const [showAmountOpDropdown, setShowAmountOpDropdown] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});
  const [tempSearch, setTempSearch] = useState(search);
  const [tempAmount, setTempAmount] = useState(amountVal ? amountVal.toString() : '');
  const [categorySearch, setCategorySearch] = useState('');

  useEffect(() => {
    setTempSearch(search);
  }, [search]);

  useEffect(() => {
    setTempAmount(amountVal ? amountVal.toString() : '');
  }, [amountVal]);

  const { data: categories = [] } = useCategories();
  
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);

  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filterType !== 'Alle poster') count++;
    if (startDate || endDate) count++;
    if (selectedTag) count++;
    if (categoryId) count++;
    if (amountOp) count++;
    return count;
  }, [filterType, startDate, endDate, selectedTag, categoryId, amountOp]);

  const handleResetFilters = () => {
    setFilterType('Alle poster');
    setStartDate('');
    setEndDate('');
    setSelectedTag('');
    setCategoryId('');
    setAmountOp('');
    setAmountVal(undefined);
    setTempAmount('');
    setTempSearch('');
    setSearch('');
  };
  
  const groupedCategories = useMemo(() => {
    const groups: Record<string, any[]> = {};
    
    let filtered = categories;
    if (categorySearch.trim()) {
      const q = categorySearch.toLowerCase().trim();
      filtered = categories.filter((c: any) => 
        c.name.toLowerCase().includes(q) || 
        c.mainCategoryName.toLowerCase().includes(q)
      );
    }

    filtered.forEach((c: any) => {
      if (!groups[c.mainCategoryName]) groups[c.mainCategoryName] = [];
      groups[c.mainCategoryName].push(c);
    });
    return groups;
  }, [categories, categorySearch]);
  
  const toggleCategoryExpand = (mainCat: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedCategories(prev => ({
      ...prev,
      [mainCat]: !prev[mainCat]
    }));
  };

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = () => {
      setShowTypeDropdown(false);
      setShowPeriodDropdown(false);
      setShowTagDropdown(false);
      setShowCategoryDropdown(false);
      setShowAmountOpDropdown(false);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const types = ['Alle poster', 'Regninger', 'Forbrug', 'Ukategoriseret', 'Ekstraordinær'];

  // Calculate current year and quick links
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 8 }, (_, i) => currentYear - i);

  // Period state for custom dropdown
  const [customStartMonth, setCustomStartMonth] = useState('01');
  const [customStartYear, setCustomStartYear] = useState(currentYear.toString());
  const [customEndMonth, setCustomEndMonth] = useState('12');
  const [customEndYear, setCustomEndYear] = useState(currentYear.toString());

  const applyCustomPeriod = () => {
    const sDate = `${customStartYear}-${customStartMonth}-01`;
    // Get last day of end month
    const eDateObj = new Date(parseInt(customEndYear), parseInt(customEndMonth), 0);
    const eDate = format(eDateObj, 'yyyy-MM-dd');
    setStartDate(sDate);
    setEndDate(eDate);
    setShowPeriodDropdown(false);
  };

  const getPeriodLabel = () => {
    if (!startDate && !endDate) return 'hele perioden';
    
    // Check if it's "Denne måned"
    const thisMonthStart = format(startOfMonth(new Date()), 'yyyy-MM-dd');
    const thisMonthEnd = format(endOfMonth(new Date()), 'yyyy-MM-dd');
    if (startDate === thisMonthStart && endDate === thisMonthEnd) return 'denne måned';

    // Check if it's a specific year
    for (const y of years) {
      if (startDate === `${y}-01-01` && endDate === `${y}-12-31`) return y.toString();
    }

    return 'valgt periode';
  };

  return (
    <div className="bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-color))] rounded-lg p-3 shadow-sm relative z-20">
      
      {/* Mobile view search and filter trigger */}
      <div className="md:hidden flex items-center gap-2 w-full">
        <div className="relative flex-grow">
          <input 
            type="text" 
            placeholder={t('app.search') + "..."}
            value={tempSearch}
            onChange={(e) => setTempSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                setSearch(tempSearch);
              }
            }}
            className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg py-2 px-3 pl-8 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
        </div>
        <button
          onClick={() => setIsMobileDrawerOpen(true)}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-semibold transition-colors shrink-0 ${
            activeFiltersCount > 0
              ? 'bg-[hsl(var(--brand-primary))] text-white border-[hsl(var(--brand-primary))]'
              : 'bg-[hsl(var(--bg-secondary))] border-[hsl(var(--border-color))] text-[hsl(var(--text-primary))]'
          }`}
        >
          <span>Filtrér</span>
          {activeFiltersCount > 0 && (
            <span className="flex items-center justify-center bg-white text-[hsl(var(--brand-primary))] text-[10px] font-bold rounded-full w-4 h-4">
              {activeFiltersCount}
            </span>
          )}
        </button>
      </div>

      {/* Desktop view filters (hidden on mobile) */}
      <div className="hidden md:flex flex-wrap items-center gap-3 text-sm w-full">
        
        <div className="flex items-center gap-2">
          <span className="text-muted">Viser</span>
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button 
              className="flex items-center gap-1 font-medium bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] px-3 py-1.5 rounded-md hover:border-primary"
              onClick={() => { setShowTypeDropdown(!showTypeDropdown); setShowPeriodDropdown(false); setShowTagDropdown(false); setShowAmountOpDropdown(false); }}
            >
              {filterType || 'Alle poster'} <ChevronDown size={14} />
            </button>
            
            {showTypeDropdown && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-md shadow-lg py-1 z-30 animate-fade-in">
                {types.map(t => (
                  <button 
                    key={t}
                    className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors"
                    onClick={() => { setFilterType(t); setShowTypeDropdown(false); }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-muted">fra</span>
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button 
              className="flex items-center gap-1 font-medium bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] px-3 py-1.5 rounded-md hover:border-primary"
              onClick={() => { setShowPeriodDropdown(!showPeriodDropdown); setShowTypeDropdown(false); setShowTagDropdown(false); setShowAmountOpDropdown(false); }}
            >
              {getPeriodLabel()} <ChevronDown size={14} />
            </button>

            {showPeriodDropdown && (
              <div className="absolute top-full left-0 mt-1 w-80 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-md shadow-lg p-4 z-30 animate-fade-in">
                <h3 className="text-lg text-primary mb-4 font-light">Måneder</h3>
                
                <div className="flex items-center gap-2 mb-4">
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] rounded p-1" value={customStartMonth} onChange={e => setCustomStartMonth(e.target.value)}>
                    {Array.from({length: 12}, (_, i) => {
                      const m = (i + 1).toString().padStart(2, '0');
                      const name = format(new Date(2000, i, 1), 'MMMM', { locale });
                      return <option key={m} value={m}>{name}</option>
                    })}
                  </select>
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] rounded p-1" value={customStartYear} onChange={e => setCustomStartYear(e.target.value)}>
                    {years.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <span className="text-muted">til</span>
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] rounded p-1" value={customEndMonth} onChange={e => setCustomEndMonth(e.target.value)}>
                    {Array.from({length: 12}, (_, i) => {
                      const m = (i + 1).toString().padStart(2, '0');
                      const name = format(new Date(2000, i, 1), 'MMMM', { locale });
                      return <option key={m} value={m}>{name}</option>
                    })}
                  </select>
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] rounded p-1" value={customEndYear} onChange={e => setCustomEndYear(e.target.value)}>
                    {years.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
                <button onClick={applyCustomPeriod} className="w-full bg-primary text-primary-foreground py-1 rounded mb-4 hover:opacity-90">Anvend</button>

                <div className="flex flex-wrap gap-x-4 gap-y-2 text-primary">
                  <button onClick={() => { setStartDate(''); setEndDate(''); setShowPeriodDropdown(false); }} className="hover:underline">Hele perioden</button>
                  <button onClick={() => {
                    setStartDate(format(startOfMonth(new Date()), 'yyyy-MM-dd'));
                    setEndDate(format(endOfMonth(new Date()), 'yyyy-MM-dd'));
                    setShowPeriodDropdown(false);
                  }} className="hover:underline">Denne måned</button>
                  {years.map(y => (
                    <button key={y} onClick={() => {
                      setStartDate(`${y}-01-01`);
                      setEndDate(`${y}-12-31`);
                      setShowPeriodDropdown(false);
                    }} className="hover:underline">{y}</button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-muted">med tag</span>
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button 
              className="flex items-center gap-1 font-medium bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] px-3 py-1.5 rounded-md hover:border-primary"
              onClick={() => { setShowTagDropdown(!showTagDropdown); setShowTypeDropdown(false); setShowPeriodDropdown(false); setShowAmountOpDropdown(false); }}
            >
              {selectedTag ? `#${selectedTag}` : 'Alle tags'} <ChevronDown size={14} />
            </button>
            
            {showTagDropdown && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-md shadow-lg py-1 z-30 animate-fade-in max-h-60 overflow-y-auto">
                <button 
                  className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors"
                  onClick={() => { setSelectedTag(''); setShowTagDropdown(false); }}
                >
                  Alle tags
                </button>
                {tags?.map(t => (
                  <button 
                    key={t.id}
                    className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors"
                    onClick={() => { setSelectedTag(t.name); setShowTagDropdown(false); }}
                  >
                    #{t.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-muted">med kategori</span>
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button 
              className="flex items-center gap-1 font-medium bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] px-3 py-1.5 rounded-md hover:border-primary max-w-[200px] truncate"
              onClick={() => { setShowCategoryDropdown(!showCategoryDropdown); setShowTagDropdown(false); setShowTypeDropdown(false); setShowPeriodDropdown(false); setShowAmountOpDropdown(false); }}
            >
              {categoryId ? categories.find((c: any) => c.id === categoryId)?.name.replace('-', ' ') || 'Alle kategorier' : 'Alle kategorier'} <ChevronDown size={14} className="shrink-0" />
            </button>
            
            {showCategoryDropdown && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-md shadow-lg py-1 z-30 animate-fade-in flex flex-col max-h-80">
                
                <div className="p-2 border-b border-[hsl(var(--border-color))] flex items-center gap-2 sticky top-0 bg-[hsl(var(--bg-primary))] z-10">
                  <Search size={16} className="text-muted shrink-0" />
                  <input 
                    type="text" 
                    placeholder={t('app.search') + "..."}
                    value={categorySearch}
                    onChange={e => setCategorySearch(e.target.value)}
                    className="w-full bg-transparent outline-none text-sm"
                    autoFocus
                    onClick={e => e.stopPropagation()}
                  />
                </div>

                <div className="overflow-y-auto flex-1">
                  <button 
                    className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors font-medium border-b border-[hsl(var(--border-color))]"
                    onClick={() => { setCategoryId(''); setShowCategoryDropdown(false); setCategorySearch(''); }}
                  >
                    Alle kategorier
                  </button>
                  {Object.entries(groupedCategories).length === 0 && (
                    <p className="text-center text-sm text-muted p-4">Ingen kategorier fundet</p>
                  )}
                  {Object.entries(groupedCategories).map(([mainCat, subCats]) => (
                  <div key={mainCat} className="flex flex-col border-b border-[hsl(var(--border-color))] last:border-0">
                    <div className="flex items-center w-full hover:bg-primary hover:text-primary-foreground transition-colors">
                      <button 
                        className="flex-1 text-left px-4 py-2 font-medium text-sm capitalize"
                        onClick={() => { setCategoryId(mainCat.toLowerCase()); setShowCategoryDropdown(false); }}
                      >
                        {mainCat}
                      </button>
                      <button 
                        className="p-2 mr-1 hover:bg-black/10 dark:hover:bg-white/10 rounded-md transition-colors"
                        onClick={(e) => toggleCategoryExpand(mainCat, e)}
                      >
                        {expandedCategories[mainCat] ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </button>
                    </div>
                    {expandedCategories[mainCat] && (
                      <div className="flex flex-col bg-[hsl(var(--bg-tertiary))] py-1">
                        {subCats.map((c: any) => (
                          <button 
                            key={c.id}
                            className="w-full text-left px-4 py-2 pl-8 hover:bg-primary hover:text-primary-foreground transition-colors text-sm capitalize"
                            onClick={() => { setCategoryId(c.id); setShowCategoryDropdown(false); }}
                          >
                            {c.name.replace('-', ' ')}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-muted">med beløb</span>
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button 
              className="flex items-center gap-1 font-medium bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] px-3 py-1.5 rounded-md hover:border-primary"
              onClick={() => { setShowAmountOpDropdown(!showAmountOpDropdown); setShowTagDropdown(false); setShowTypeDropdown(false); setShowPeriodDropdown(false); }}
            >
              {amountOp === 'lt' ? 'mindre end' : amountOp === 'gt' ? 'større end' : amountOp === 'eq' ? 'lig med' : 'alle beløb'} <ChevronDown size={14} />
            </button>
            
            {showAmountOpDropdown && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-color))] rounded-md shadow-lg py-1 z-30 animate-fade-in">
                <button 
                  className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors"
                  onClick={() => { setAmountOp(''); setShowAmountOpDropdown(false); }}
                >
                  alle beløb
                </button>
                <button 
                  className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors"
                  onClick={() => { setAmountOp('lt'); setShowAmountOpDropdown(false); }}
                >
                  mindre end
                </button>
                <button 
                  className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors"
                  onClick={() => { setAmountOp('gt'); setShowAmountOpDropdown(false); }}
                >
                  større end
                </button>
                <button 
                  className="w-full text-left px-4 py-2 hover:bg-primary hover:text-primary-foreground transition-colors"
                  onClick={() => { setAmountOp('eq'); setShowAmountOpDropdown(false); }}
                >
                  lig med
                </button>
              </div>
            )}
          </div>
          
          {amountOp && (
            <div className="relative w-24">
              <input 
                type="number" 
                placeholder="beløb"
                value={tempAmount}
                onChange={(e) => setTempAmount(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const val = parseFloat(tempAmount);
                    setAmountVal(isNaN(val) ? undefined : val);
                  }
                }}
                onBlur={() => {
                  const val = parseFloat(tempAmount);
                  setAmountVal(isNaN(val) ? undefined : val);
                }}
                className="w-full bg-transparent border border-[hsl(var(--border-color))] rounded-md py-1.5 px-3 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <span className="text-muted">med teksten</span>
          <div className="relative flex-1">
            <input 
              type="text" 
              placeholder="Skriv søgeord og tryk enter"
              value={tempSearch}
              onChange={(e) => setTempSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setSearch(tempSearch);
                }
              }}
              className="w-full bg-transparent border border-[hsl(var(--border-color))] rounded-md py-1.5 px-3 pl-8 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          </div>
        </div>

      </div>

      {/* Mobile Drawer (Bottom Sheet) */}
      {isMobileDrawerOpen && (
        <>
          <div className="fixed inset-0 bg-black/60 z-[90] animate-fade-in" onClick={() => setIsMobileDrawerOpen(false)} />
          <div className="fixed bottom-0 left-0 right-0 max-h-[85vh] bg-[hsl(var(--bg-secondary))] border-t border-[hsl(var(--border-color))] rounded-t-2xl shadow-2xl z-[100] overflow-y-auto flex flex-col animate-slide-in-up pb-safe text-sm">
            
            {/* Header */}
            <div className="p-4 border-b border-[hsl(var(--border-color))] flex justify-between items-center bg-[hsl(var(--bg-secondary))] rounded-t-2xl sticky top-0 z-10">
              <h3 className="font-semibold text-base">Filtrér transaktioner</h3>
              <button 
                onClick={() => setIsMobileDrawerOpen(false)} 
                className="text-muted hover:text-[hsl(var(--text-primary))] font-medium"
              >
                Luk
              </button>
            </div>
            
            {/* Scrollable Filters */}
            <div className="p-5 flex flex-col gap-6 overflow-y-auto flex-grow bg-[hsl(var(--bg-primary))]">
              {/* Viser (Filter Type) */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-muted uppercase tracking-wider">Vis</label>
                <select 
                  value={filterType} 
                  onChange={e => setFilterType(e.target.value)}
                  className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 outline-none focus:border-primary text-sm"
                >
                  {types.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>

              {/* Periode */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-muted uppercase tracking-wider">Periode</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  <button 
                    onClick={() => { setStartDate(''); setEndDate(''); }}
                    className={`px-3 py-1.5 rounded-full text-xs border font-medium ${!startDate && !endDate ? 'bg-[hsl(var(--brand-primary))] text-white border-[hsl(var(--brand-primary))]' : 'bg-[hsl(var(--bg-secondary))] border-[hsl(var(--border-color))] text-muted'}`}
                  >
                    Hele perioden
                  </button>
                  <button 
                    onClick={() => {
                      setStartDate(format(startOfMonth(new Date()), 'yyyy-MM-dd'));
                      setEndDate(format(endOfMonth(new Date()), 'yyyy-MM-dd'));
                    }}
                    className={`px-3 py-1.5 rounded-full text-xs border font-medium ${startDate === format(startOfMonth(new Date()), 'yyyy-MM-dd') ? 'bg-[hsl(var(--brand-primary))] text-white border-[hsl(var(--brand-primary))]' : 'bg-[hsl(var(--bg-secondary))] border-[hsl(var(--border-color))] text-muted'}`}
                  >
                    Denne måned
                  </button>
                  {years.slice(0, 3).map(y => (
                    <button 
                      key={y} 
                      onClick={() => { setStartDate(`${y}-01-01`); setEndDate(`${y}-12-31`); }}
                      className={`px-3 py-1.5 rounded-full text-xs border font-medium ${startDate === `${y}-01-01` && endDate === `${y}-12-31` ? 'bg-[hsl(var(--brand-primary))] text-white border-[hsl(var(--brand-primary))]' : 'bg-[hsl(var(--bg-secondary))] border-[hsl(var(--border-color))] text-muted'}`}
                    >
                      {y}
                    </button>
                  ))}
                </div>
                
                {/* Custom Month Selector */}
                <div className="flex items-center gap-1 bg-[hsl(var(--bg-secondary))] p-2 rounded-lg border border-[hsl(var(--border-color))]">
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] rounded p-1.5 flex-1 min-w-0" value={customStartMonth} onChange={e => setCustomStartMonth(e.target.value)}>
                    {Array.from({length: 12}, (_, i) => {
                      const m = (i + 1).toString().padStart(2, '0');
                      const name = format(new Date(2000, i, 1), 'MMMM', { locale });
                      return <option key={m} value={m}>{name}</option>
                    })}
                  </select>
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] rounded p-1.5 flex-1 min-w-0" value={customStartYear} onChange={e => setCustomStartYear(e.target.value)}>
                    {years.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <span className="text-muted px-1 text-xs">til</span>
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] rounded p-1.5 flex-1 min-w-0" value={customEndMonth} onChange={e => setCustomEndMonth(e.target.value)}>
                    {Array.from({length: 12}, (_, i) => {
                      const m = (i + 1).toString().padStart(2, '0');
                      const name = format(new Date(2000, i, 1), 'MMMM', { locale });
                      return <option key={m} value={m}>{name}</option>
                    })}
                  </select>
                  <select className="border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] rounded p-1.5 flex-1 min-w-0" value={customEndYear} onChange={e => setCustomEndYear(e.target.value)}>
                    {years.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <button onClick={applyCustomPeriod} className="bg-primary text-primary-foreground px-3 py-1.5 rounded ml-2 hover:opacity-90 shrink-0 font-medium text-xs font-semibold">Anvend</button>
                </div>
              </div>

              {/* Tag */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-muted uppercase tracking-wider">Tag</label>
                <select 
                  value={selectedTag} 
                  onChange={e => setSelectedTag(e.target.value)}
                  className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 outline-none focus:border-primary text-sm"
                >
                  <option value="">Alle tags</option>
                  {tags?.map(t => <option key={t.id} value={t.name}>#{t.name}</option>)}
                </select>
              </div>

              {/* Kategori */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-muted uppercase tracking-wider">Kategori</label>
                <select 
                  value={categoryId} 
                  onChange={e => setCategoryId(e.target.value)}
                  className="w-full bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 outline-none focus:border-primary text-sm capitalize"
                >
                  <option value="">Alle kategorier</option>
                  {Object.entries(groupedCategories).map(([mainCat, subCats]) => (
                    <optgroup key={mainCat} label={mainCat.toUpperCase()}>
                      <option value={mainCat.toLowerCase()}>{mainCat} (Alle)</option>
                      {subCats.map((c: any) => (
                        <option key={c.id} value={c.id}>
                          &nbsp;&nbsp;{c.name.replace('-', ' ')}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              {/* Beløb */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-muted uppercase tracking-wider">Beløb</label>
                <div className="flex gap-2">
                  <select 
                    value={amountOp} 
                    onChange={e => setAmountOp(e.target.value)}
                    className="flex-1 bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 outline-none focus:border-primary text-sm"
                  >
                    <option value="">Alle beløb</option>
                    <option value="lt">mindre end</option>
                    <option value="gt">større end</option>
                    <option value="eq">lig med</option>
                  </select>
                  {amountOp && (
                    <input 
                      type="number" 
                      placeholder="beløb"
                      value={tempAmount}
                      onChange={(e) => {
                        setTempAmount(e.target.value);
                        const val = parseFloat(e.target.value);
                        setAmountVal(isNaN(val) ? undefined : val);
                      }}
                      className="w-28 bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] rounded-lg p-3 outline-none focus:border-primary text-sm"
                    />
                  )}
                </div>
              </div>
            </div>
            
            {/* Footer */}
            <div className="p-4 border-t border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] flex gap-3 sticky bottom-0 z-10">
              <button 
                onClick={handleResetFilters}
                className="flex-1 py-3 rounded-lg border border-[hsl(var(--border-color))] text-sm font-medium hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
              >
                Nulstil
              </button>
              <button 
                onClick={() => setIsMobileDrawerOpen(false)}
                className="flex-1 py-3 rounded-lg bg-[hsl(var(--brand-primary))] text-white text-sm font-medium hover:opacity-95 transition-colors"
              >
                Vis resultater
              </button>
            </div>
          </div>
        </>
      )}

    </div>
  );
}
