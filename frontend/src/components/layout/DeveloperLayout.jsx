import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from '../common/Header';
import { Sidebar } from '../common/Sidebar';

export const DeveloperLayout = () => {
  return (
    <div className="min-h-screen bg-white flex flex-col font-sans">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-7xl mx-auto w-full bg-white overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
