import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
  className?: string;
}

export function LoadingSpinner({ message = 'Loading...', className = '' }: LoadingSpinnerProps) {
  return (
    <div className={`flex flex-col items-center justify-center p-12 space-y-4 animate-page-in ${className}`}>
      <div className="relative">
        {/* Glow effect */}
        <div className="absolute inset-0 bg-accent/20 blur-xl rounded-full"></div>
        {/* Spinner */}
        <Loader2 className="w-8 h-8 text-accent animate-spin relative z-10" />
      </div>
      {message && (
        <div className="text-sm font-medium text-tx-secondary tracking-wide animate-pulse">
          {message}
        </div>
      )}
    </div>
  );
}
