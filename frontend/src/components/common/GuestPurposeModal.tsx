import React, { useState } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { AuthService } from '../../services/api';
import { Compass, Check } from 'lucide-react';

const PURPOSES = [
  'Retail Investor',
  'Financial Analyst',
  'Active Trader',
  'Student / Academic',
  'General Research',
];

export const GuestPurposeModal: React.FC = () => {
  const { isGuestPurposeModalOpen, setGuestPurposeModalOpen } = useAppStore();
  const [selected, setSelected] = useState<string>('Retail Investor');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isGuestPurposeModalOpen) return null;

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      await AuthService.submitGuestPurpose(selected);
      setGuestPurposeModalOpen(false);
    } catch (e) {
      console.error('Failed to submit purpose:', e);
      setGuestPurposeModalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in font-sans">
      <div className="bg-[#0D1912] border border-hairline rounded-xl p-6 max-w-md w-full shadow-2xl space-y-5 text-left">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-[#14251B] border border-hairline text-accent flex items-center justify-center">
            <Compass className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-medium text-cream">Welcome to VittLens!</h2>
            <p className="text-xs text-cream-muted">What brings you to our platform today?</p>
          </div>
        </div>

        <div className="space-y-2">
          {PURPOSES.map((p) => {
            const active = selected === p;
            return (
              <button
                key={p}
                onClick={() => setSelected(p)}
                className={`w-full flex items-center justify-between p-3 rounded-lg border text-sm transition-colors text-left ${
                  active
                    ? 'border-accent bg-[#14251B] text-cream font-medium'
                    : 'border-hairline bg-[#060E0A] text-cream-muted hover:bg-[#14251B]/50'
                }`}
              >
                <span>{p}</span>
                {active && <Check className="w-4 h-4 text-accent" />}
              </button>
            );
          })}
        </div>

        <div className="pt-2 flex items-center justify-end space-x-3">
          <button
            onClick={() => setGuestPurposeModalOpen(false)}
            className="px-4 py-2 text-xs text-cream-muted hover:text-cream transition-colors"
          >
            Skip for now
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="bg-accent hover:bg-accent-hover text-cream text-xs font-medium px-4 py-2 rounded-lg transition-colors shadow-sm"
          >
            {isSubmitting ? 'Saving...' : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  );
};
