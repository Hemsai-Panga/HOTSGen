import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  Trash2,
  Play,
  Activity,
  AlertCircle,
  File,
  Plus,
} from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { StatusBadge } from '../common/StatusBadge';
import { uploadMaterial, deleteMaterial, ingestMaterial } from '../../api/materials';

export const UploadSection = ({
  stepNumber,
  title,
  subtitle,
  sourceType,
  courseCode,
  materials = [],
  allowMultiple = false,
  acceptFormats = '.pdf,.pptx,.docx,.png,.jpg,.jpeg',
  onMaterialUpdated,
  onInspectPipeline,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ingestingId, setIngestingId] = useState(null);
  const [error, setError] = useState(null);
  const [examType, setExamType] = useState('CAT1');
  const [examYear, setExamYear] = useState(new Date().getFullYear());
  const fileInputRef = useRef(null);

  const hasFiles = materials.length > 0;

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(e.target.files);
    }
  };

  const processFiles = async (filesList) => {
    const filesToUpload = allowMultiple ? Array.from(filesList) : [filesList[0]];
    setUploading(true);
    setError(null);

    try {
      for (const file of filesToUpload) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('course_code', courseCode);
        formData.append('source_type', sourceType);

        if (sourceType === 'exam_paper') {
          formData.append('exam_type', examType);
          formData.append('year', examYear.toString());
        }

        await uploadMaterial(formData);
      }
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
      onMaterialUpdated();
    } catch (err) {
      setUploading(false);
      setError(err.response?.data?.detail || 'Failed to upload material. Please try again.');
    }
  };

  const handleDelete = async (materialId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this document?')) return;
    try {
      await deleteMaterial(materialId);
      onMaterialUpdated();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete material.');
    }
  };

  const handleIngest = async (materialId, e) => {
    e.stopPropagation();
    setIngestingId(materialId);
    setError(null);
    try {
      await ingestMaterial(materialId);
      setIngestingId(null);
      onMaterialUpdated();
    } catch (err) {
      setIngestingId(null);
      setError(err.response?.data?.detail || 'Ingestion pipeline failed.');
      onMaterialUpdated();
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm transition-all hover:border-slate-300">
      {/* Section Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-bold shrink-0">
            {stepNumber}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-slate-900">{title}</h3>
              {hasFiles && (
                <span className="flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckCircle2 size={12} />
                  <span>{materials.length} {materials.length === 1 ? 'file' : 'files'}</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
          </div>
        </div>
      </div>

      {/* Exam metadata selectors (if exam_paper) */}
      {sourceType === 'exam_paper' && (
        <div className="flex flex-wrap items-center gap-4 mb-4 p-3 rounded-xl bg-slate-50 border border-slate-200">
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-slate-700">Exam Type:</label>
            <select
              value={examType}
              onChange={(e) => setExamType(e.target.value)}
              className="text-xs font-medium px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white focus:ring-2 focus:ring-slate-900"
            >
              <option value="CAT1">CAT1</option>
              <option value="CAT2">CAT2</option>
              <option value="FAT">FAT</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-slate-700">Year:</label>
            <input
              type="number"
              min="2000"
              max="2100"
              value={examYear}
              onChange={(e) => setExamYear(parseInt(e.target.value) || new Date().getFullYear())}
              className="w-20 text-xs font-medium px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white focus:ring-2 focus:ring-slate-900"
            />
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="mb-4 flex items-center justify-between p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* Upload Dropzone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-slate-900 bg-slate-50'
            : 'border-slate-200 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptFormats}
          multiple={allowMultiple}
          onChange={handleFileChange}
          className="hidden"
        />

        {uploading ? (
          <div className="flex flex-col items-center justify-center gap-2 text-slate-600 py-2">
            <LoadingSpinner size={24} />
            <span className="text-xs font-medium">Uploading material...</span>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-2">
            <div className="w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-600 shadow-2xs">
              <UploadCloud size={20} />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-900">
                Click to browse or drag & drop {allowMultiple ? 'files' : 'a file'}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Supported: PDF, PPTX, DOCX, PNG, JPG
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Uploaded Materials List */}
      {hasFiles && (
        <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
            Uploaded Documents ({materials.length})
          </p>
          <div className="space-y-2">
            {materials.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-slate-300 bg-white transition-all text-xs"
              >
                <div className="flex items-center gap-3 min-w-0 pr-2">
                  <FileText size={18} className="text-slate-500 shrink-0" />
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900 truncate" title={item.original_filename}>
                      {item.original_filename}
                    </p>
                    <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                      <span>{formatFileSize(item.file_size_bytes)}</span>
                      {item.exam_type && <span>• {item.exam_type} ({item.year || 'N/A'})</span>}
                    </div>
                  </div>
                </div>

                {/* Actions & Processing Status */}
                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={item.processing_status} errorMsg={item.error_message} />

                  {/* Trigger Ingestion Pipeline */}
                  <button
                    onClick={(e) => handleIngest(item.id, e)}
                    disabled={ingestingId === item.id}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium text-[11px] shadow-2xs transition-all disabled:opacity-50"
                    title="Run end-to-end ingestion pipeline for this material"
                  >
                    {ingestingId === item.id ? (
                      <LoadingSpinner size={12} className="text-white" />
                    ) : (
                      <Play size={10} className="fill-current" />
                    )}
                    <span>Ingest</span>
                  </button>

                  {/* Inspect Pipeline Details */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onInspectPipeline(item);
                    }}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
                    title="Inspect pipeline stage details"
                  >
                    <Activity size={14} />
                  </button>

                  {/* Delete Material */}
                  <button
                    onClick={(e) => handleDelete(item.id, e)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                    title="Delete document"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
