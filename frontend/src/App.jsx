import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, RequireAuth } from './context/AuthContext';
import { DeveloperLogin } from './pages/DeveloperLogin';
import { Dashboard } from './pages/Dashboard';
import { CourseMaterials } from './pages/CourseMaterials';
import { DeveloperLayout } from './components/layout/DeveloperLayout';

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public Login Route */}
        <Route path="/login" element={<DeveloperLogin />} />

        {/* Protected Developer Routes wrapped in DeveloperLayout */}
        <Route
          element={
            <RequireAuth>
              <DeveloperLayout />
            </RequireAuth>
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/courses" element={<Dashboard />} />
          <Route path="/courses/:courseCode" element={<CourseMaterials />} />
        </Route>

        {/* Root and Fallback Route */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
