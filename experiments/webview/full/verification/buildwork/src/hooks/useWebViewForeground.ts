import { useEffect, useState } from 'react';

// Keep React draft state mounted while pausing read-only editor effects in the background.
// No mutation is replayed when a host returns to the foreground.
export function useWebViewForeground() {
  const [foreground, setForeground] = useState(() => document.visibilityState !== 'hidden');
  useEffect(() => {
    const visibility = () => setForeground(document.visibilityState !== 'hidden');
    const hide = () => setForeground(false);
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('pagehide', hide);
    window.addEventListener('pageshow', visibility);
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('pagehide', hide);
      window.removeEventListener('pageshow', visibility);
    };
  }, []);
  return foreground;
}
