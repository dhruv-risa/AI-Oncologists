import React, { createContext, useContext, useState, useEffect } from 'react';

export type Hospital = 'demo' | 'astera';

interface HospitalContextType {
  selectedHospital: Hospital;
  setSelectedHospital: (hospital: Hospital) => void;
  hospitalDisplayName: string;
}

const HospitalContext = createContext<HospitalContextType | undefined>(undefined);

export function HospitalProvider({ children }: { children: React.ReactNode }) {
  // Load from localStorage or default to 'demo'
  const [selectedHospital, setSelectedHospitalState] = useState<Hospital>(() => {
    const saved = localStorage.getItem('selectedHospital');
    return (saved === 'astera' ? 'astera' : 'demo') as Hospital;
  });

  // Save to localStorage when changed
  const setSelectedHospital = (hospital: Hospital) => {
    setSelectedHospitalState(hospital);
    localStorage.setItem('selectedHospital', hospital);
  };

  const hospitalDisplayName = selectedHospital === 'demo' ? 'Demo Hospital' : 'Astera';

  return (
    <HospitalContext.Provider value={{ selectedHospital, setSelectedHospital, hospitalDisplayName }}>
      {children}
    </HospitalContext.Provider>
  );
}

export function useHospital() {
  const context = useContext(HospitalContext);
  if (context === undefined) {
    throw new Error('useHospital must be used within a HospitalProvider');
  }
  return context;
}
