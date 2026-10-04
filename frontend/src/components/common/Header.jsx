import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { User, LogOut, BookOpen } from 'lucide-react';

export const Header = () => {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-sm shadow-sm">
          <BookOpen size={18} />
        </div>
        <div>
          <h1 className="text-base font-semibold text-slate-900 tracking-tight">HOTS RAG</h1>
          <p className="text-xs text-slate-500 font-medium">University Developer Portal</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium">
          <User size={14} className="text-slate-500" />
          <span>{user || 'Developer'}</span>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
          title="Sign out of Developer Mode"
        >
          <LogOut size={14} />
          <span>Logout</span>
        </button>
      </div>
    </header>
  );
};
