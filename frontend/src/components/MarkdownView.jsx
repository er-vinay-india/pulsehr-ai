import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

/**
 * Strips enclosing code fences (e.g. ```markdown ... ```) if an LLM wraps its markdown response.
 */
function unwrapMarkdown(text) {
  if (!text) return '';
  let s = String(text).trim();
  if (s.startsWith('```markdown')) {
    s = s.slice(11).replace(/^[\r\n]+/, '');
  } else if (s.startsWith('```md')) {
    s = s.slice(5).replace(/^[\r\n]+/, '');
  } else if (s.startsWith('```')) {
    s = s.slice(3).replace(/^[\r\n]+/, '');
  }
  if (s.endsWith('```')) {
    s = s.slice(0, -3).replace(/[\r\n]+$/, '');
  }
  return s.trim();
}

export default function MarkdownView({ content, className = '' }) {
  if (!content) return null;

  const cleanContent = unwrapMarkdown(content);

  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          strong: ({ node, ...props }) => (
            <strong className="md-bold" {...props} />
          ),
          b: ({ node, ...props }) => (
            <b className="md-bold" {...props} />
          ),
          table: ({ node, ...props }) => (
            <div className="table-container" style={{ margin: '0.75rem 0' }}>
              <table {...props} />
            </div>
          ),
          a: ({ node, ...props }) => (
            <a target="_blank" rel="noopener noreferrer" {...props} />
          )
        }}
      >
        {cleanContent}
      </ReactMarkdown>
    </div>
  );
}
