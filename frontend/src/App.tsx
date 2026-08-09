import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppStore } from './store/useAppStore';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { GuestLimitModal } from './components/common/GuestLimitModal';
import { GuestPurposeModal } from './components/common/GuestPurposeModal';
import { ChatPage } from './pages/ChatPage';
import { DashboardPage } from './pages/DashboardPage';
import { NewsPage } from './pages/NewsPage';
import { CompanyDetailPage } from './pages/CompanyDetailPage';
import { PortfolioAnalyzerPage } from './pages/PortfolioAnalyzerPage';
import { DeepAnalyzePage } from './pages/DeepAnalyzePage';
import { FilingAgentPage } from './pages/FilingAgentPage';
import { SettingsPage } from './pages/SettingsPage';
import { LoginPage } from './pages/LoginPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

});

const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  return (
    <>
      <Header onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
      <div className="flex-1 flex overflow-hidden relative min-h-0">
        <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
        <main className="flex-1 flex flex-col min-w-0 overflow-y-auto h-full bg-[#060E0A]">
          {children}
        </main>
      </div>
    </>
  );
};

export const App: React.FC = () => {
  const { initSession, setGuestLimitModalOpen, preferences } = useAppStore();

  useEffect(() => {
    initSession();

    // Check for Google OAuth callback token in URL query
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (token) {
      localStorage.setItem('auth_token', token);
      window.history.replaceState({}, document.title, window.location.pathname);
      initSession();
    }

    // Listen for custom limit reached events
    const handleGuestLimit = () => setGuestLimitModalOpen(true);
    const handleUserLimit = () => alert("You have reached your daily limit of 45 queries. Please come back tomorrow!");
    
    window.addEventListener('guest_limit_reached', handleGuestLimit);
    window.addEventListener('user_limit_reached', handleUserLimit);

    return () => {
      window.removeEventListener('guest_limit_reached', handleGuestLimit);
      window.removeEventListener('user_limit_reached', handleUserLimit);
    };
  }, []);

  // Theme Sync Effect: Toggle light-mode class on body
  useEffect(() => {
    if (preferences.theme === 'Light') {
      document.body.classList.add('light-mode');
    } else {
      document.body.classList.remove('light-mode');
    }
  }, [preferences.theme]);

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="h-screen max-h-screen bg-[#060E0A] text-[#F5EFE6] flex flex-col font-sans overflow-hidden">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/*" element={
              <MainLayout>
                <Routes>
                  <Route path="/" element={<Navigate to="/login" replace />} />
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/news" element={<NewsPage />} />
                  <Route path="/company/:symbol" element={<CompanyDetailPage />} />
                  <Route path="/portfolio-analyzer" element={<PortfolioAnalyzerPage />} />
                  <Route path="/deep-analyze" element={<DeepAnalyzePage />} />
                  <Route path="/filing-agent" element={<FilingAgentPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="*" element={<Navigate to="/chat" replace />} />
                </Routes>
              </MainLayout>
            } />
          </Routes>

          {/* Global Modals */}
          <GuestLimitModal />
          <GuestPurposeModal />
        </div>
      </Router>
    </QueryClientProvider>
  );
};
