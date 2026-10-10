import React from 'react';
import {
  Target,
  Trophy,
  Users,
  Calendar,
  AlertTriangle,
  TrendingUp,
  BarChart2,
  GitCompare,
  Network,
  Shield,
  LayoutGrid,
  Wind,
  Layers,
  FileText,
  Activity,
} from 'lucide-react';

const ICON_MAP = {
  target: Target,
  trophy: Trophy,
  users: Users,
  calendar: Calendar,
  alert: AlertTriangle,
  trend: TrendingUp,
  distribution: BarChart2,
  compare: GitCompare,
  relationship: Network,
  shield: Shield,
  matrix: LayoutGrid,
  wind: Wind,
  layers: Layers,
  composition: Layers,
  bar_chart: BarChart2,
  'file-text': FileText,
};

export default function SemanticIcon({ name, className = 'w-4 h-4', size = 16 }) {
  const IconComponent = ICON_MAP[(name || '').toLowerCase()] || Activity;
  return <IconComponent className={className} size={size} />;
}
