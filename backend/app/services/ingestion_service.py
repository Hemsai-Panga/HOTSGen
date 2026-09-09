"""Ingestion pipeline service orchestrating end-to-end processing across all stages."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.material import MaterialInDB, ProcessingStatus, SourceType
from app.models.pipeline import (
    IngestionPipelineResponse,
    IngestionStatusResponse,
    PipelineStageResult,
    StageName,
    StageStatus,
)
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.syllabus_alignment_repository import SyllabusAlignmentRepository
from app.repositories.teaching_question_repository import TeachingQuestionRepository
from app.services.chunk_service import ChunkService
from app.services.document_processing_service import DocumentProcessingService
from app.services.embedding_service import EmbeddingService
from app.services.material_service import MaterialNotFoundError
from app.services.syllabus_alignment_service import SyllabusAlignmentService
from app.services.syllabus_service import SyllabusService
from app.services.teaching_question_service import TeachingQuestionService

logger = logging.getLogger(__name__)


class IngestionPipelineError(Exception):
    """Base exception for ingestion pipeline orchestrator."""
    pass


class InvalidMaterialSourceTypeForPipelineError(IngestionPipelineError):
    """Raised when an unsupported material source type is triggered in pipeline."""
    pass


class IngestionPipelineService:
    """Orchestrates end-to-end document ingestion from extraction through vector embedding."""

    @staticmethod
    def _get_pipeline_stages(source_type: SourceType) -> List[StageName]:
        """Determine sequential pipeline stages based on source material category."""
        if source_type in (SourceType.LECTURE_MATERIAL, SourceType.REFERENCE_BOOK):
            return [
                StageName.EXTRACTION,
                StageName.SYLLABUS_ALIGNMENT,
                StageName.CHUNKING,
                StageName.EMBEDDINGS,
            ]
        elif source_type == SourceType.EXAM_PAPER:
            return [
                StageName.EXTRACTION,
                StageName.QUESTION_STRUCTURING,
                StageName.EMBEDDINGS,
            ]
        elif source_type == SourceType.SYLLABUS:
            return [
                StageName.EXTRACTION,
                StageName.SYLLABUS_ANALYSIS,
            ]
        else:
            raise InvalidMaterialSourceTypeForPipelineError(
                f"Unsupported source type '{source_type}' for ingestion pipeline."
            )

    @classmethod
    def run_ingestion_pipeline(cls, material_id: str) -> IngestionPipelineResponse:
        """
        Execute the full ingestion pipeline for a material in sequential order.
        Guarantees idempotent replacement of derived artifacts on re-run.
        """
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        pipeline_start = datetime.now(timezone.utc)
        stage_names = cls._get_pipeline_stages(material.source_type)

        # Mark material as processing
        MaterialRepository.update_material_status(material_id, ProcessingStatus.PROCESSING)

        stage_results: List[PipelineStageResult] = [
            PipelineStageResult(stage=name, status=StageStatus.PENDING)
            for name in stage_names
        ]

        logger.info(
            f"Starting ingestion pipeline for material '{material_id}' "
            f"(course='{material.course_code}', source_type='{material.source_type.value}', "
            f"stages={[s.value for s in stage_names]})."
        )

        for i, stage_name in enumerate(stage_names):
            current_stage_res = stage_results[i]
            current_stage_res.status = StageStatus.RUNNING
            current_stage_res.started_at = datetime.now(timezone.utc)

            try:
                # Dispatch stage execution
                if stage_name == StageName.EXTRACTION:
                    extract_res = DocumentProcessingService.process_material(material_id)
                    current_stage_res.details = {
                        "page_count": extract_res.page_count,
                        "total_characters": extract_res.total_characters,
                        "has_ocr_content": extract_res.has_ocr_content,
                    }
                    current_stage_res.message = f"Extracted {extract_res.page_count} pages of text."

                elif stage_name == StageName.SYLLABUS_ANALYSIS:
                    syllabus_res = SyllabusService.analyze_syllabus(material_id)
                    current_stage_res.details = {
                        "units_count": len(syllabus_res.units),
                    }
                    current_stage_res.message = f"Analyzed syllabus structure ({len(syllabus_res.units)} units)."

                elif stage_name == StageName.SYLLABUS_ALIGNMENT:
                    align_res = SyllabusAlignmentService.align_material(material_id)
                    current_stage_res.details = {
                        "total_segments": align_res.total_segments,
                        "in_syllabus_count": align_res.in_syllabus_count,
                        "out_of_syllabus_count": align_res.out_of_syllabus_count,
                        "ambiguous_count": align_res.ambiguous_count,
                    }
                    current_stage_res.message = (
                        f"Aligned {align_res.total_segments} segments "
                        f"({align_res.in_syllabus_count} in-syllabus)."
                    )

                elif stage_name == StageName.CHUNKING:
                    chunk_res = ChunkService.chunk_material(material_id)
                    current_stage_res.details = {
                        "total_chunks": chunk_res.total_chunks,
                        "total_tokens": chunk_res.total_tokens,
                    }
                    current_stage_res.message = f"Prepared {chunk_res.total_chunks} context chunks."

                elif stage_name == StageName.QUESTION_STRUCTURING:
                    q_res = TeachingQuestionService.extract_questions_from_material(material_id)
                    current_stage_res.details = {
                        "questions_extracted": q_res.questions_extracted,
                        "exam_type": q_res.exam_type.value if q_res.exam_type else None,
                        "year": q_res.year,
                    }
                    current_stage_res.message = f"Extracted {q_res.questions_extracted} exam questions."

                elif stage_name == StageName.EMBEDDINGS:
                    emb_res = EmbeddingService.generate_material_embeddings(material_id)
                    current_stage_res.details = {
                        "embedded_count": emb_res.embedded_count,
                        "dimension": emb_res.dimension,
                    }
                    current_stage_res.message = f"Generated {emb_res.embedded_count} vector embeddings."

                current_stage_res.status = StageStatus.COMPLETED
                current_stage_res.completed_at = datetime.now(timezone.utc)

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                logger.error(
                    f"Pipeline failed at stage '{stage_name.value}' for material '{material_id}': {error_msg}",
                    exc_info=True,
                )
                current_stage_res.status = StageStatus.FAILED
                current_stage_res.error = error_msg
                current_stage_res.completed_at = datetime.now(timezone.utc)

                # Mark remaining stages as skipped
                for j in range(i + 1, len(stage_names)):
                    stage_results[j].status = StageStatus.SKIPPED
                    stage_results[j].message = f"Skipped due to failure at stage '{stage_name.value}'."

                # Update material status in DB
                MaterialRepository.update_material_status(
                    material_id,
                    ProcessingStatus.FAILED,
                    error_message=f"Pipeline failed at stage '{stage_name.value}': {str(e)}",
                )

                return IngestionPipelineResponse(
                    material_id=material_id,
                    course_code=material.course_code,
                    source_type=material.source_type.value,
                    overall_status="failed",
                    current_stage=stage_name,
                    stages=stage_results,
                    started_at=pipeline_start,
                    completed_at=datetime.now(timezone.utc),
                    error_message=f"Stage '{stage_name.value}' failed: {str(e)}",
                )

        # All stages completed successfully
        MaterialRepository.update_material_status(material_id, ProcessingStatus.COMPLETED, error_message="")
        logger.info(f"Ingestion pipeline completed successfully for material '{material_id}'.")

        return IngestionPipelineResponse(
            material_id=material_id,
            course_code=material.course_code,
            source_type=material.source_type.value,
            overall_status="completed",
            stages=stage_results,
            started_at=pipeline_start,
            completed_at=datetime.now(timezone.utc),
            error_message=None,
        )

    @classmethod
    def get_pipeline_status(cls, material_id: str) -> IngestionStatusResponse:
        """
        Inspect the complete multi-stage status and metric counts for a material.
        """
        material = MaterialRepository.get_material(material_id)
        if not material:
            raise MaterialNotFoundError(f"Material with ID '{material_id}' not found.")

        stage_names = cls._get_pipeline_stages(material.source_type)

        # 1. Fetch artifacts from repositories
        extracted = ExtractedContentRepository.get_content_by_material(material_id)
        page_count = len(extracted) if extracted else 0

        alignments = SyllabusAlignmentRepository.get_alignments_by_material(material_id)
        alignment_count = len(alignments)

        chunks = ChunkRepository.get_chunks_by_material(material_id)
        chunk_count = len(chunks)

        questions = TeachingQuestionRepository.get_questions_by_material(material_id)
        question_count = len(questions)

        # Compute embeddings count based on source type
        embeddings_count = 0
        if material.source_type in (SourceType.LECTURE_MATERIAL, SourceType.REFERENCE_BOOK):
            embeddings_count = sum(1 for c in chunks if c.embedding is not None)
        elif material.source_type == SourceType.EXAM_PAPER:
            embeddings_count = sum(1 for q in questions if q.embedding is not None)

        # 2. Derive individual stage statuses
        stage_results: List[PipelineStageResult] = []
        for name in stage_names:
            if name == StageName.EXTRACTION:
                if page_count > 0:
                    status = StageStatus.COMPLETED
                    msg = f"Extracted {page_count} pages."
                elif material.processing_status == ProcessingStatus.FAILED:
                    status = StageStatus.FAILED
                    msg = "Extraction failed or produced no content."
                else:
                    status = StageStatus.PENDING
                    msg = "Not yet extracted."
                stage_results.append(PipelineStageResult(
                    stage=name,
                    status=status,
                    message=msg,
                    details={"page_count": page_count},
                ))

            elif name == StageName.SYLLABUS_ANALYSIS:
                course = CourseRepository.get_course(material.course_code)
                units_count = len(course.units) if course and course.units else 0
                if units_count > 0 and page_count > 0:
                    status = StageStatus.COMPLETED
                    msg = f"Syllabus structure contains {units_count} units."
                else:
                    status = StageStatus.PENDING
                    msg = "Syllabus not yet analyzed."
                stage_results.append(PipelineStageResult(
                    stage=name,
                    status=status,
                    message=msg,
                    details={"units_count": units_count},
                ))

            elif name == StageName.SYLLABUS_ALIGNMENT:
                if alignment_count > 0:
                    status = StageStatus.COMPLETED
                    msg = f"{alignment_count} segments aligned."
                else:
                    status = StageStatus.PENDING
                    msg = "No segments aligned."
                stage_results.append(PipelineStageResult(
                    stage=name,
                    status=status,
                    message=msg,
                    details={"alignment_count": alignment_count},
                ))

            elif name == StageName.CHUNKING:
                if chunk_count > 0:
                    status = StageStatus.COMPLETED
                    msg = f"{chunk_count} chunks prepared."
                else:
                    status = StageStatus.PENDING
                    msg = "No chunks prepared."
                stage_results.append(PipelineStageResult(
                    stage=name,
                    status=status,
                    message=msg,
                    details={"chunk_count": chunk_count},
                ))

            elif name == StageName.QUESTION_STRUCTURING:
                if question_count > 0:
                    status = StageStatus.COMPLETED
                    msg = f"{question_count} exam questions extracted."
                else:
                    status = StageStatus.PENDING
                    msg = "No questions extracted."
                stage_results.append(PipelineStageResult(
                    stage=name,
                    status=status,
                    message=msg,
                    details={"question_count": question_count},
                ))

            elif name == StageName.EMBEDDINGS:
                total_target = chunk_count if material.source_type != SourceType.EXAM_PAPER else question_count
                if total_target > 0 and embeddings_count == total_target:
                    status = StageStatus.COMPLETED
                    msg = f"{embeddings_count}/{total_target} embeddings generated."
                elif embeddings_count > 0:
                    status = StageStatus.RUNNING
                    msg = f"{embeddings_count}/{total_target} embeddings generated."
                else:
                    status = StageStatus.PENDING
                    msg = "No embeddings generated."
                stage_results.append(PipelineStageResult(
                    stage=name,
                    status=status,
                    message=msg,
                    details={"embeddings_count": embeddings_count, "total_target": total_target},
                ))

        # 3. Determine if fully ingested
        is_fully_ingested = False
        if material.source_type in (SourceType.LECTURE_MATERIAL, SourceType.REFERENCE_BOOK):
            is_fully_ingested = (
                page_count > 0
                and chunk_count > 0
                and chunk_count == embeddings_count
                and material.processing_status in (ProcessingStatus.COMPLETED, ProcessingStatus.PROCESSED)
            )
        elif material.source_type == SourceType.EXAM_PAPER:
            is_fully_ingested = (
                page_count > 0
                and question_count > 0
                and question_count == embeddings_count
                and material.processing_status in (ProcessingStatus.COMPLETED, ProcessingStatus.PROCESSED)
            )
        elif material.source_type == SourceType.SYLLABUS:
            is_fully_ingested = (
                page_count > 0
                and material.processing_status in (ProcessingStatus.COMPLETED, ProcessingStatus.PROCESSED)
            )

        return IngestionStatusResponse(
            material_id=material_id,
            course_code=material.course_code,
            source_type=material.source_type.value,
            processing_status=material.processing_status.value if hasattr(material.processing_status, "value") else str(material.processing_status),
            stages=stage_results,
            extracted_page_count=page_count,
            alignment_segment_count=alignment_count,
            chunk_count=chunk_count,
            question_count=question_count,
            embeddings_count=embeddings_count,
            is_fully_ingested=is_fully_ingested,
            last_error=material.error_message,
            updated_at=material.updated_at,
        )
