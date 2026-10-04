import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CourseReadiness } from '../components/materials/CourseReadiness';

describe('CourseReadiness Component', () => {
  it('displays ready status when all 4 material categories are successfully completed', () => {
    const materials = [
      { id: '1', source_type: 'syllabus', processing_status: 'completed' },
      { id: '2', source_type: 'lecture_material', processing_status: 'completed' },
      { id: '3', source_type: 'reference_book', processing_status: 'completed' },
      { id: '4', source_type: 'exam_paper', processing_status: 'completed' },
    ];

    render(<CourseReadiness materials={materials} courseCode="BCSE301" />);

    expect(screen.getByText(/Course Status/i)).toBeInTheDocument();
    expect(screen.getByText(/4 of 4 categories/i)).toBeInTheDocument();
    expect(screen.getByText(/Ready for Question Generation/i)).toBeInTheDocument();
  });

  it('displays incomplete status when material categories are missing', () => {
    const materials = [
      { id: '1', source_type: 'syllabus', processing_status: 'completed' },
      { id: '2', source_type: 'lecture_material', processing_status: 'completed' },
    ];

    render(<CourseReadiness materials={materials} courseCode="BCSE301" />);

    expect(screen.getByText(/2 of 4 categories/i)).toBeInTheDocument();
    expect(screen.getByText(/Course Incomplete/i)).toBeInTheDocument();
  });

  it('displays incomplete status when any category has failed material processing', () => {
    const materials = [
      { id: '1', source_type: 'syllabus', processing_status: 'completed' },
      { id: '2', source_type: 'lecture_material', processing_status: 'failed' },
      { id: '3', source_type: 'reference_book', processing_status: 'completed' },
      { id: '4', source_type: 'exam_paper', processing_status: 'completed' },
    ];

    render(<CourseReadiness materials={materials} courseCode="BCSE301" />);

    expect(screen.getByText(/3 of 4 categories/i)).toBeInTheDocument();
    expect(screen.getByText(/Course Incomplete/i)).toBeInTheDocument();
  });

  it('displays incomplete status when any category is still pending/uploaded', () => {
    const materials = [
      { id: '1', source_type: 'syllabus', processing_status: 'completed' },
      { id: '2', source_type: 'lecture_material', processing_status: 'uploaded' },
      { id: '3', source_type: 'reference_book', processing_status: 'completed' },
      { id: '4', source_type: 'exam_paper', processing_status: 'completed' },
    ];

    render(<CourseReadiness materials={materials} courseCode="BCSE301" />);

    expect(screen.getByText(/3 of 4 categories/i)).toBeInTheDocument();
    expect(screen.getByText(/Course Incomplete/i)).toBeInTheDocument();
  });
});
