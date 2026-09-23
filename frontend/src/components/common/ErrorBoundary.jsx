import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div
          className="card-panel error-boundary-card"
          style={{
            padding: '1.75rem',
            margin: '1rem 0',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            backgroundColor: 'rgba(244, 63, 94, 0.05)',
            borderRadius: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#f43f5e', marginBottom: '0.5rem' }}>
            <AlertTriangle size={20} />
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>
              {this.props.title || 'Component Display Error'}
            </h4>
          </div>
          <p style={{ color: '#cbd5e1', fontSize: '0.875rem', margin: '0 0 1rem 0', lineHeight: 1.5 }}>
            {this.state.error?.message || 'An unexpected error occurred while rendering this component.'}
          </p>
          <button
            type="button"
            className="btn-secondary"
            onClick={this.handleReset}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
          >
            <RefreshCw size={13} /> Retry Component
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
