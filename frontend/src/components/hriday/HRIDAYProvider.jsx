import React, { createContext, useContext, useRef, useSyncExternalStore, useEffect } from 'react';
import { streamCopilotQuery } from '../../api/client.js';
import { HRIDAYConversation } from './conversation.js';

const Context = createContext(null);
export function HRIDAYProvider({ children }) {
  const ref = useRef(null);
  if (!ref.current) ref.current = new HRIDAYConversation(streamCopilotQuery);
  useEffect(() => () => ref.current.stop(), []);
  return <Context.Provider value={ref.current}>{children}</Context.Provider>;
}
export function useHRIDAY() {
  const conversation = useContext(Context);
  if (!conversation) throw new Error('HRIDAY chat must be inside HRIDAYProvider.');
  const state = useSyncExternalStore(conversation.subscribe, conversation.getSnapshot, conversation.getSnapshot);
  return { conversation, ...state };
}
