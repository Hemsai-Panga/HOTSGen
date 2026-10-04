import React, { useState, useEffect } from 'react';
import { getCourses } from '../api/courses';
import { getMaterials } from '../api/materials';
import { CourseCard } from '../components/dashboard/CourseCard';
import { AddCourseModal } from '../components/dashboard/AddCourseModal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Plus, BookOpen, AlertCircle, RefreshCw } from 'lucide-react';

export const Dashboard = () => {
  const [courses, setCourses] = useState([]);
  const [materialsByCourse, setMaterialsByCourse] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const coursesData = await getCourses();
      setCourses(coursesData || []);

      // Fetch materials for each course to calculate category readiness
      if (coursesData && coursesData.length > 0) {
        const materialsMap = {};
        await Promise.all(
          coursesData.map(async (course) => {
            try {
              const mats = await getMaterials(course.course_code);
              materialsMap[course.course_code] = mats || [];
            } catch (err) {
              materialsMap[course.course_code] = [];
            }
          })
        );
        setMaterialsByCourse(materialsMap);
      }
      setLoading(false);
    } catch (err) {
      setLoading(false);
      setError(err.response?.data?.detail || 'Failed to fetch course catalog.');
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleCourseCreated = (newCourse) => {
    setCourses((prev) => [newCourse, ...prev]);
    setMaterialsByCourse((prev) => ({ ...prev, [newCourse.course_code]: [] }));
  };

  return (
    <div className="space-y-8">
      {/* Top Banner & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Course Knowledge Base</h2>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Manage course syllabi, documents, exam papers, and inspect HOTS question generation readiness.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="p-2.5 rounded-xl border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors"
            title="Refresh dashboard"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-sm font-semibold shadow-sm transition-all"
          >
            <Plus size={16} />
            <span>Add Course</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm font-medium">
          <div className="flex items-center gap-2">
            <AlertCircle size={18} className="shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchDashboardData}
            className="px-3 py-1 bg-rose-100 hover:bg-rose-200 rounded-lg text-xs font-semibold text-rose-800 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
          <LoadingSpinner size={32} />
          <p className="text-sm font-medium">Loading course catalog...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && courses.length === 0 && !error && (
        <div className="py-20 px-6 text-center border-2 border-dashed border-slate-200 rounded-3xl bg-slate-50/50 flex flex-col items-center justify-center max-w-lg mx-auto">
          <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 flex items-center justify-center text-slate-400 mb-4 shadow-sm">
            <BookOpen size={24} />
          </div>
          <h3 className="text-base font-semibold text-slate-900">No courses available</h3>
          <p className="text-xs text-slate-500 max-w-xs mt-1 mb-6">
            Get started by registering a new course to upload syllabi, notes, and past examination papers.
          </p>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-sm font-semibold shadow-sm transition-all"
          >
            <Plus size={16} />
            <span>Add Your First Course</span>
          </button>
        </div>
      )}

      {/* Course Grid: Square Cards */}
      {!loading && courses.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {courses.map((course) => (
            <CourseCard
              key={course.course_code}
              course={course}
              materials={materialsByCourse[course.course_code] || []}
            />
          ))}
        </div>
      )}

      {/* Add Course Modal */}
      <AddCourseModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onCourseCreated={handleCourseCreated}
      />
    </div>
  );
};
