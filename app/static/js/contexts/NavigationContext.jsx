// app/static/js/contexts/NavigationContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { trackPageVisit } from '../utils/analytics';

const NavigationContext = createContext(undefined);

export const NavigationProvider = ({ children }) => {
  const [activePage, setActivePage] = useState('Practice');

  // Track initial page load
  useEffect(() => {
    trackPageVisit(activePage);
  }, []);

  // Enhanced setActivePage that includes analytics tracking
  const setActivePageWithTracking = (pageName) => {
    setActivePage(pageName);
    trackPageVisit(pageName);
  };

  return (
    <NavigationContext.Provider value={{ 
      activePage, 
      setActivePage: setActivePageWithTracking 
    }}>
      {children}
    </NavigationContext.Provider>
  );
};

export const useNavigation = () => {
  const context = useContext(NavigationContext);
  if (context === undefined) {
    throw new Error('useNavigation must be used within a NavigationProvider');
  }
  return context;
};
