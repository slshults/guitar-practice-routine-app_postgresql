// Connection status tracking
let isServerDown = false;
let lastConnectionAttempt = 0;
let connectionCheckInterval = null;
const CONNECTION_CHECK_DELAY = 30000; // 30 seconds between reconnection attempts

// Frontend logging utility that sends logs to backend
export const serverLog = async (message, level = 'DEBUG', context = {}) => {
  // Skip sending to server if we know it's down and haven't waited long enough
  if (isServerDown && Date.now() - lastConnectionAttempt < CONNECTION_CHECK_DELAY) {
    return;
  }

  try {
    const response = await fetch('/api/debug/log', {
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

    if (response.ok && isServerDown) {
      // Server is back up!
      isServerDown = false;
      hideConnectionModal();
      if (connectionCheckInterval) {
        clearInterval(connectionCheckInterval);
        connectionCheckInterval = null;
      }
    }
  } catch (error) {
    // Use original console methods to avoid recursive loop
    if (!isServerDown) {
      isServerDown = true;
      lastConnectionAttempt = Date.now();
      showConnectionModal();
      scheduleReconnectionAttempts();
    }
    // Use original console methods to prevent recursion
    originalConsoleError('Failed to send log to server:', error);
    originalConsoleLog(`[${level}] ${message}`, context);
  }
};

// Override console methods to also send to server
const originalConsoleLog = console.log;
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

// Connection status modal functions
function showConnectionModal() {
  // Remove any existing modal
  hideConnectionModal();

  const modal = document.createElement('div');
  modal.id = 'connection-status-modal';
  modal.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #ef4444;
    color: white;
    padding: 16px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 10000;
    max-width: 400px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.4;
  `;

  modal.innerHTML = `
    <div style="font-weight: 600; margin-bottom: 8px;">Broken string</div>
    <div>...metaphorically speaking, anyway.<br><br>Something's wrong with the connection to the server. Could be your connection, could be a server problem, can't tell from here.<br><br>We'll try again in 30 seconds. Or you can try refreshing the page in a minute or two.<br><br>If the problem continues practice your favorite riff for awhile, or go touch grass, then come back later.</div>
  `;

  document.body.appendChild(modal);
}

function hideConnectionModal() {
  const existingModal = document.getElementById('connection-status-modal');
  if (existingModal) {
    existingModal.remove();
  }
}

function scheduleReconnectionAttempts() {
  if (connectionCheckInterval) return; // Already scheduled

  connectionCheckInterval = setInterval(async () => {
    if (!isServerDown) {
      clearInterval(connectionCheckInterval);
      connectionCheckInterval = null;
      return;
    }

    try {
      const response = await fetch('/api/debug/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'reconnection-test', level: 'DEBUG', context: {} })
      });

      if (response.ok) {
        isServerDown = false;
        hideConnectionModal();
        clearInterval(connectionCheckInterval);
        connectionCheckInterval = null;
      }
    } catch (error) {
      // Still down, continue checking
      lastConnectionAttempt = Date.now();
    }
  }, CONNECTION_CHECK_DELAY);
}

console.log = function(...args) {
  originalConsoleLog.apply(console, args);
  // Send to server (but don't wait for it, and don't use console.error if it fails)
  serverLog(args.join(' '), 'INFO', {}).catch(() => {});
};

console.error = function(...args) {
  originalConsoleError.apply(console, args);
  // Send to server (but don't wait for it, and don't use console.error if it fails)
  serverLog(args.join(' '), 'ERROR', {}).catch(() => {});
};

console.warn = function(...args) {
  originalConsoleWarn.apply(console, args);
  // Send to server (but don't wait for it, and don't use console.error if it fails)
  serverLog(args.join(' '), 'WARNING', {}).catch(() => {});
};

export const serverDebug = (message, context) => serverLog(message, 'DEBUG', context);
export const serverInfo = (message, context) => serverLog(message, 'INFO', context);
export const serverError = (message, context) => serverLog(message, 'ERROR', context);