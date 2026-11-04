import { useEffect, useState } from 'react';

// Keep React drafts mounted. Both the document and native host must be active
// before read-only editor effects resume; mutations are never replayed here.
export function useWebViewForeground() {
  const [activity, setActivity] = useState(() => ({
    documentActive: document.visibilityState !== 'hidden',
    hostActive: true,
  }));
  useEffect(() => {
    function setDocumentActive(documentActive: boolean) {
      setActivity((current) => current.documentActive === documentActive
        ? current : { ...current, documentActive });
    }
    const visibility = () => setDocumentActive(document.visibilityState !== 'hidden');
    const hide = () => setDocumentActive(false);
    const host = (event: Event) => {
      if (!(event instanceof CustomEvent) || typeof event.detail !== 'boolean') return;
      const hostActive: boolean = event.detail;
      setActivity((current) => current.hostActive === hostActive
        ? current : { ...current, hostActive });
    };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('pagehide', hide);
    window.addEventListener('pageshow', visibility);
    window.addEventListener('daynomy:active', host);
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('pagehide', hide);
      window.removeEventListener('pageshow', visibility);
      window.removeEventListener('daynomy:active', host);
    };
  }, []);
  return activity.documentActive && activity.hostActive;
}
