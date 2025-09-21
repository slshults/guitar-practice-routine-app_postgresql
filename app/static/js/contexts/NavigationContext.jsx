// app/static/js/contexts/NavigationContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { trackPageVisit } from '../utils/analytics';

const NavigationContext = createContext(undefined);

export const NavigationProvider = ({ children }) => {
  // Initialize from URL hash or default to 'Practice'
  const getInitialPage = () => {
    const hash = window.location.hash.slice(1); // Remove the #
    const validPages = ['Practice', 'Routines', 'Items'];
    return validPages.includes(hash) ? hash : 'Practice';
  };

  const [activePage, setActivePage] = useState(getInitialPage);

  // Track initial page load
  useEffect(() => {
    trackPageVisit(activePage);
  }, []);

  // Enhanced setActivePage that includes analytics tracking and URL sync
  const setActivePageWithTracking = (pageName, updateHistory = true) => {
    setActivePage(pageName);
    trackPageVisit(pageName);

    // Update URL hash to reflect current page
    if (updateHistory) {
      window.history.pushState(null, '', `#${pageName}`);
    }
  };

  // Listen for browser back/forward button
  useEffect(() => {
    const handlePopState = () => {
      const newPage = getInitialPage();
      // Update state without creating new history entry
      setActivePageWithTracking(newPage, false);
    };

    window.addEventListener('popstate', handlePopState);

    // Cleanup listener
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

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
