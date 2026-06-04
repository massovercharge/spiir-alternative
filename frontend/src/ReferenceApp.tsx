import { Suspense, lazy, useState } from "react";

import { useAppPreferences, type Locale, type ThemePreference } from "./appPreferences";

const KvitteringerDashboard = lazy(() => import("./KvitteringerDashboard"));
const BankDashboard = lazy(() => import("./BankDashboard"));
const SpiirDashboard = lazy(() => import("./SpiirDashboard"));

type Tab = "bank" | "spiir" | "kvitteringer";

export default function ReferenceApp() {
    const [tab, setTab] = useState<Tab>("bank");
    const { locale, setLocale, themePreference, setThemePreference, t } = useAppPreferences();

    return <main className={tab === "bank" ? "app-mode-bank" : "app-shell app-shell-wide"}>
        <nav className="top-nav-panel" aria-label={t("nav.aria")}>
            <div className="top-nav-start">
                <strong>{t("app.brand")}</strong>
            </div>
            <div className="top-nav-controls">
                <button type="button" className={tab === "bank" ? "nav-pill active" : "nav-pill"} onClick={() => setTab("bank")}>{t("nav.bank")}</button>
                <button type="button" className={tab === "spiir" ? "nav-pill active" : "nav-pill"} onClick={() => setTab("spiir")}>{t("nav.overview")}</button>
                <button type="button" className={tab === "kvitteringer" ? "nav-pill active" : "nav-pill"} onClick={() => setTab("kvitteringer")}>{t("nav.receipts")}</button>
            </div>
            <div className="top-nav-actions app-settings-controls">
                <label className="app-setting-select">
                    <span>{t("settings.language")}</span>
                    <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
                        <option value="da">{t("settings.language.da")}</option>
                        <option value="en">{t("settings.language.en")}</option>
                    </select>
                </label>
                <label className="app-setting-select">
                    <span>{t("settings.theme")}</span>
                    <select value={themePreference} onChange={(event) => setThemePreference(event.target.value as ThemePreference)}>
                        <option value="system">{t("settings.theme.system")}</option>
                        <option value="light">{t("settings.theme.light")}</option>
                        <option value="dark">{t("settings.theme.dark")}</option>
                    </select>
                </label>
            </div>
        </nav>
        <Suspense fallback={<div className="panel">{t("app.loading")}</div>}>
            {tab === "bank" ? <BankDashboard active={true} source="local-ledger" /> : null}
            {tab === "spiir" ? <SpiirDashboard active={true} /> : null}
            {tab === "kvitteringer" ? <KvitteringerDashboard active={true} /> : null}
        </Suspense>
    </main>;
}
