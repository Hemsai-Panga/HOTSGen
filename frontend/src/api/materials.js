import apiClient from './client';

export const getMaterials = async (courseCode) => {
  const params = courseCode ? { course_code: courseCode } : {};
  const response = await apiClient.get('/dev/materials', { params });
  return response.data;
};

export const getMaterial = async (materialId) => {
  const response = await apiClient.get(`/dev/materials/${materialId}`);
  return response.data;
};

export const uploadMaterial = async (formData) => {
  const response = await apiClient.post('/dev/materials', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const deleteMaterial = async (materialId) => {
  const response = await apiClient.delete(`/dev/materials/${materialId}`);
  return response.data;
};

export const ingestMaterial = async (materialId) => {
  const response = await apiClient.post(`/dev/materials/${materialId}/ingest`);
  return response.data;
};

export const getPipelineStatus = async (materialId) => {
  const response = await apiClient.get(`/dev/materials/${materialId}/pipeline-status`);
  return response.data;
};
