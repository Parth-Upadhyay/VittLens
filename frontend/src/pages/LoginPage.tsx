import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../store/useAppStore';
import { LineChart, Lock } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAppStore();

  useEffect(() => {
    if (user) {
      const origin = (location.state as any)?.from?.pathname || '/chat';
      navigate(origin, { replace: true });
    }
  }, [user, navigate, location]);

  const handleGoogleLogin = () => {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
    window.location.href = `${apiBaseUrl}/auth/google/login`;
  };

  const handleGuestAccess = () => {
    navigate('/chat', { replace: true });
  };

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* Background subtle warm orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/8 rounded-full blur-[120px] opacity-60 pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-semantic-amber/8 rounded-full blur-[120px] opacity-40 pointer-events-none" />

      {/* Main Card */}
      <div className="relative z-10 w-full max-w-md animate-page-in">
        <div className="surface-elevated p-8 flex flex-col items-center text-center">
          
          {/* Logo area */}
          <div className="w-16 h-16 bg-accent-light border border-border rounded-2xl flex items-center justify-center mb-6">
            <LineChart className="w-8 h-8 text-accent" />
          </div>

          <h1 className="text-3xl font-heading font-semibold text-tx-primary mb-2 tracking-tight">Welcome to VittLens</h1>
          <p className="text-sm text-tx-secondary mb-8 leading-relaxed">
            Advanced Financial Intelligence for the Indian Market.
          </p>

          {/* Action Buttons */}
          <div className="w-full space-y-4">
            <button
              onClick={handleGoogleLogin}
              className="w-full flex items-center justify-center space-x-3 bg-accent hover:bg-accent-hover text-white py-3 px-4 rounded-xl nav-transition btn-press shadow-card group"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
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
                <div className="w-full border-t border-border"></div>
              </div>
              <span className="relative bg-bg-secondary px-4 text-xs text-tx-tertiary uppercase tracking-wider font-medium">Or</span>
            </div>

            <button
              onClick={handleGuestAccess}
              className="w-full flex items-center justify-center space-x-2 bg-bg-tertiary hover:bg-bg-hover border border-border text-tx-primary py-3 px-4 rounded-xl nav-transition btn-press group"
            >
              <Lock className="w-4 h-4 text-tx-secondary group-hover:text-tx-primary nav-transition" />
              <span className="font-medium text-[14px]">Continue as Guest</span>
            </button>
            <p className="text-[11px] text-tx-tertiary mt-2 text-center">
              Guest access is limited to 15 queries per day.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-xs text-tx-tertiary">
          <p>© 2026 VittLens Platform. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
};
