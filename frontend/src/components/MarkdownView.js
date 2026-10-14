import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

function escapedAt(text, index) {
  let slashes = 0;
  while (text[--index] === '\\') slashes++;
  return slashes % 2 === 1;
}

function normalizeMath(text, streaming) {
  // Explicit delimiters are unambiguous, unlike ordinary currency dollars.
  text = text.replace(/\\\(([\s\S]*?)\\\)/g, (_match, math) => `$$${math}$$`)
    .replace(/\\\[([\s\S]*?)\\\]/g, (_match, math) => `\n\n$$\n${math}\n$$\n\n`);
  if (streaming) {
    // Don't send half-written LaTeX to KaTeX while the answer is revealing.
    text = text.replace(/\\([\[(])([\s\S]*)$/, (match, opener, tail) =>
      tail.includes(opener === '(' ? '\\)' : '\\]') ? match : '');
  }
  let output = '';
  for (let index = 0; index < text.length;) {
    if (text[index] !== '$' || escapedAt(text, index)) {
      output += text[index++];
      continue;
    }
    const delimiter = text[index + 1] === '$' ? '$$' : '$';
    const start = index + delimiter.length;
    let end = text.indexOf(delimiter, start);
    while (end !== -1 && escapedAt(text, end)) end = text.indexOf(delimiter, end + delimiter.length);
    const body = text.slice(start, end === -1 ? text.length : end);
    const isMath = delimiter === '$$' || /\\[A-Za-z]+/.test(body);
    if (end !== -1 && isMath) {
      output += `$$${body}$$`;
      index = end + delimiter.length;
    } else if (end === -1 && streaming && (delimiter === '$$' || /^\s*\\/.test(body))) {
      break;
    } else {
      output += text[index++];
    }
  }
  return output;
}

function completeStreamingEmphasis(text) {
  // Balance only the render copy. Stored answers and copied text stay intact.
  const math = [];
  text = text.replace(/\$\$[\s\S]*?\$\$/g, match => {
    math.push(match);
    return `@@PULSE_MATH_${math.length - 1}@@`;
  });
  const open = [];
  let output = '';
  for (let index = 0; index < text.length;) {
    const char = text[index];
    if (!['*', '_'].includes(char) || escapedAt(text, index)
      || (char === '_' && /[\p{L}\p{N}]/u.test(text[index - 1] || '') && /[\p{L}\p{N}]/u.test(text[index + 1] || ''))) {
      output += text[index++];
      continue;
    }
    const marker = text[index + 1] === char ? char + char : char;
    const next = text[index + marker.length];
    if (open.at(-1) === marker && !/\s/.test(text[index - 1] || '')) open.pop();
    else if (next && !/\s/.test(next)) open.push(marker);
    else if (!next) break; // Hide a delimiter that is still arriving.
    output += marker;
    index += marker.length;
  }
  return (output + open.reverse().join('')).replace(/@@PULSE_MATH_(\d+)@@/g, (_, index) => math[Number(index)]);
}

/**
 * Strips enclosing code fences and normalizes unambiguous malformed markdown
 * without corrupting code blocks, numbers, citations, or currency values.
 */
export function normalizeMarkdownContent(text, { streaming = false } = {}) {
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
  const codePattern = streaming ? /(```[\s\S]*?```|`[^`\n]+`|`[^`\n]*$)/g : /(```[\s\S]*?```|`[^`\n]+`)/g;
  s = s.replace(codePattern, (match) => {
    codeBlocks.push(match === '`' ? '' : (!match.endsWith('`') ? match + '`' : match));
    return `@@PULSE_CODE_${codeBlocks.length - 1}@@`;
  });

  // 1. Normalize unambiguous Unicode asterisk operators used for bolding: ∗∗word∗∗ -> **word**
  s = s.replace(/\u2217\u2217/g, '**');

  // 2. Normalize unambiguous escaped asterisks used for bolding: \*\*word\*\* -> **word**
  s = s.replace(/\\\*\\\*([^\n]+?)\\\*\\\*/g, '**$1**');

  // Single-dollar LaTeX commands are math; currency remains ordinary text.
  s = normalizeMath(s, streaming);
  if (streaming) s = completeStreamingEmphasis(s);

  // Restore protected code blocks
  s = s.replace(/@@PULSE_CODE_(\d+)@@/g, (_, idx) => codeBlocks[Number(idx)]);

  return s;
}

export default function MarkdownView({ content, className = '', inline = false, streaming = false }) {
  if (!content) return null;

  const cleanContent = normalizeMarkdownContent(content, { streaming });

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
