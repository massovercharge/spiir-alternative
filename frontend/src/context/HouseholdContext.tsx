import React, { createContext, useContext, useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { setHouseholdId, useHouseholds } from '../api/client';

interface HouseholdContextType {
  activeHouseholdId: string | null;
  setActiveHousehold: (id: string) => void;
  isLoadingHouseholds: boolean;
  households: any[];
}

const HouseholdContext = createContext<HouseholdContextType | undefined>(undefined);

export function HouseholdProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const { data: households, isLoading } = useHouseholds();
  const [activeHouseholdId, setActiveHouseholdId] = useState<string | null>(() => {
    return localStorage.getItem('peng_household_id');
  });

  // Ensure an active household is set if data is available
  useEffect(() => {
    if (households && households.length > 0) {
      if (!activeHouseholdId || !households.find((h: any) => h.id === activeHouseholdId)) {
        const firstId = households[0].id;
        setActiveHouseholdId(firstId);
        localStorage.setItem('peng_household_id', firstId);
        setHouseholdId(firstId);
        queryClient.invalidateQueries();
      } else {
        setHouseholdId(activeHouseholdId);
      }
    }
  }, [households, activeHouseholdId, queryClient]);

  const setActiveHousehold = (id: string) => {
    setActiveHouseholdId(id);
    localStorage.setItem('peng_household_id', id);
    setHouseholdId(id);
    // Invalidate domain queries without wiping the households list
    queryClient.invalidateQueries({ queryKey: ['households'] });
    queryClient.invalidateQueries({ queryKey: ['transactions'] });
    queryClient.invalidateQueries({ queryKey: ['accounts'] });
    queryClient.invalidateQueries({ queryKey: ['budgets'] });
    queryClient.invalidateQueries({ queryKey: ['insights'] });
    queryClient.invalidateQueries({ queryKey: ['categories'] });
  };

  return (
    <HouseholdContext.Provider value={{ activeHouseholdId, setActiveHousehold, isLoadingHouseholds: isLoading, households: households || [] }}>
      {children}
    </HouseholdContext.Provider>
  );
}

export function useHousehold() {
  const context = useContext(HouseholdContext);
  if (context === undefined) {
    throw new Error('useHousehold must be used within a HouseholdProvider');
  }
  return context;
}
