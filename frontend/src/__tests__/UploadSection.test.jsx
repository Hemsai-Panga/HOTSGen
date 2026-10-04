import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UploadSection } from '../components/materials/UploadSection';
import * as materialsApi from '../api/materials';

vi.mock('../api/materials', () => ({
  uploadMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
  ingestMaterial: vi.fn(),
  getPipelineStatus: vi.fn(),
}));

describe('UploadSection Component', () => {
  const onMaterialUpdated = vi.fn();
  const onInspectPipeline = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockMaterials = [
    {
      id: 'mat-1',
      original_filename: 'Lecture1_Introduction.pdf',
      source_type: 'lecture_material',
      file_size_bytes: 1048576,
      processing_status: 'uploaded',
      course_code: 'BCSE301',
    },
  ];

  it('renders step number, title, description, and files list', () => {
    render(
      <UploadSection
        stepNumber="2"
        title="Lecture Materials"
        subtitle="Upload lecture slides and PPTs"
        sourceType="lecture_material"
        courseCode="BCSE301"
        materials={mockMaterials}
        onMaterialUpdated={onMaterialUpdated}
        onInspectPipeline={onInspectPipeline}
      />
    );

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Lecture Materials')).toBeInTheDocument();
    expect(screen.getByText('Upload lecture slides and PPTs')).toBeInTheDocument();
    expect(screen.getByText(/Lecture1_Introduction.pdf/i)).toBeInTheDocument();
  });

  it('renders exam metadata inputs when sourceType is exam_paper', () => {
    render(
      <UploadSection
        stepNumber="4"
        title="CAT / FAT Exam Papers"
        subtitle="Upload previous semester question papers"
        sourceType="exam_paper"
        courseCode="BCSE301"
        materials={[]}
        onMaterialUpdated={onMaterialUpdated}
        onInspectPipeline={onInspectPipeline}
      />
    );

    expect(screen.getByText(/Exam Type:/i)).toBeInTheDocument();
    expect(screen.getByText(/Year:/i)).toBeInTheDocument();
  });

  it('triggers ingestion pipeline when "Ingest" button is clicked', async () => {
    materialsApi.ingestMaterial.mockResolvedValueOnce({
      material_id: 'mat-1',
      status: 'completed',
      results: {},
    });

    render(
      <UploadSection
        stepNumber="2"
        title="Lecture Materials"
        subtitle="Upload lecture slides and PPTs"
        sourceType="lecture_material"
        courseCode="BCSE301"
        materials={mockMaterials}
        onMaterialUpdated={onMaterialUpdated}
        onInspectPipeline={onInspectPipeline}
      />
    );

    const ingestBtn = screen.getByRole('button', { name: /Ingest/i });
    fireEvent.click(ingestBtn);

    await waitFor(() => {
      expect(materialsApi.ingestMaterial).toHaveBeenCalledWith('mat-1');
      expect(onMaterialUpdated).toHaveBeenCalled();
    });
  });

  it('triggers pipeline status modal when inspect activity button is clicked', () => {
    render(
      <UploadSection
        stepNumber="2"
        title="Lecture Materials"
        subtitle="Upload lecture slides and PPTs"
        sourceType="lecture_material"
        courseCode="BCSE301"
        materials={mockMaterials}
        onMaterialUpdated={onMaterialUpdated}
        onInspectPipeline={onInspectPipeline}
      />
    );

    const inspectBtn = screen.getByTitle(/Inspect pipeline stage details/i);
    fireEvent.click(inspectBtn);

    expect(onInspectPipeline).toHaveBeenCalledWith(mockMaterials[0]);
  });
});
