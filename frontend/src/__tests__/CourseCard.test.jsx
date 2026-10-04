import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { CourseCard } from '../components/dashboard/CourseCard';

describe('CourseCard Component', () => {
  const mockCourse = {
    id: 'c1',
    course_code: 'BCSE301',
    course_name: 'Database Management Systems',
    description: 'Relational database systems',
  };

  const completeMaterials = [
    { id: 'm1', source_type: 'syllabus', processing_status: 'completed' },
    { id: 'm2', source_type: 'lecture_material', processing_status: 'completed' },
    { id: 'm3', source_type: 'reference_book', processing_status: 'completed' },
    { id: 'm4', source_type: 'exam_paper', processing_status: 'completed' },
  ];

  const partialMaterials = [
    { id: 'm1', source_type: 'syllabus', processing_status: 'completed' },
    { id: 'm2', source_type: 'lecture_material', processing_status: 'completed' },
  ];

  const failedMaterials = [
    { id: 'm1', source_type: 'syllabus', processing_status: 'completed' },
    { id: 'm2', source_type: 'lecture_material', processing_status: 'failed' },
    { id: 'm3', source_type: 'reference_book', processing_status: 'completed' },
    { id: 'm4', source_type: 'exam_paper', processing_status: 'completed' },
  ];

  const pendingMaterials = [
    { id: 'm1', source_type: 'syllabus', processing_status: 'completed' },
    { id: 'm2', source_type: 'lecture_material', processing_status: 'uploaded' },
    { id: 'm3', source_type: 'reference_book', processing_status: 'completed' },
    { id: 'm4', source_type: 'exam_paper', processing_status: 'completed' },
  ];

  it('renders course code and course name', () => {
    render(
      <BrowserRouter>
        <CourseCard course={mockCourse} materials={completeMaterials} />
      </BrowserRouter>
    );

    expect(screen.getByText('BCSE301')).toBeInTheDocument();
    expect(screen.getByText('Database Management Systems')).toBeInTheDocument();
  });

  it('displays full readiness badge when all 4 categories are completed', () => {
    render(
      <BrowserRouter>
        <CourseCard course={mockCourse} materials={completeMaterials} />
      </BrowserRouter>
    );

    expect(screen.getByText(/4\/4 complete/i)).toBeInTheDocument();
    expect(screen.getByText(/Ready/i)).toBeInTheDocument();
  });

  it('displays incomplete readiness badge when some categories are missing', () => {
    render(
      <BrowserRouter>
        <CourseCard course={mockCourse} materials={partialMaterials} />
      </BrowserRouter>
    );

    expect(screen.getByText(/2\/4 complete/i)).toBeInTheDocument();
    expect(screen.getByText(/Incomplete/i)).toBeInTheDocument();
  });

  it('displays incomplete readiness badge when a category material has failed processing', () => {
    render(
      <BrowserRouter>
        <CourseCard course={mockCourse} materials={failedMaterials} />
      </BrowserRouter>
    );

    expect(screen.getByText(/3\/4 complete/i)).toBeInTheDocument();
    expect(screen.getByText(/Incomplete/i)).toBeInTheDocument();
  });

  it('displays incomplete readiness badge when a category material is pending/uploaded', () => {
    render(
      <BrowserRouter>
        <CourseCard course={mockCourse} materials={pendingMaterials} />
      </BrowserRouter>
    );

    expect(screen.getByText(/3\/4 complete/i)).toBeInTheDocument();
    expect(screen.getByText(/Incomplete/i)).toBeInTheDocument();
  });

  it('has clickable button role with navigation trigger', () => {
    render(
      <BrowserRouter>
        <CourseCard course={mockCourse} materials={completeMaterials} />
      </BrowserRouter>
    );

    const card = screen.getByRole('button');
    expect(card).toBeInTheDocument();
  });
});
