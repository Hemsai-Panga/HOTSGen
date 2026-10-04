import apiClient from './client';

export const getCourses = async () => {
  const response = await apiClient.get('/dev/courses');
  return response.data;
};

export const getCourse = async (courseCode) => {
  const response = await apiClient.get(`/dev/courses/${courseCode}`);
  return response.data;
};

export const createCourse = async (courseData) => {
  const response = await apiClient.post('/dev/courses', {
    course_code: courseData.course_code.trim().toUpperCase(),
    course_name: courseData.course_name.trim(),
    description: courseData.description?.trim() || null,
  });
  return response.data;
};
