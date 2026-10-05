import React, { createContext, useContext, useRef, useSyncExternalStore, useEffect } from 'react';
import { streamCopilotQuery, getAssistantIdentity } from '../../api/client.js';
import { HRIDAYConversation } from './conversation.js';

const Context = createContext(null);
export function HRIDAYProvider({ children }) {
  const ref = useRef(null);
  if (!ref.current) ref.current = new HRIDAYConversation(streamCopilotQuery);
  useEffect(() => {
    const clearDeletedData = () => ref.current.newChat();
    const clearUploadedContext = () => ref.current.invalidateDatasetContext();
    window.addEventListener('workbooks-deleted', clearDeletedData);
    window.addEventListener('workbook-uploaded', clearUploadedContext);
    const controller = new AbortController();
    getAssistantIdentity(controller.signal).then(identity => {
      if (!controller.signal.aborted) ref.current.setIdentity(identity);
    }).catch(() => {}); // Keep the central offline bootstrap if the API is unavailable.
    return () => {
      controller.abort(); ref.current.stop();
      window.removeEventListener('workbooks-deleted', clearDeletedData);
      window.removeEventListener('workbook-uploaded', clearUploadedContext);
    };
  }, []);
  return <Context.Provider value={ref.current}>{children}</Context.Provider>;
}
export function useHRIDAY() {
  const conversation = useContext(Context);
  if (!conversation) throw new Error('HRIDAY chat must be inside HRIDAYProvider.');
  const state = useSyncExternalStore(conversation.subscribe, conversation.getSnapshot, conversation.getSnapshot);
  return { conversation, ...state };
}
