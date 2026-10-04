import apiClient from './client';

export const loginDeveloper = async (username, password) => {
  const response = await apiClient.post('/auth/login', {
    username: username.trim(),
    password,
  });
  return response.data;
};
