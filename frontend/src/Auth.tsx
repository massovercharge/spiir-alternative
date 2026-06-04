import { LogtoProvider, LogtoConfig, useLogto, useHandleSignInCallback } from '@logto/react';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import React, { useEffect } from 'react';
import { setAccessToken } from './api';
import { useAppPreferences } from './appPreferences';
import ReferenceApp from './ReferenceApp';

const config: LogtoConfig = {
  endpoint: import.meta.env.VITE_LOGTO_ENDPOINT || 'https://<your-logto-tenant>.logto.app/',
  appId: import.meta.env.VITE_LOGTO_APP_ID || '<your-app-id>',
  resources: [import.meta.env.VITE_LOGTO_API_RESOURCE || 'https://spiir.seame.click/api']
};

const AuthCheck: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, error, signIn, getAccessToken } = useLogto();
  const { t } = useAppPreferences();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      signIn(window.location.origin + '/callback');
    }
  }, [isLoading, isAuthenticated, signIn]);

  useEffect(() => {
    if (isAuthenticated) {
      getAccessToken(config.resources?.[0]).then((token) => {
        if (token) {
          setAccessToken(token);
        }
      });
    }
  }, [isAuthenticated, getAccessToken]);

  if (isLoading || !isAuthenticated) {
    return <div className="auth-status">{t("auth.redirecting")}</div>;
  }
  
  if (error) {
    return <div className="auth-status">{t("auth.error")}: {error.message}</div>;
  }

  return <>{children}</>;
};

const Callback: React.FC = () => {
  const { t } = useAppPreferences();
  const { isLoading, error } = useHandleSignInCallback(() => {
    navigate('/');
  });
  const navigate = useNavigate();

  if (isLoading) {
    return <div className="auth-status">{t("auth.handlingCallback")}</div>;
  }
  
  if (error) {
    return <div className="auth-status">{t("auth.error")}: {error.message}</div>;
  }
  
  return null;
};

export const AuthApp: React.FC = () => {
  return (
    <LogtoProvider config={config}>
      <BrowserRouter>
        <Routes>
          <Route path="/callback" element={<Callback />} />
          <Route path="*" element={<AuthCheck><ReferenceApp /></AuthCheck>} />
        </Routes>
      </BrowserRouter>
    </LogtoProvider>
  );
};
