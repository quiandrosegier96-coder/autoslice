"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { type Lang, type TKey, type Translations, LANG_KEY, getSavedLang, translations } from "@/lib/i18n";

type LangCtx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TKey) => string;
};

const LangContext = createContext<LangCtx>({
  lang: "nl",
  setLang: () => {},
  t: (k) => k,
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    setLangState(getSavedLang());
  }, []);

  const setLang = useCallback((l: Lang) => {
    localStorage.setItem(LANG_KEY, l);
    setLangState(l);
  }, []);

  const t = useCallback(
    (key: TKey): string => {
      const dict = translations[lang] as Translations;
      return dict[key] ?? (translations.en as Translations)[key] ?? key;
    },
    [lang],
  );

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  return useContext(LangContext);
}
