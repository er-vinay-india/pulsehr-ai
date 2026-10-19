import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import MarkdownView, { normalizeMarkdownContent } from '../src/components/MarkdownView.js';

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${message}`);
    process.exit(1);
  }
  console.log(`✅ PASS: ${message}`);
}

console.log("=== RUNNING MARKDOWN & MATH RENDERING REGRESSION TESTS ===\n");

{
  const input = 'For $n$ trials, expand $(a+b)^n$ using terms $a^{n-k}$ and $b^k$. There are $n+1$ terms. Budget: $5 and $10.';
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));
  assert((html.match(/class="katex"/g) || []).length === 5, 'Binomial variables and algebra render as inline math');
  assert(!html.includes('katex-error'), 'Binomial notation renders without formula errors');
  assert(html.includes('Budget: $5 and $10.'), 'Currency stays literal alongside plain algebra');
}

// 1. User reported regression case
{
  const input = "**💡Strategic Observation**\n**Revenue Trajectory**: Total weekly sales across all locations peaked on **2010-12-24** at **$80.93M**, with lowest volume on **2011-01-28** ($39.60M). Overall network volume stabilized around an average of **$48.61M** per week across 143 observation dates.";
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));

  assert(html.includes('<strong class="md-bold">Revenue Trajectory</strong>'), "Revenue Trajectory is bold");
  assert(html.includes('<strong class="md-bold">2010-12-24</strong>'), "Peak date is bold");
  assert(html.includes('<strong class="md-bold">$80.93M</strong>'), "Peak currency $80.93M is bold");
  assert(html.includes('<strong class="md-bold">2011-01-28</strong>'), "Lowest date is bold");
  assert(html.includes('($39.60M)'), "Lowest currency ($39.60M) is intact");
  assert(html.includes('<strong class="md-bold">$48.61M</strong>'), "Average currency $48.61M is bold");
  assert(html.includes(', with lowest volume on '), "Normal spacing is preserved around punctuation");
  assert(!html.includes('katex'), "No accidental KaTeX rendering triggered on currency");
  assert(!html.includes('withlowestvolumeon'), "No space collapsing");
  assert(!html.includes('∗'), "No corrupted Unicode asterisk operators");
  assert(!html.includes('\\*\\*'), "No escaped literal asterisks");
}

// 2. Multiple currency values in one paragraph
{
  const input = "The top store generated $2,107,676.87/wk while store 33 had $259,862.31/wk, with a spread ratio of 8.11x and network mean of $1,046,964.88.";
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));

  assert(html.includes('$2,107,676.87/wk'), "First currency amount intact");
  assert(html.includes('$259,862.31/wk'), "Second currency amount intact");
  assert(html.includes('$1,046,964.88'), "Third currency amount intact");
  assert(!html.includes('katex'), "No math mode triggered across multiple dollar signs");
}

// 3. Dates, percentages, parentheses, and punctuation
{
  const input = "Between 2010-02-05 and 2012-10-26 (143 weeks), holiday periods saw a **+7.8%** uplift (p < 0.01).";
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));

  assert(html.includes('2010-02-05 and 2012-10-26'), "Date range intact");
  assert(html.includes('<strong class="md-bold">+7.8%</strong>'), "Percentage is bold");
  assert(html.includes('(143 weeks)'), "Parentheses intact");
  assert(!html.includes('−'), "Hyphens not converted to math minus signs");
}

// 4. Escaped and Unicode asterisks outside code
{
  const input = "\\*\\*Escaped bold\\*\\* and \u2217\u2217Unicode bold\u2217\u2217 while inside `\\*\\*literal code\\*\\*` remains protected.";
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));

  assert(html.includes('<strong class="md-bold">Escaped bold</strong>'), "Escaped bold normalized to bold tag");
  assert(html.includes('<strong class="md-bold">Unicode bold</strong>'), "Unicode bold normalized to bold tag");
  assert(html.includes('<code>\\*\\*literal code\\*\\*</code>'), "Code blocks preserved untouched");
}

// 5. Legitimate mathematical display content
{
  const input = "The OLS regression formula is:\n\n$$ y = \\beta_0 + \\beta_1 x + \\epsilon $$";
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));

  assert(html.includes('katex'), "KaTeX math is rendered for explicit $$ math blocks");
  assert(html.includes('β'), "Greek symbols rendered in KaTeX math");
}

// 6. Mixed lists and paragraphs with currency
{
  const input = "# Executive Summary\n\nKey figures:\n- Average Weekly Sales: $1,046,964.88\n- Peak holiday week: **$80.93M** on 2010-12-24\n- Total volume: **$6.73B** across network";
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));

  assert(html.includes('<h1>Executive Summary</h1>'), "Heading 1 rendered");
  assert(html.includes('<ul>'), "List container rendered");
  assert(html.includes('<li>Average Weekly Sales: $1,046,964.88</li>'), "List item with currency intact");
  assert(html.includes('<strong class="md-bold">$80.93M</strong>'), "Bold currency in list rendered");
  assert(html.includes('<strong class="md-bold">$6.73B</strong>'), "Bold total in list rendered");
}

// 7. Inline rendering mode
{
  const step = "Isolated 143 row records for Store 20 from `Walmart_Sales.csv` with mean of **$2,107,676.87/wk**.";
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: step, inline: true }));

  assert(html.includes('<span class="markdown-content-inline'), "Inline span wrapper rendered");
  assert(html.includes('<code>Walmart_Sales.csv</code>'), "Inline code rendered");
  assert(html.includes('<strong class="md-bold">$2,107,676.87/wk</strong>'), "Inline bold currency rendered");
  assert(!html.includes('<p>'), "No paragraph wrappers in inline mode");
}

// 8. Previously cached executive story from database
{
  const cachedNarrative = `# Executive Headline
