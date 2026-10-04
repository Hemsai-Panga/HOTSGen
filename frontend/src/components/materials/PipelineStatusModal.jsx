import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { StatusBadge } from '../common/StatusBadge';
import { getPipelineStatus } from '../../api/materials';
import { Activity, Layers, CheckCircle2, XCircle, Clock, AlertCircle } from 'lucide-react';

export const PipelineStatusModal = ({ isOpen, onClose, material }) => {
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen && material?.id) {
      fetchStatus();
    }
  }, [isOpen, material?.id]);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPipelineStatus(material.id);
      setStatusData(data);
      setLoading(false);
    } catch (err) {
      setLoading(false);
      setError(err.response?.data?.detail || 'Failed to fetch pipeline status.');
    }
  };

  if (!material) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Ingestion Pipeline Status" maxWidth="max-w-xl">
      <div className="space-y-5">
        {/* Document Header */}
        <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Document</span>
            <StatusBadge status={material.processing_status} errorMsg={material.error_message} />
          </div>
          <p className="text-sm font-semibold text-slate-900 mt-1 truncate">{material.original_filename}</p>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-500">
            <LoadingSpinner size={24} />
            <span className="text-xs font-medium">Fetching multi-stage status...</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-medium flex items-center gap-2">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Pipeline Stages Breakdown */}
        {!loading && statusData && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-700 uppercase tracking-wider">
              <span>Pipeline Stages</span>
              <span className="text-slate-400 font-normal">
                {statusData.is_fully_ingested ? '● Completed' : 'In Progress'}
              </span>
            </div>

            <div className="space-y-2.5">
              {statusData.stages?.map((stage, idx) => {
                const isSuccess = stage.status === 'completed';
                const isFailed = stage.status === 'failed';
                const isRunning = stage.status === 'running';

                return (
                  <div
                    key={stage.stage}
                    className={`p-3 rounded-xl border flex items-center justify-between transition-colors ${
                      isSuccess
                        ? 'bg-emerald-50/40 border-emerald-200 text-emerald-900'
                        : isFailed
                        ? 'bg-rose-50/40 border-rose-200 text-rose-900'
                        : isRunning
                        ? 'bg-sky-50/40 border-sky-200 text-sky-900'
                        : 'bg-slate-50/40 border-slate-200 text-slate-500'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded-full bg-white border flex items-center justify-center text-xs font-bold text-slate-700 shadow-2xs">
                        {idx + 1}
                      </div>
                      <div>
                        <p className="text-xs font-semibold capitalize">
                          {stage.stage.replace(/_/g, ' ')}
                        </p>
                        <p className="text-[11px] text-slate-500">
                          {stage.message || 'Waiting to execute'}
                        </p>
                      </div>
                    </div>
                    <StatusBadge status={stage.status} errorMsg={stage.error} size="xs" />
                  </div>
                );
              })}
            </div>

            {/* Artifact Metrics */}
            <div className="grid grid-cols-3 gap-2 pt-2 text-center text-xs">
              <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Pages</span>
                <span className="text-sm font-bold text-slate-800">{statusData.extracted_page_count || 0}</span>
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">
                  {statusData.source_type === 'exam_paper' ? 'Questions' : 'Chunks'}
                </span>
                <span className="text-sm font-bold text-slate-800">
                  {statusData.source_type === 'exam_paper'
                    ? statusData.question_count || 0
                    : statusData.chunk_count || 0}
                </span>
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Embeddings</span>
                <span className="text-sm font-bold text-slate-800">{statusData.embeddings_count || 0}</span>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
};
