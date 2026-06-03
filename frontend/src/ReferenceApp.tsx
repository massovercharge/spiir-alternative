import { Suspense, lazy, useState } from "react";

const KvitteringerDashboard = lazy(() => import("./KvitteringerDashboard"));
const BankDashboard = lazy(() => import("./BankDashboard"));
const SpiirDashboard = lazy(() => import("./SpiirDashboard"));

type Tab = "bank" | "spiir" | "kvitteringer";

export default function ReferenceApp() {
    const [tab, setTab] = useState<Tab>("bank");

    return <main className={tab === "bank" ? "app-mode-bank" : "app-shell app-shell-wide"}>
        <nav className="top-nav-panel" aria-label="Reference navigation">
            <div className="top-nav-start">
                <strong>Spiir alternative</strong>
            </div>
            <div className="top-nav-controls">
                <button type="button" className={tab === "bank" ? "nav-pill active" : "nav-pill"} onClick={() => setTab("bank")}>Bank ledger</button>
                <button type="button" className={tab === "spiir" ? "nav-pill active" : "nav-pill"} onClick={() => setTab("spiir")}>Overview</button>
                <button type="button" className={tab === "kvitteringer" ? "nav-pill active" : "nav-pill"} onClick={() => setTab("kvitteringer")}>Receipts</button>
            </div>
            <div />
        </nav>
        <Suspense fallback={<div className="panel">Loading...</div>}>
            {tab === "bank" ? <BankDashboard active={true} source="local-ledger" /> : null}
            {tab === "spiir" ? <SpiirDashboard active={true} /> : null}
            {tab === "kvitteringer" ? <KvitteringerDashboard active={true} /> : null}
        </Suspense>
    </main>;
}
