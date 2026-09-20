import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

/**
 * Strips enclosing code fences and normalizes unambiguous malformed markdown
 * without corrupting code blocks, numbers, citations, or currency values.
 */
export function normalizeMarkdownContent(text) {
  if (!text) return '';
  let s = String(text).trim();

  // Strip enclosing markdown code fences if wrapped by an LLM
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
  s = s.trim();

  // Protect code blocks (both multi-line and inline) from transformation
  const codeBlocks = [];
  s = s.replace(/(```[\s\S]*?```|`[^`\n]+`)/g, (match) => {
    codeBlocks.push(match);
    return `@@PULSE_CODE_${codeBlocks.length - 1}@@`;
  });

  // 1. Normalize unambiguous Unicode asterisk operators used for bolding: ∗∗word∗∗ -> **word**
  s = s.replace(/\u2217\u2217/g, '**');

  // 2. Normalize unambiguous escaped asterisks used for bolding: \*\*word\*\* -> **word**
  s = s.replace(/\\\*\\\*([^\n]+?)\\\*\\\*/g, '**$1**');

  // 3. Convert explicit LaTeX display delimiters \[ ... \] to $$ ... $$ so display math continues to render
  s = s.replace(/\\\[([\s\S]*?)\\\]/g, '$$$$$1$$$$');

  // Restore protected code blocks
  s = s.replace(/@@PULSE_CODE_(\d+)@@/g, (_, idx) => codeBlocks[Number(idx)]);

  return s;
}

export default function MarkdownView({ content, className = '', inline = false }) {
  if (!content) return null;

  const cleanContent = normalizeMarkdownContent(content);

  const baseComponents = {
    strong: ({ node, ...props }) => React.createElement('strong', { className: 'md-bold', ...props }),
    b: ({ node, ...props }) => React.createElement('b', { className: 'md-bold', ...props }),
    table: ({ node, ...props }) => React.createElement(
      'div',
      { className: 'table-container', style: { margin: '0.75rem 0' } },
      React.createElement('table', props)
    ),
    a: ({ node, ...props }) => React.createElement('a', { target: '_blank', rel: 'noopener noreferrer', ...props })
  };

  if (inline) {
    return React.createElement(
      'span',
      { className: `markdown-content-inline ${className}`.trim() },
      React.createElement(ReactMarkdown, {
        remarkPlugins: [remarkGfm, [remarkMath, { singleDollarTextMath: false }]],
        rehypePlugins: [rehypeKatex],
        components: {
          ...baseComponents,
          p: ({ node, ...props }) => React.createElement('span', props)
        }
      }, cleanContent)
    );
  }

  return React.createElement(
    'div',
    { className: `markdown-content ${className}`.trim() },
    React.createElement(ReactMarkdown, {
      remarkPlugins: [remarkGfm, [remarkMath, { singleDollarTextMath: false }]],
      rehypePlugins: [rehypeKatex],
      components: baseComponents
    }, cleanContent)
  );
}
