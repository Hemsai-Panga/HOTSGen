import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getCourse } from '../api/courses';
import { getMaterials } from '../api/materials';
import { CourseReadiness } from '../components/materials/CourseReadiness';
import { UploadSection } from '../components/materials/UploadSection';
import { PipelineStatusModal } from '../components/materials/PipelineStatusModal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ArrowLeft, RefreshCw, AlertCircle, BookOpen } from 'lucide-react';

export const CourseMaterials = () => {
  const { courseCode } = useParams();
  const navigate = useNavigate();

  const [course, setCourse] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [inspectMaterial, setInspectMaterial] = useState(null);

  const fetchCourseData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [courseData, materialsData] = await Promise.all([
        getCourse(courseCode),
        getMaterials(courseCode),
      ]);
      setCourse(courseData);
      setMaterials(materialsData || []);
      setLoading(false);
    } catch (err) {
      setLoading(false);
      setError(err.response?.data?.detail || 'Failed to fetch course details or materials.');
    }
  };

  useEffect(() => {
    if (courseCode) {
      fetchCourseData();
    }
  }, [courseCode]);

  // Filter materials by category
  const syllabusMaterials = materials.filter((m) => m.source_type === 'syllabus');
  const lectureMaterials = materials.filter((m) => m.source_type === 'lecture_material');
  const referenceMaterials = materials.filter((m) => m.source_type === 'reference_book');
  const examMaterials = materials.filter((m) => m.source_type === 'exam_paper');

  return (
    <div className="space-y-8">
      {/* Top Breadcrumbs & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
        <div>
          <button
            onClick={() => navigate('/dashboard')}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-2 transition-colors"
          >
            <ArrowLeft size={14} />
            <span>Back to Dashboard</span>
          </button>
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 text-xs font-bold font-mono tracking-wide rounded-md bg-slate-900 text-white">
              {courseCode}
            </span>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
              {course ? course.course_name : 'Course Materials'}
            </h2>
          </div>
          {course?.description && (
            <p className="text-xs text-slate-500 mt-1 max-w-2xl font-medium">{course.description}</p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchCourseData}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-50 text-xs font-semibold transition-colors"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
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
            onClick={fetchCourseData}
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
          <p className="text-sm font-medium">Loading course materials & readiness state...</p>
        </div>
      )}

      {/* Main Material Sections */}
      {!loading && (
        <div className="space-y-8">
          {/* Top Course Readiness Panel */}
          <CourseReadiness materials={materials} courseCode={courseCode} />

          {/* Four Visually Sequential Upload Sections */}
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Material Ingestion Pipeline
                </h3>
                <p className="text-xs text-slate-500 font-medium">
                  Upload files for each category. Sections execute independently and do not block one another.
                </p>
              </div>
            </div>

            {/* ① Syllabus */}
            <UploadSection
              stepNumber="①"
              title="Course Syllabus"
              subtitle="Upload official course syllabus document (PDF/DOC) to extract structured units, topics, and subtopics."
              sourceType="syllabus"
              courseCode={courseCode}
              materials={syllabusMaterials}
              allowMultiple={false}
              onMaterialUpdated={fetchCourseData}
              onInspectPipeline={setInspectMaterial}
            />

            {/* ② Lecture Materials */}
            <UploadSection
              stepNumber="②"
              title="Lecture Materials & Slide Decks"
              subtitle="Upload weekly presentation slides, transcripts, or notes (PPTX, PDF, DOCX)."
              sourceType="lecture_material"
              courseCode={courseCode}
              materials={lectureMaterials}
              allowMultiple={true}
              onMaterialUpdated={fetchCourseData}
              onInspectPipeline={setInspectMaterial}
            />

            {/* ③ Reference Books / Notes */}
            <UploadSection
              stepNumber="③"
              title="Reference Books & Academic Notes"
              subtitle="Upload textbook chapters, reference notes, or supplementary reading materials (PDF, DOCX)."
              sourceType="reference_book"
              courseCode={courseCode}
              materials={referenceMaterials}
              allowMultiple={true}
              onMaterialUpdated={fetchCourseData}
              onInspectPipeline={setInspectMaterial}
            />

            {/* ④ CAT / FAT Exam Papers */}
            <UploadSection
              stepNumber="④"
              title="CAT / CAT2 / FAT Examination Papers"
              subtitle="Upload previous CAT1, CAT2, and FAT exam papers to extract question style, tone, and mark exemplars."
              sourceType="exam_paper"
              courseCode={courseCode}
              materials={examMaterials}
              allowMultiple={true}
              onMaterialUpdated={fetchCourseData}
              onInspectPipeline={setInspectMaterial}
            />
          </div>
        </div>
      )}

      {/* Granular Pipeline Status Inspector Modal */}
      <PipelineStatusModal
        isOpen={!!inspectMaterial}
        onClose={() => setInspectMaterial(null)}
        material={inspectMaterial}
      />
    </div>
  );
};
