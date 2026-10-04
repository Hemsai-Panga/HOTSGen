import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { createCourse } from '../../api/courses';
import { PlusCircle, AlertCircle } from 'lucide-react';

export const AddCourseModal = ({ isOpen, onClose, onCourseCreated }) => {
  const [courseCode, setCourseCode] = useState('');
  const [courseName, setCourseName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const resetForm = () => {
    setCourseCode('');
    setCourseName('');
    setDescription('');
    setError(null);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!courseCode.trim() || !courseName.trim()) {
      setError('Please provide both course code and course title.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const newCourse = await createCourse({
        course_code: courseCode.trim().toUpperCase(),
        course_name: courseName.trim(),
        description: description.trim() || undefined,
      });
      setLoading(false);
      resetForm();
      onCourseCreated(newCourse);
      onClose();
    } catch (err) {
      setLoading(false);
      setError(err.response?.data?.detail || 'Failed to create course. Please check if code already exists.');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Add New Course">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
            <AlertCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
            Course Code <span className="text-rose-500">*</span>
          </label>
          <input
            type="text"
            required
            placeholder="e.g. BCSE301"
            value={courseCode}
            onChange={(e) => setCourseCode(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent text-sm uppercase font-mono"
          />
          <p className="text-xs text-slate-400 mt-1">Unique university course identifier.</p>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
            Course Title / Name <span className="text-rose-500">*</span>
          </label>
          <input
            type="text"
            required
            placeholder="e.g. Database Management Systems"
            value={courseName}
            onChange={(e) => setCourseName(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent text-sm"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
            Description <span className="text-slate-400 text-xs font-normal">(Optional)</span>
          </label>
          <textarea
            rows={3}
            placeholder="Brief description of the course contents or syllabus objectives..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent text-sm resize-none"
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-semibold shadow-sm transition-all disabled:opacity-50"
          >
            {loading ? (
              <>
                <LoadingSpinner size={16} className="text-white" />
                <span>Creating...</span>
              </>
            ) : (
              <>
                <PlusCircle size={16} />
                <span>Create Course</span>
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
};
