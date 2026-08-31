import React, { createContext, useContext, useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { setHouseholdId, useHouseholds } from '../api/client';

interface HouseholdContextType {
  activeHouseholdId: string | null;
  setActiveHousehold: (id: string) => void;
  isLoadingHouseholds: boolean;
  households: any[];
  deletedHouseholds: any[];
}

const HouseholdContext = createContext<HouseholdContextType | undefined>(undefined);

export function HouseholdProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const { data: households, isLoading } = useHouseholds();
  const [activeHouseholdId, setActiveHouseholdId] = useState<string | null>(() => {
    return localStorage.getItem('peng_household_id');
  });

  const activeHouseholds = households?.filter((h: any) => !h.deleted_at) || [];
  const deletedHouseholds = households?.filter((h: any) => !!h.deleted_at) || [];

  // Ensure an active household is set if data is available
  useEffect(() => {
    if (activeHouseholds.length > 0) {
      if (!activeHouseholdId || !activeHouseholds.find((h: any) => h.id === activeHouseholdId)) {
        const firstId = activeHouseholds[0].id;
        setActiveHouseholdId(firstId);
        localStorage.setItem('peng_household_id', firstId);
        setHouseholdId(firstId);
        queryClient.invalidateQueries();
      } else {
        setHouseholdId(activeHouseholdId);
      }
    } else if (!isLoading && activeHouseholdId) {
      setActiveHouseholdId(null);
      localStorage.removeItem('peng_household_id');
      setHouseholdId('');
    }
  }, [activeHouseholds, activeHouseholdId, isLoading, queryClient]);

  const setActiveHousehold = (id: string) => {
    setActiveHouseholdId(id);
    localStorage.setItem('peng_household_id', id);
    setHouseholdId(id);
    // Reset all domain queries to prevent data leakage and stale data flashing
    queryClient.resetQueries({
      predicate: (query) => query.queryKey[0] !== 'households',
    });
    // Ensure the households list is fresh
    queryClient.invalidateQueries({ queryKey: ['households'] });
  };

  return (
    <HouseholdContext.Provider
      value={{
        activeHouseholdId,
        setActiveHousehold,
        isLoadingHouseholds: isLoading,
        households: activeHouseholds,
        deletedHouseholds,
      }}
    >
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
