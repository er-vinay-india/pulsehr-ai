import React from 'react';
import { PlugZap, Search, Layers, GitCompareArrows, ClipboardCheck, PenLine, Calculator, Presentation, Sparkles } from 'lucide-react';

const stageIcons = {
  connecting: PlugZap, understanding: Search, exploring: Layers, retrieving: Search,
  calculating: Calculator, presenting: Presentation, working: Sparkles,
  comparing: GitCompareArrows, reviewing: ClipboardCheck, composing: PenLine, writing: PenLine,
};
export default function HRIDAYActivity({ activity }) {
  if (!activity) return null;
  const Icon = stageIcons[activity.stage] || Sparkles;
  return <div className="hriday-working" data-stage={activity.stage} aria-busy="true">
    <span className="hriday-activity-mark" aria-hidden="true">
      <span className="hriday-activity-orbit" />
      <span className="hriday-activity-icon" key={activity.revision}><Icon size={17} /></span>
    </span>
    <span className="hriday-activity-text" key={activity.revision}>{activity.text}</span>
  </div>;
}
