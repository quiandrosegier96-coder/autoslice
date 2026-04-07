"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Unit = "mm" | "inch";
const UNITS_KEY = "autoslice_units";

type UnitsCtx = {
  unit: Unit;
  setUnit: (u: Unit) => void;
  convertMm: (mm: number, decimals?: number) => string;
};

const UnitsContext = createContext<UnitsCtx>({
  unit: "mm",
  setUnit: () => {},
  convertMm: (mm) => `${mm} mm`,
});

export function UnitsProvider({ children }: { children: React.ReactNode }) {
  const [unit, setUnitState] = useState<Unit>("mm");

  useEffect(() => {
    const saved = (localStorage.getItem(UNITS_KEY) as Unit) ?? "mm";
    setUnitState(saved);
  }, []);

  const setUnit = useCallback((u: Unit) => {
    localStorage.setItem(UNITS_KEY, u);
    setUnitState(u);
  }, []);

  const convertMm = useCallback(
    (mm: number, decimals = 1): string => {
      if (unit === "inch") return `${(mm / 25.4).toFixed(3)}"`;
      return `${mm.toFixed(decimals)} mm`;
    },
    [unit],
  );

  return (
    <UnitsContext.Provider value={{ unit, setUnit, convertMm }}>
      {children}
    </UnitsContext.Provider>
  );
}

export function useUnits() {
  return useContext(UnitsContext);
}
