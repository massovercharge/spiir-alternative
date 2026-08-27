import React from 'react';
import { Routes, Route, Navigate, NavLink } from 'react-router-dom';
import { LayoutDashboard, Receipt, PieChart, Settings, Wallet, Sun, Moon, LogIn, LogOut, Loader2 } from 'lucide-react';
import { useTheme } from '../../theme/ThemeProvider';
import { useTranslation } from 'react-i18next';
import { useLogto } from '@logto/react';

import { Suspense, lazy } from 'react';

const DashboardPage = lazy(() => import('../../pages/DashboardPage'));
const TransactionsPage = lazy(() => import('../../pages/TransactionsPage'));
const BudgetsPage = lazy(() => import('../../pages/BudgetsPage'));
const AccountsPage = lazy(() => import('../../pages/AccountsPage'));
const SettingsPage = lazy(() => import('../../pages/SettingsPage'));
const InsightsPage = lazy(() => import('../../pages/InsightsPage'));
const Callback = lazy(() => import('../../pages/Callback'));
const ReleaseNotesPage = lazy(() => import('../../pages/ReleaseNotesPage'));

import { HouseholdProvider } from '../../context/HouseholdContext';
import HouseholdSwitcher from './HouseholdSwitcher';
import NotificationDrawer from '../ui/NotificationDrawer';

