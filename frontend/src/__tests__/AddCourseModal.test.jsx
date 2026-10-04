import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AddCourseModal } from '../components/dashboard/AddCourseModal';
import * as coursesApi from '../api/courses';

vi.mock('../api/courses', () => ({
  createCourse: vi.fn(),
}));

describe('AddCourseModal Component', () => {
  const onCourseCreated = vi.fn();
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders input fields for course code, title, and description', () => {
    render(
      <AddCourseModal isOpen={true} onClose={onClose} onCourseCreated={onCourseCreated} />
    );

    expect(screen.getByText('Add New Course')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e\.g\. BCSE301/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e\.g\. Database Management Systems/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Brief description/i)).toBeInTheDocument();
  });

  it('submits form with valid course data', async () => {
    const createdCourse = {
      id: 'course-123',
      course_code: 'BCSE301',
      course_name: 'Database Management Systems',
      description: 'DBMS fundamentals',
      units: [],
    };
    coursesApi.createCourse.mockResolvedValueOnce(createdCourse);

    render(
      <AddCourseModal isOpen={true} onClose={onClose} onCourseCreated={onCourseCreated} />
    );

    fireEvent.change(screen.getByPlaceholderText(/e\.g\. BCSE301/i), {
      target: { value: 'BCSE301' },
    });
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. Database Management Systems/i), {
      target: { value: 'Database Management Systems' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Brief description/i), {
      target: { value: 'DBMS fundamentals' },
    });

    const submitBtn = screen.getByRole('button', { name: /Create Course/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(coursesApi.createCourse).toHaveBeenCalledWith({
        course_code: 'BCSE301',
        course_name: 'Database Management Systems',
        description: 'DBMS fundamentals',
      });
      expect(onCourseCreated).toHaveBeenCalledWith(createdCourse);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('displays error message when creation fails', async () => {
    coursesApi.createCourse.mockRejectedValueOnce({
      response: { data: { detail: 'Course with code BCSE301 already exists' } },
    });

    render(
      <AddCourseModal isOpen={true} onClose={onClose} onCourseCreated={onCourseCreated} />
    );

    fireEvent.change(screen.getByPlaceholderText(/e\.g\. BCSE301/i), {
      target: { value: 'BCSE301' },
    });
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. Database Management Systems/i), {
      target: { value: 'Database Management Systems' },
    });

    const submitBtn = screen.getByRole('button', { name: /Create Course/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Course with code BCSE301 already exists/i)).toBeInTheDocument();
    });
  });
});
