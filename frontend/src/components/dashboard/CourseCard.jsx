import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Circle, AlertCircle, ArrowUpRight, Sparkles } from 'lucide-react';

export const CourseCard = ({ course, materials = [] }) => {
  const navigate = useNavigate();

  // Compute status for the 4 required categories based on successful pipeline processing
  const isCategoryReady = (sourceType) => {
    const catMaterials = materials.filter((m) => m.source_type === sourceType);
    if (catMaterials.length === 0) return false;
    // Category is ready ONLY if all uploaded files in it are processed/completed, with none pending or failed
    return catMaterials.every(
      (m) => m.processing_status === 'completed' || m.processing_status === 'processed'
    );
  };

  const hasSyllabus = isCategoryReady('syllabus');
  const hasLectures = isCategoryReady('lecture_material');
  const hasReferences = isCategoryReady('reference_book');
  const hasExams = isCategoryReady('exam_paper');

  const categories = [
    { label: 'Syllabus', ready: hasSyllabus },
    { label: 'Lecture Materials', ready: hasLectures },
    { label: 'Reference Materials', ready: hasReferences },
    { label: 'Exam Papers', ready: hasExams },
  ];

  const completedCount = categories.filter((c) => c.ready).length;
  const isReady = completedCount === 4;

  const handleClick = () => {
    navigate(`/courses/${course.course_code}`);
  };

  return (
    <div
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      className="group aspect-square p-6 bg-white rounded-2xl border border-slate-200 hover:border-slate-400 hover:shadow-lg transition-all flex flex-col justify-between cursor-pointer relative overflow-hidden"
    >
      {/* Top Header */}
      <div>
        <div className="flex items-start justify-between gap-2 mb-2">
          <span className="inline-block px-2.5 py-1 text-xs font-bold font-mono tracking-wide rounded-md bg-slate-100 text-slate-800 border border-slate-200">
            {course.course_code}
          </span>
          <div className="text-slate-300 group-hover:text-slate-600 transition-colors">
            <ArrowUpRight size={18} />
          </div>
        </div>
        <h3 className="text-base font-semibold text-slate-900 leading-snug line-clamp-2" title={course.course_name}>
          {course.course_name}
        </h3>
      </div>

      {/* Category Checklist */}
      <div className="my-auto py-2 space-y-1.5 border-y border-slate-100">
        {categories.map((cat) => (
          <div key={cat.label} className="flex items-center gap-2 text-xs">
            {cat.ready ? (
              <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
            ) : (
              <Circle size={14} className="text-slate-300 shrink-0" />
            )}
            <span className={cat.ready ? 'text-slate-700 font-medium' : 'text-slate-400'}>
              {cat.label}
            </span>
          </div>
        ))}
      </div>

      {/* Bottom Status & Readiness */}
      <div>
        <div className="flex items-center justify-between text-xs font-medium mb-2">
          <span className="text-slate-500">{completedCount}/4 complete</span>
          {isReady ? (
            <span className="flex items-center gap-1 text-emerald-600 font-semibold">
              <Sparkles size={12} />
              <span>Ready</span>
            </span>
          ) : (
            <span className="flex items-center gap-1 text-amber-600 font-medium">
              <AlertCircle size={12} />
              <span>Incomplete</span>
            </span>
          )}
        </div>

        {/* Mini progress bar */}
        <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              isReady ? 'bg-emerald-500' : 'bg-amber-500'
            }`}
            style={{ width: `${(completedCount / 4) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};