export default function AppLayout() {
  const { t } = useTranslation();
  const { theme, setTheme, isDark } = useTheme();
  const { isAuthenticated, signIn, signOut, isLoading, getAccessToken, error } = useLogto();
  const [tokenReady, setTokenReady] = React.useState(false);
  const [signInError, setSignInError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isAuthenticated) {
      getAccessToken(import.meta.env.VITE_LOGTO_API_RESOURCE || 'https://peng.seame.click/api')
        .then(token => {
          if (token) {
            import('../../api/client').then(({ setApiToken }) => {
              setApiToken(token);
              setTokenReady(true);
            });
          } else {
            setTokenReady(true);
          }
        })
        .catch((err) => {
          console.error(err);
          setTokenReady(true);
        });
    } else if (!isLoading) {
      setTokenReady(true);
    }
  }, [isAuthenticated, getAccessToken, isLoading]);

  const navItems = [
    { to: '/dashboard', icon: <LayoutDashboard size={20} />, label: t('app.dashboard') },
    { to: '/transactions', icon: <Receipt size={20} />, label: t('app.transactions') },
    { to: '/budgets', icon: <PieChart size={20} />, label: t('app.budgets') },
    { to: '/insights', icon: <PieChart size={20} />, label: t('app.insights', 'Indblik') },
    { to: '/accounts', icon: <Wallet size={20} />, label: t('app.accounts') },
    { to: '/settings', icon: <Settings size={20} />, label: t('app.settings') },
  ];

  if (error || signInError) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[hsl(var(--bg-primary))]">
        <div className="text-center space-y-4 p-6 bg-[hsl(var(--bg-secondary))] rounded-2xl shadow-xl max-w-md">
          <div className="w-16 h-16 bg-[hsl(var(--brand-danger))] rounded-full mx-auto flex items-center justify-center text-white mb-4">
            <LayoutDashboard size={32} />
          </div>
          <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">{t('app.loginError', 'Login Fejl')}</h2>
          <p className="text-[hsl(var(--text-secondary))] break-words">
            {error?.message || signInError}
          </p>
          <button 
            onClick={() => window.location.href = '/'}
            className="mt-6 w-full bg-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary-dark))] text-white font-medium py-2 px-4 rounded-xl transition-all"
          >
            {t('common.tryAgain', 'Prøv igen')}
          </button>
        </div>
      </div>
    );
  }

  if (isLoading || (isAuthenticated && !tokenReady)) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[hsl(var(--bg-primary))]">
        <Loader2 size={48} className="animate-spin text-[hsl(var(--brand-primary))]" />
      </div>
    );
  }

  // Allow the callback route to render its own component even if not authenticated yet
  if (!isAuthenticated && window.location.pathname !== '/callback') {
    return (
      <div className="flex flex-col h-screen w-full items-center justify-center bg-[hsl(var(--bg-primary))]">
        <div className="text-center space-y-6 max-w-sm mx-auto p-6">
          <div className="w-20 h-20 bg-[hsl(var(--brand-primary))] rounded-2xl mx-auto flex items-center justify-center shadow-lg">
            <LayoutDashboard size={40} className="text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-[hsl(var(--text-primary))] mb-2">{t('app.welcome', 'Velkommen')}</h1>
            <p className="text-[hsl(var(--text-secondary))]">{t('app.loginToContinue', 'Log ind for at få adgang til dit økonomiske overblik.')}</p>
          </div>
          <button 
            onClick={() => {
              signIn(`${window.location.origin}/callback`).catch((err: Error) => {
                console.error("SignIn error:", err);
                setSignInError(err.message || t('app.loginErrorGeneric', "Der opstod en fejl under login."));
              });
            }}
            className="w-full bg-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary-dark))] text-white font-medium py-3 px-4 rounded-xl transition-all shadow-md hover:shadow-lg active:scale-[0.98]"
          >
            {t('app.loginButton', 'Log ind for at fortsætte')}
          </button>
        </div>
      </div>
    );
  }

  // If we are on /callback but not authenticated, we still need to render the Routes
  if (!isAuthenticated && window.location.pathname === '/callback') {
    return (
      <Suspense fallback={<div className="flex h-screen w-full items-center justify-center bg-[hsl(var(--bg-primary))]"><Loader2 size={48} className="animate-spin text-[hsl(var(--brand-primary))]" /></div>}>
        <Routes>
          <Route path="/callback" element={<Callback />} />
          <Route path="*" element={<Navigate to="/callback" replace />} />
        </Routes>
      </Suspense>
    );
  }

  return (
    <HouseholdProvider>
      <div className="flex h-screen w-full overflow-hidden">
        {/* Desktop Sidebar */}
        <aside className="hidden md:flex flex-col w-64 border-r border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]">
        <div className="p-4 px-6 flex items-center justify-between border-b border-[hsl(var(--border-color))]">
          <div className="flex items-center gap-2 min-w-0">
            <h1 className="text-2xl font-bold text-[hsl(var(--brand-primary))] shrink-0">{t('app.title')}</h1>
            <HouseholdSwitcher compact />
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <NotificationDrawer compact />
            <button 
              onClick={() => setTheme(isDark ? 'light' : 'dark')}
              className="p-2 rounded-full hover:bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] transition-colors shrink-0"
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>
        </div>
        
        <nav className="flex-1 px-4 py-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive 
                    ? 'bg-[hsla(var(--brand-primary),0.1)] text-[hsl(var(--brand-primary))] font-medium' 
                    : 'text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-tertiary))] hover:text-[hsl(var(--text-primary))]'
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-[hsl(var(--border-color))]">
          <button 
            onClick={() => signOut(window.location.origin)}
            className="flex items-center gap-3 px-4 py-3 w-full text-left rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-tertiary))] hover:text-[hsl(var(--brand-danger))] transition-colors"
          >
            <LogOut size={20} />
            <span>{t('app.logout', 'Log ud')}</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[hsl(var(--bg-primary))]">
        {/* Mobile Header */}
        <header className="md:hidden flex items-center justify-between p-4 border-b border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]">
          <div className="flex items-center gap-2 min-w-0">
            <h1 className="text-xl font-bold text-[hsl(var(--brand-primary))] shrink-0">{t('app.title')}</h1>
            <HouseholdSwitcher compact />
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <NotificationDrawer compact />
            <button 
              onClick={() => setTheme(isDark ? 'light' : 'dark')}
              className="p-2 rounded-full hover:bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] transition-colors"
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button 
              onClick={() => signOut(window.location.origin)}
              className="p-2 rounded-full text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--brand-danger))] transition-colors"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>

        <div id="scroll-container" className="flex-1 overflow-y-auto pb-24 md:pb-0 relative z-0">
          <Suspense fallback={
            <div className="flex h-full w-full items-center justify-center">
              <Loader2 size={32} className="animate-spin text-[hsl(var(--brand-primary))]" />
            </div>
          }>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/budgets" element={<BudgetsPage />} />
              <Route path="/accounts" element={<AccountsPage />} />
              <Route path="/insights" element={<InsightsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/settings/release-notes" element={<ReleaseNotesPage />} />
              <Route path="/callback" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Suspense>
        </div>
      </main>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 glass border-t flex justify-around p-2 pb-safe z-50">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => 
              `flex flex-col items-center gap-0.5 py-1 px-0.5 rounded-lg transition-colors flex-1 min-w-0 ${
                isActive 
                  ? 'text-[hsl(var(--brand-primary))]' 
                  : 'text-[hsl(var(--text-secondary))]'
              }`
            }
          >
            {item.icon}
            <span className="text-[10px] font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
    </HouseholdProvider>
  );
}
