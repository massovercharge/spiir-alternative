import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Locale = "da" | "en";
export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

const messages = {
    da: {
        "app.brand": "Spiir alternative",
        "app.loading": "Indlæser...",
        "auth.redirecting": "Sender dig videre til login...",
        "auth.handlingCallback": "Logger dig ind...",
        "auth.error": "Fejl",
        "nav.aria": "Hovednavigation",
        "nav.bank": "Bank",
        "nav.overview": "Overblik",
        "nav.receipts": "Kvitteringer",
        "settings.language": "Sprog",
        "settings.language.da": "Dansk",
        "settings.language.en": "English",
        "settings.theme": "Tema",
        "settings.theme.system": "System",
        "settings.theme.light": "Lys",
        "settings.theme.dark": "Mørk"
    },
    en: {
        "app.brand": "Spiir alternative",
        "app.loading": "Loading...",
        "auth.redirecting": "Redirecting to login...",
        "auth.handlingCallback": "Handling authentication...",
        "auth.error": "Error",
        "nav.aria": "Main navigation",
        "nav.bank": "Bank ledger",
        "nav.overview": "Overview",
        "nav.receipts": "Receipts",
        "settings.language": "Language",
        "settings.language.da": "Dansk",
        "settings.language.en": "English",
        "settings.theme": "Theme",
        "settings.theme.system": "System",
        "settings.theme.light": "Light",
        "settings.theme.dark": "Dark"
    }
} as const;

export type MessageKey = keyof typeof messages.da;

type AppPreferencesContextValue = {
    locale: Locale;
    setLocale: (locale: Locale) => void;
    themePreference: ThemePreference;
    setThemePreference: (theme: ThemePreference) => void;
    resolvedTheme: ResolvedTheme;
    t: (key: MessageKey) => string;
};

const AppPreferencesContext = createContext<AppPreferencesContextValue | null>(null);

const LOCALE_STORAGE_KEY = "spiir_locale";
const THEME_STORAGE_KEY = "spiir_theme";

function getStoredLocale(): Locale {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored === "da" || stored === "en") {
        return stored;
    }
    return window.navigator.language.toLowerCase().startsWith("da") ? "da" : "en";
}

function getStoredThemePreference(): ThemePreference {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

function getSystemTheme(): ResolvedTheme {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function AppPreferencesProvider({ children }: { children: ReactNode }) {
    const [locale, setLocaleState] = useState<Locale>(() => getStoredLocale());
    const [themePreference, setThemePreferenceState] = useState<ThemePreference>(() => getStoredThemePreference());
    const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() => getSystemTheme());
    const resolvedTheme = themePreference === "system" ? systemTheme : themePreference;

    useEffect(() => {
        const media = window.matchMedia?.("(prefers-color-scheme: dark)");
        if (!media) {
            return undefined;
        }
        const update = () => setSystemTheme(media.matches ? "dark" : "light");
        update();
        media.addEventListener("change", update);
        return () => media.removeEventListener("change", update);
    }, []);

    useEffect(() => {
        document.documentElement.lang = locale;
        document.documentElement.dataset.locale = locale;
        window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    }, [locale]);

    useEffect(() => {
        document.documentElement.dataset.theme = resolvedTheme;
        document.documentElement.dataset.themePreference = themePreference;
        window.localStorage.setItem(THEME_STORAGE_KEY, themePreference);
    }, [resolvedTheme, themePreference]);

    const value = useMemo<AppPreferencesContextValue>(() => ({
        locale,
        setLocale: setLocaleState,
        themePreference,
        setThemePreference: setThemePreferenceState,
        resolvedTheme,
        t: (key) => messages[locale][key]
    }), [locale, resolvedTheme, themePreference]);

    return <AppPreferencesContext.Provider value={value}>{children}</AppPreferencesContext.Provider>;
}

export function useAppPreferences(): AppPreferencesContextValue {
    const value = useContext(AppPreferencesContext);
    if (!value) {
        throw new Error("useAppPreferences must be used inside AppPreferencesProvider");
    }
    return value;
}
