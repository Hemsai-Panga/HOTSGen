import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { CourseMaterials } from '../pages/CourseMaterials';
import { AuthProvider } from '../context/AuthContext';
import * as coursesApi from '../api/courses';
import * as materialsApi from '../api/materials';

vi.mock('../api/courses', () => ({
  getCourse: vi.fn(),
}));

vi.mock('../api/materials', () => ({
  getMaterials: vi.fn(),
  uploadMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
  ingestMaterial: vi.fn(),
  getPipelineStatus: vi.fn(),
}));

describe('CourseMaterials Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockCourse = {
    id: 'c1',
    course_code: 'BCSE301',
    course_name: 'Database Management Systems',
    description: 'Relational databases and SQL',
  };

  const mockMaterials = [
    {
      id: 'mat-1',
      original_filename: 'BCSE301_Syllabus.pdf',
      source_type: 'syllabus',
      file_size_bytes: 512000,
      processing_status: 'processed',
      course_code: 'BCSE301',
    },
    {
      id: 'mat-2',
      original_filename: 'BCSE301_Module1.pptx',
      source_type: 'lecture_material',
      file_size_bytes: 2048000,
      processing_status: 'completed',
      course_code: 'BCSE301',
    },
  ];

  it('renders course information, readiness panel, and 4 sequential upload sections', async () => {
    coursesApi.getCourse.mockResolvedValueOnce(mockCourse);
    materialsApi.getMaterials.mockResolvedValueOnce(mockMaterials);

    render(
      <MemoryRouter initialEntries={['/courses/BCSE301']}>
        <AuthProvider>
          <Routes>
            <Route path="/courses/:courseCode" element={<CourseMaterials />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: 'Database Management Systems' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: 'Course Status' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: 'Course Syllabus' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: 'Lecture Materials & Slide Decks' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: 'Reference Books & Academic Notes' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3, name: 'CAT / CAT2 / FAT Examination Papers' })).toBeInTheDocument();
    });
  });
});
