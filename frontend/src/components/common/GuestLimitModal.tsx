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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in font-sans">
      <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 max-w-md w-full shadow-2xl text-center space-y-5">
        <div className="w-12 h-12 rounded-full bg-[#14251B] border border-hairline text-accent flex items-center justify-center mx-auto">
          <Lock className="w-6 h-6" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-medium text-cream">Guest Limit Reached</h2>
          <p className="text-sm text-cream-muted leading-relaxed">
            You have used all free guest queries. Sign in with Google to unlock unlimited AI financial analysis, portfolio tracking, and custom watchlists.
          </p>
        </div>

        <div className="bg-[#14251B] p-4 rounded-lg border border-hairline text-left space-y-2 text-xs text-cream">
          <div className="flex items-center space-x-2 text-accent font-medium">
            <Sparkles className="w-4 h-4" />
            <span>Unlocked with Free Account:</span>
          </div>
          <ul className="list-disc list-inside space-y-1 text-cream-muted">
            <li>Unlimited multi-agent financial queries</li>
            <li>Saved portfolio holdings & live P&L tracking</li>
            <li>Custom NIFTY 20 watchlists & SEC filing charts</li>
          </ul>
        </div>

        <div className="pt-2 space-y-3">
          <button
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center space-x-2 bg-accent hover:bg-accent-hover text-cream font-medium py-2.5 px-4 rounded-lg transition-colors text-sm shadow-sm"
          >
            <LogIn className="w-4 h-4" />
            <span>Sign in with Google</span>
          </button>

          <button
            onClick={() => setGuestLimitModalOpen(false)}
            className="text-xs text-cream-muted hover:text-cream transition-colors"
          >
            Dismiss for now
          </button>
        </div>
      </div>
    </div>
  );
};
