import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { LogtoProvider, LogtoConfig } from '@logto/react';
import { Toaster } from 'sonner';

import './i18n/config'; // Initialize i18n
import './index.css';

import { ThemeProvider } from './theme/ThemeProvider';
import AppLayout from './components/layout/AppLayout';

const logtoConfig: LogtoConfig = {
  endpoint: import.meta.env.VITE_LOGTO_ENDPOINT || 'https://auth.seame.click/',
  appId: import.meta.env.VITE_LOGTO_APP_ID || '',
  resources: [import.meta.env.VITE_LOGTO_API_RESOURCE || 'https://peng.seame.click/api'],
  scopes: ['read:transactions', 'write:transactions', 'email', 'profile'],
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LogtoProvider config={logtoConfig}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <BrowserRouter>
            <AppLayout />
            <Toaster position="bottom-right" theme="system" richColors />
          </BrowserRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </LogtoProvider>
  </React.StrictMode>
);
