import React from 'react';
import { CheckCircle2, Circle, Sparkles, AlertTriangle } from 'lucide-react';

export const CourseReadiness = ({ materials = [], courseCode }) => {
  const isCategoryReady = (sourceType) => {
    const catMaterials = materials.filter((m) => m.source_type === sourceType);
    if (catMaterials.length === 0) return false;
    return catMaterials.every(
      (m) => m.processing_status === 'completed' || m.processing_status === 'processed'
    );
  };

  const hasSyllabus = isCategoryReady('syllabus');
  const hasLectures = isCategoryReady('lecture_material');
  const hasReferences = isCategoryReady('reference_book');
  const hasExams = isCategoryReady('exam_paper');

  const categories = [
    { label: 'Syllabus', ready: hasSyllabus, count: materials.filter((m) => m.source_type === 'syllabus').length },
    { label: 'Lecture Materials', ready: hasLectures, count: materials.filter((m) => m.source_type === 'lecture_material').length },
    { label: 'Reference Materials', ready: hasReferences, count: materials.filter((m) => m.source_type === 'reference_book').length },
    { label: 'Exam Papers', ready: hasExams, count: materials.filter((m) => m.source_type === 'exam_paper').length },
  ];

  const completedCount = categories.filter((c) => c.ready).length;
  const isReady = completedCount === 4;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900">Course Status</h3>
          <p className="text-xs text-slate-500 font-medium">Readiness for HOTS Question Generation</p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
          {completedCount} of 4 categories
        </span>
      </div>

      {/* Checklist */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-5">
        {categories.map((cat) => (
          <div
            key={cat.label}
            className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
              cat.ready
                ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                : 'bg-slate-50/50 border-slate-200 text-slate-500'
            }`}
          >
            {cat.ready ? (
              <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />
            ) : (
              <Circle size={18} className="text-slate-300 shrink-0" />
            )}
            <div className="min-w-0">
              <p className="text-xs font-semibold truncate">{cat.label}</p>
              <p className="text-[10px] text-slate-500">{cat.count} {cat.count === 1 ? 'file' : 'files'}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Readiness Badge */}
      <div className="pt-4 border-t border-slate-100">
        {isReady ? (
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800">
            <div className="flex items-center gap-2.5">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-sm font-semibold">Ready for Question Generation</span>
            </div>
            <Sparkles size={18} className="text-emerald-600 shrink-0" />
          </div>
        ) : (
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
            <div className="flex items-center gap-2.5">
              <AlertTriangle size={18} className="text-amber-600 shrink-0" />
              <span className="text-sm font-semibold">Course Incomplete</span>
            </div>
            <span className="text-xs font-medium text-amber-700">
              {completedCount} of 4 required categories available
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
