// app/static/js/components/NavMenu.jsx
import React from 'react';
import { Button } from '@ui/button';
import { cn } from '@lib/utils';
import AuthButton from './AuthButton';
import { useNavigation } from '@contexts/NavigationContext';

const NavMenu = ({ className }) => {
  const { activePage, setActivePage } = useNavigation();
  const navItems = ['Practice', 'Routines', 'Items', 'Imports'];

  return (
    <nav className={cn("flex items-center space-x-4 mb-8", className)}>
      <div className="flex space-x-4">
        {navItems.map((item) => (
          <Button
            key={item}
            variant={activePage === item ? "secondary" : "ghost"}
            className={cn(
              "text-xl py-6 px-8",
              activePage === item ? "bg-secondary hover:bg-secondary/90" : "hover:bg-accent"
            )}
            onClick={() => setActivePage(item)}
          >
            {item}
          </Button>
        ))}
      </div>
      <AuthButton />
    </nav>
  );
};

export default NavMenu;