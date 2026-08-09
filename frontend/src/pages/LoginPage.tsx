import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../store/useAppStore';
import { LineChart, Lock } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAppStore();

  useEffect(() => {
    // If user is already authenticated, redirect them away from the login page
    if (isAuthenticated) {
      const origin = (location.state as any)?.from?.pathname || '/chat';
      navigate(origin, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  const handleGoogleLogin = () => {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    window.location.href = `${apiBaseUrl}/auth/google/login`;
  };

  const handleGuestAccess = () => {
    navigate('/chat', { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#060E0A] flex items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* Background glowing orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/20 rounded-full blur-[120px] opacity-60 pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#2C6E49]/20 rounded-full blur-[120px] opacity-40 pointer-events-none" />

      {/* Main Glass Card */}
      <div className="relative z-10 w-full max-w-md">
        <div className="bg-[#0D1912]/80 backdrop-blur-xl border border-hairline rounded-2xl p-8 shadow-2xl flex flex-col items-center text-center">
          
          {/* Logo area */}
          <div className="w-16 h-16 bg-[#14251B] border border-hairline rounded-2xl flex items-center justify-center mb-6 shadow-inner">
            <LineChart className="w-8 h-8 text-accent" />
          </div>

          <h1 className="text-3xl font-medium text-cream mb-2 tracking-tight">Welcome to VittLens</h1>
          <p className="text-sm text-cream-muted mb-8 ai-answer-serif">
            Advanced Financial Intelligence for the Indian Market.
          </p>

          {/* Action Buttons */}
          <div className="w-full space-y-4">
            <button
              onClick={handleGoogleLogin}
              className="w-full flex items-center justify-center space-x-3 bg-[#E5D5B5] hover:bg-[#D4C3A3] text-[#060E0A] py-3 px-4 rounded-xl transition-all duration-200 shadow-[0_0_15px_rgba(229,213,181,0.15)] hover:shadow-[0_0_25px_rgba(229,213,181,0.25)] group"
            >
              <svg className="w-5 h-5 text-[#060E0A]" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              <span className="font-medium text-[15px]">Sign in with Google</span>
            </button>

            <div className="relative flex items-center justify-center my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-hairline"></div>
              </div>
              <span className="relative bg-[#0D1912] px-4 text-xs text-cream-dim uppercase tracking-wider font-medium">Or</span>
            </div>

            <button
              onClick={handleGuestAccess}
              className="w-full flex items-center justify-center space-x-2 bg-[#14251B] hover:bg-[#1A2E22] border border-hairline text-cream py-3 px-4 rounded-xl transition-colors group"
            >
              <Lock className="w-4 h-4 text-cream-muted group-hover:text-cream transition-colors" />
              <span className="font-medium text-[14px]">Continue as Guest</span>
            </button>
            <p className="text-[11px] text-cream-dim mt-2 text-center">
              Guest access is limited to 15 queries per day.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-xs text-cream-dim">
          <p>© 2026 VittLens Platform. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
};
