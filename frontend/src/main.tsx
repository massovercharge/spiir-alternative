import React from "react";
import ReactDOM from "react-dom/client";

import { AppPreferencesProvider } from "./appPreferences";
import { AuthApp } from "./Auth";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <AppPreferencesProvider>
            <AuthApp />
        </AppPreferencesProvider>
    </React.StrictMode>
);