This dataset reveals critical insights into Walmart's workforce operations and demographics, highlighting key performance indicators that can inform strategic HR decisions.

# Key Findings & Critical Thresholds
- **Average Weekly Sales**: \\$1,046,964.88, indicating a baseline performance level.
- **Holiday Impact**: 7% increase in sales during holidays, suggesting a significant boost in revenue.
- **Temperature's Influence**: Average temperature of 60.66°F, with a 100.14°F peak, showing moderate impact on sales.
- **Unemployment Rate**: 8.0%, with a peak of 14.31%, indicating a stable but slightly fluctuating economic environment.`;

  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: cachedNarrative }));

  assert(html.includes('<h1>Executive Headline</h1>'), "Cached headline rendered as h1");
  assert(html.includes('<strong class="md-bold">Average Weekly Sales</strong>: $1,046,964.88'), "Cached escaped currency rendered as clean bold label and amount");
  assert(html.includes('<strong class="md-bold">Holiday Impact</strong>: 7%'), "Cached holiday impact rendered");
  assert(!html.includes('katex'), "No math mode triggered on cached narrative");
}

// 9. User-reported attendance answer with inline LaTeX and protected code.
{
  const input = String.raw`For the **attendance rate**, use **Final Attendance** from **'Sheet1'**.

### 1. Using Final Attendance

The column is pre-calculated as: \`Total Attendance−Approved Leaves\`

- **Source:** \`WFO_July_2026_Test.xlsx\`, Sheet: \`Sheet1\`
- **Evidence:** Row 259 shows \`Total Attendance: 11\`, \`Approved Leaves: 2\`, and \`Final Attendance: 9\`.
- **Formula:** $\text{Derived Attendance} = \text{Total Working Days in Period} - \text{Total approved leaves}$

### Recommendation

Use **Final Attendance** for standard reporting.`.replace(/\\`/g, '`');
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));
  assert(html.includes('class="katex"') && !html.includes('katex-error'), 'Attendance formula renders as valid math');
  assert(html.includes('<mtext>Derived Attendance</mtext>'), 'Attendance formula retains readable word spacing');
  assert(html.includes('<h3>1. Using Final Attendance</h3>'), 'Attendance section headings render correctly');
  assert(html.includes('<code>Total Attendance−Approved Leaves</code>'), 'Inline calculation code preserves spaces and minus sign');
  assert(html.includes('<code>WFO_July_2026_Test.xlsx</code>'), 'Source filename remains unchanged');
}

// 10. Explicit inline math must not revive the currency-rendering regression.
{
  const input = String.raw`Budget: $5 and $10; peak **$80.93M**. Formula: $\text{Cost} = \$5$. Inline: \(x + y\). Display: \[y = \beta x\]. Literal: \`$\text{Cost} = \$5$\`.`.replace(/\\`/g, '`');
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: input }));
  assert(html.includes('Budget: $5 and $10; peak <strong class="md-bold">$80.93M</strong>'), 'Currency remains literal beside LaTeX');
  assert((html.match(/class="katex"/g) || []).length === 3, 'Single-dollar LaTeX, explicit inline and display delimiters render');
  assert(html.includes('katex-display'), 'Explicit display math remains a display block');
  assert(!html.includes('katex-error'), 'Escaped dollars within math do not cause parse errors');
  assert(html.includes('<code>$\\text{Cost} = \\$5$</code>'), 'LaTeX inside code is not interpreted');
}

// 11. Character-by-character delivery must not flash raw formatting syntax.
{
  const bold = 'Use **Final Attendance** and *actual utilization* from `Sheet1`.';
  let cleanAtEveryPrefix = true;
  for (let end = 1; end <= bold.length; end++) {
    const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: bold.slice(0, end), streaming: true }));
    if (html.replace(/<[^>]*>/g, '').includes('*')) cleanAtEveryPrefix = false;
  }
  assert(cleanAtEveryPrefix, 'Bold and italic markers stay hidden at every typing boundary');
  const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: 'Use **Final Att', streaming: true }));
  assert(html.includes('<strong class="md-bold">Final Att</strong>'), 'Partial bold text is styled while it reveals');
  const code = renderToStaticMarkup(React.createElement(MarkdownView, { content: 'Use `**literal', streaming: true }));
  assert(code.includes('<code>**literal</code>'), 'Unfinished code spans remain literal during typing');
  const formula = String.raw`- **Formula:** $\text{Derived Attendance} = \text{Working Days} - \text{Approved Leaves}$`;
  let mathAtEveryPrefix = true;
  for (let end = formula.indexOf('$') + 2; end <= formula.length; end++) {
    const html = renderToStaticMarkup(React.createElement(MarkdownView, { content: formula.slice(0, end), streaming: true }));
    if (html.includes('katex-error') || (end < formula.length && html.includes('\\text'))) mathAtEveryPrefix = false;
  }
  assert(mathAtEveryPrefix, 'Incomplete LaTeX stays buffered without raw commands or parse errors');
  const completed = renderToStaticMarkup(React.createElement(MarkdownView, { content: formula, streaming: true }));
  assert(completed.includes('class="katex"'), 'Formula appears once its closing delimiter arrives');
}

console.log("\n🎉 ALL 11 MARKDOWN & MATH RENDERING TEST SUITES PASSED SUCCESSFULLY!\n");
