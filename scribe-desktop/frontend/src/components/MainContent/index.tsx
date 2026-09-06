'use client';

import React from 'react';

interface MainContentProps {
  children: React.ReactNode;
}

const MainContent: React.FC<MainContentProps> = ({ children }) => {
  return (
    <main className="flex-1 min-w-0 h-screen">
      {children}
    </main>
  );
};

export default MainContent;
