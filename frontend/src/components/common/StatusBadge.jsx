import React from 'react';
import { CheckCircle2, Clock, AlertTriangle, XCircle, ArrowRight } from 'lucide-react';

export const StatusBadge = ({ status, errorMsg, size = 'sm' }) => {
  const normalized = (status || 'uploaded').toLowerCase();

  let label = 'Uploaded';
  let colorClass = 'bg-slate-50 text-slate-700 border-slate-200';
  let Icon = Clock;

  switch (normalized) {
    case 'completed':
    case 'processed':
    case 'ready':
      label = 'Ready';
      colorClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';
      Icon = CheckCircle2;
      break;
    case 'processing':
    case 'running':
      label = 'Processing';
      colorClass = 'bg-sky-50 text-sky-700 border-sky-200';
      Icon = ArrowRight;
      break;
    case 'failed':
      label = 'Failed';
      colorClass = 'bg-rose-50 text-rose-700 border-rose-200';
      Icon = XCircle;
      break;
    case 'pending':
      label = 'Pending';
      colorClass = 'bg-amber-50 text-amber-700 border-amber-200';
      Icon = Clock;
      break;
    case 'skipped':
      label = 'Skipped';
      colorClass = 'bg-slate-100 text-slate-500 border-slate-200';
      Icon = AlertTriangle;
      break;
    case 'uploaded':
    default:
      label = 'Uploaded';
      colorClass = 'bg-slate-100 text-slate-700 border-slate-200';
      Icon = Clock;
      break;
  }

  const paddingClass = size === 'xs' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1 font-medium rounded-full border ${paddingClass} ${colorClass}`}
      title={errorMsg || label}
    >
      <Icon size={12} className="shrink-0" />
      <span>{label}</span>
    </span>
  );
};
