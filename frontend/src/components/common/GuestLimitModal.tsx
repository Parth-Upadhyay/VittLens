import React from 'react';
import { useAppStore } from '../../store/useAppStore';
import { LogIn, Lock, Sparkles } from 'lucide-react';

export const GuestLimitModal: React.FC = () => {
  const { isGuestLimitModalOpen, setGuestLimitModalOpen } = useAppStore();

  if (!isGuestLimitModalOpen) return null;

  const handleGoogleLogin = () => {
    window.location.href = '/api/v1/auth/google/login';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-page-in font-sans">
      <div className="surface-elevated p-6 max-w-md w-full text-center space-y-5">
        <div className="w-12 h-12 rounded-full bg-accent-light border border-border text-accent flex items-center justify-center mx-auto">
          <Lock className="w-6 h-6" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-heading font-semibold text-tx-primary">Guest Limit Reached</h2>
          <p className="text-sm text-tx-secondary leading-relaxed">
            You have used all free guest queries. Sign in with Google to unlock unlimited AI financial analysis, portfolio tracking, and custom watchlists.
          </p>
        </div>

        <div className="bg-bg-tertiary p-4 rounded-lg border border-border text-left space-y-2 text-xs text-tx-primary">
          <div className="flex items-center space-x-2 text-accent font-medium">
            <Sparkles className="w-4 h-4" />
            <span>Unlocked with Free Account:</span>
          </div>
          <ul className="list-disc list-inside space-y-1 text-tx-secondary">
            <li>Unlimited multi-agent financial queries</li>
            <li>Saved portfolio holdings & live P&L tracking</li>
            <li>Custom NIFTY 20 watchlists & SEC filing charts</li>
          </ul>
        </div>

        <div className="pt-2 space-y-3">
          <button
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center space-x-2 bg-accent hover:bg-accent-hover text-white font-medium py-2.5 px-4 rounded-lg nav-transition btn-press text-sm shadow-sm"
          >
            <LogIn className="w-4 h-4" />
            <span>Sign in with Google</span>
          </button>

          <button
            onClick={() => setGuestLimitModalOpen(false)}
            className="text-xs text-tx-secondary hover:text-tx-primary nav-transition"
          >
            Dismiss for now
          </button>
        </div>
      </div>
    </div>
  );
};
