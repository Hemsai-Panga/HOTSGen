import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { Dashboard } from '../pages/Dashboard';
import { AuthProvider } from '../context/AuthContext';
import * as coursesApi from '../api/courses';
import * as materialsApi from '../api/materials';

vi.mock('../api/courses', () => ({
  getCourses: vi.fn(),
  createCourse: vi.fn(),
}));

vi.mock('../api/materials', () => ({
  getMaterials: vi.fn(),
}));

describe('Dashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    coursesApi.getCourses.mockReturnValue(new Promise(() => {}));

    render(
      <BrowserRouter>
        <AuthProvider>
          <Dashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText(/Loading course catalog/i)).toBeInTheDocument();
  });

  it('renders "No courses available" empty state when no courses exist', async () => {
    coursesApi.getCourses.mockResolvedValueOnce([]);

    render(
      <BrowserRouter>
        <AuthProvider>
          <Dashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/No courses available/i)).toBeInTheDocument();
      expect(screen.getByText(/Get started by registering a new course/i)).toBeInTheDocument();
    });
  });

  it('renders list of courses in a grid when courses exist', async () => {
    coursesApi.getCourses.mockResolvedValueOnce([
      {
        id: '1',
        course_code: 'BCSE301',
        course_name: 'Database Management Systems',
        description: 'DBMS course',
      },
      {
        id: '2',
        course_code: 'BCSE302',
        course_name: 'Operating Systems',
        description: 'OS course',
      },
    ]);
    materialsApi.getMaterials.mockResolvedValue([]);

    render(
      <BrowserRouter>
        <AuthProvider>
          <Dashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('BCSE301')).toBeInTheDocument();
      expect(screen.getByText('Database Management Systems')).toBeInTheDocument();
      expect(screen.getByText('BCSE302')).toBeInTheDocument();
      expect(screen.getByText('Operating Systems')).toBeInTheDocument();
    });
  });

  it('opens Add Course modal when "Add Course" button is clicked', async () => {
    coursesApi.getCourses.mockResolvedValueOnce([]);

    render(
      <BrowserRouter>
        <AuthProvider>
          <Dashboard />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/No courses available/i)).toBeInTheDocument();
    });

    const addBtn = screen.getAllByRole('button', { name: /Add Course/i })[0];
    fireEvent.click(addBtn);

    expect(screen.getByText(/Add New Course/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e\.g\. BCSE301/i)).toBeInTheDocument();
  });
});
