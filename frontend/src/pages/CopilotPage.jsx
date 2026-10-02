import React from 'react';
import HRIDAYChat from '../components/hriday/HRIDAYChat.jsx';
import { hiddenChatScope, useChatViewport } from '../components/GlobalCopilotWidget.jsx';

// Full-page and floating views share one conversation and internal diagnostics.
export default function CopilotPage(props) {
  const { mobile } = useChatViewport();
  return <HRIDAYChat fullPage mobile={mobile} scope={() => hiddenChatScope(props)} />;
}
