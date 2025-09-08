import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname, 'app/static/js'),
  base: '/static/',
  build: {
    outDir: path.resolve(__dirname, 'app/static'),
    emptyOutDir: false,
    sourcemap: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'app/static/js/main.jsx')
      },
      output: {
        format: 'es',
        entryFileNames: 'js/[name].js',
        chunkFileNames: 'js/[name].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name.endsWith('.css')) {
            return 'css/[name][extname]';
          }
          return '[name][extname]';
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'app/static/js'),
      '@components': path.resolve(__dirname, 'app/static/js/components'),
      '@ui': path.resolve(__dirname, 'app/static/js/components/ui'),
      '@lib': path.resolve(__dirname, 'app/static/js/lib'),
      '@hooks': path.resolve(__dirname, 'app/static/js/hooks'),
      '@contexts': path.resolve(__dirname, 'app/static/js/contexts')
    }
  },
  optimizeDeps: {
    include: ['react', 'react-dom']
  }
});