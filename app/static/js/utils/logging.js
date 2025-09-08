// Frontend logging utility that sends logs to backend
export const serverLog = async (message, level = 'DEBUG', context = {}) => {
  try {
    await fetch('/api/debug/log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        level,
        context
      })
    });
  } catch (error) {
    // Fallback to console if server logging fails
    console.error('Failed to send log to server:', error);
    console.log(`[${level}] ${message}`, context);
  }
};

// Override console methods to also send to server
const originalConsoleLog = console.log;
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

console.log = function(...args) {
  originalConsoleLog.apply(console, args);
  // Send to server (but don't wait for it)
  serverLog(args.join(' '), 'INFO', {}).catch(() => {});
};

console.error = function(...args) {
  originalConsoleError.apply(console, args);
  // Send to server (but don't wait for it)
  serverLog(args.join(' '), 'ERROR', {}).catch(() => {});
};

console.warn = function(...args) {
  originalConsoleWarn.apply(console, args);
  // Send to server (but don't wait for it)
  serverLog(args.join(' '), 'WARNING', {}).catch(() => {});
};

export const serverDebug = (message, context) => serverLog(message, 'DEBUG', context);
export const serverInfo = (message, context) => serverLog(message, 'INFO', context);
export const serverError = (message, context) => serverLog(message, 'ERROR', context);