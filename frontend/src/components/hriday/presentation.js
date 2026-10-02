import { DEFAULT_ASSISTANT_IDENTITY } from './identity.js';
// Customer presentation only. Original answers, events, votes and evidence stay
// in the conversation's internal diagnostics; the backend contract is unchanged.
const COUNCIL_HEADING = '### 🏆 Elected Council Replier:';
const escapeRegex = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function presentHRIDAYAnswer(raw, { streaming = false, delegates = [], assistantName = DEFAULT_ASSISTANT_IDENTITY.name } = {}) {
  let text = String(raw || '').trimStart();
  const lower = text.toLowerCase();
  if (streaming && text && COUNCIL_HEADING.toLowerCase().startsWith(lower)) return '';
  if (/^#{1,6}\s*(?:🏆\s*)?Elected Council Replier:/i.test(text)) {
    const separator = /\r?\n\s*\r?\n/.exec(text);
    if (!separator) return '';
    text = text.slice(separator.index + separator[0].length).trimStart();
  }

  // Buffer partial identity introductions before rendering any delegate name.
  const greeting = /^(?:hello|hi|hey|namaste|greetings)[!,.\s]+/i;
  for (const delegate of delegates) {
    if (!delegate.role_title) continue;
    const prefixes = ['From my perspective as ' + delegate.role_title + ',', 'As ' + delegate.role_title + ','];
    // A later introductory sentence can also contain a role (e.g. the fallback).
    const boundary = [...text.matchAll(/[.!?]\s+/g)].at(-1);
    const start = boundary ? boundary.index + boundary[0].length : 0;
    const tail = text.slice(start);
    if (streaming && tail && prefixes.some(prefix => prefix.toLowerCase().startsWith(tail.toLowerCase()))) {
      text = text.slice(0, start);
    }
  }
  const introText = text.replace(greeting, '');
  const identities = delegates.flatMap(d => [d.name, d.primary_model]).filter(Boolean)
    .flatMap(name => [name, String(name).split('/').at(-1).replace(/[-_\d].*$/, '')]).filter(Boolean);
  const intro = /^(?:I am|I'm|I’m|my name is)\s/i;
  const possibleIntro = ["I am ", "I'm ", 'I’m ', 'my name is '];
  if (streaming && (possibleIntro.some(prefix => prefix.toLowerCase().startsWith(introText.toLowerCase()))
    || ['hello', 'hi', 'hey', 'namaste', 'greetings'].some(prefix => prefix.startsWith(text.toLowerCase())))) return '';
  if (intro.test(introText)) {
    const end = (streaming ? /[.!?](?=\s)/ : /[.!?](?=\s|$)/).exec(introText);
    if (streaming && !end) return '';
    const firstSentence = end ? introText.slice(0, end.index + 1) : introText;
    const identityDescription = firstSentence.replace(/\*\*|__/g, '').replace(intro, '');
    const knownIdentity = identities.some(name => new RegExp('^' + escapeRegex(name) + '(?=\\b|[ -])', 'i').test(identityDescription));
    const productIdentity = new RegExp('^' + escapeRegex(assistantName) + '(?=\\b|[ ,])', 'i').test(identityDescription);
    if (!productIdentity && (/council|war room/i.test(firstSentence) || knownIdentity)) {
      const remainder = introText.slice(firstSentence.length).trimStart();
      const welcome = 'welcome to the war room';
      const partialWelcome = welcome.startsWith(remainder.toLowerCase()) || remainder.toLowerCase().startsWith(welcome);
      text = `Hi, I’m ${assistantName}. ` + (streaming && partialWelcome && !/[!?]/.test(remainder) ? '' : remainder);
      text = text.replace(/Welcome to the War Room[—–-][^!?]*[!?]/i, 'How can I help?');
    }
  }
  // Hide delegate role attribution, preserving the substantive answer.
  for (const delegate of delegates) {
    if (!delegate.role_title) continue;
    const role = escapeRegex(delegate.role_title);
    text = text.replace(new RegExp(`(^|[.!?]\\s+)From my perspective as ${role},\\s*`, 'gi'), '$1')
      .replace(new RegExp(`(^|[.!?]\\s+)As ${role},\\s*`, 'gi'), '$1')
      .replace(new RegExp(`^(I'm|I’m|I am) ready to provide analysis as ${role}`, 'i'), 'I can help with the analysis');
  }
  return text.trim();
}

export function inferHRIDAYTool(query) {
  const q = query.trim().toLowerCase().replace(/\?$/, '');
  const expression = q.replace(/^(calculate|what is|compute)\s+/, '');
  if (/^[\d\s.+*/()\-]+$/.test(expression) && /\d/.test(expression)) {
    return { name: 'arithmetic', expression };
  }
  if (/^(?:please )?(?:create|make|generate|build)(?: me)? (?:a |an |the )?(?:workforce |hr |executive )?(?:presentation|powerpoint|pptx?|deck)(?: for (?:the )?workforce)?[.!]?$/.test(q)) {
    return { name: 'presentation' };
  }
  // Match the backend's conservative calculation grammar without dropping filters.
  const metric = /^(?:calculate |what is |show |compare )?(?:the )?(total|average|mean|minimum|maximum|median) (attendance|attendance rate|overtime|overtime hours|rating|punctuality)(?: (by department|across departments))?$/.exec(q);
  if (metric) {
    const operations = { total: 'sum', average: 'mean', mean: 'mean', minimum: 'min', maximum: 'max', median: 'median' };
    const columns = { attendance: 'attendance_rate', 'attendance rate': 'attendance_rate', overtime: 'overtime_hours', 'overtime hours': 'overtime_hours', rating: 'rating', punctuality: 'punctuality_rate' };
    return { name: 'calculate', calculation: { operation: operations[metric[1]], column: columns[metric[2]], group_by: metric[3] ? 'department' : null } };
  }
  return null;
}

export function presentArtifacts(artifacts = []) {
  return artifacts.filter(item => typeof item?.url === 'string'
    && item.url.startsWith('/api/reports/') && !/[\\\s]/.test(item.url));
}
