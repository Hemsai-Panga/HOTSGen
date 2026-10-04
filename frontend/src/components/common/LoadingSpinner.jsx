import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingSpinner = ({ size = 20, className = 'text-slate-600' }) => {
  return (
    <Loader2 size={size} className={`animate-spin ${className}`} />
  );
};
