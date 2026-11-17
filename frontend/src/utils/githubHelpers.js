/**
 * Pure helpers for GitHub monitoring & code leak triage UI.
 */

export const GITHUB_BUILTIN_BUCKETS = [
  'language:Dockerfile, Java Properties, Protocol Buffer, Gradle, Maven POM',
  'language:Python, Git Config, INI, Shell, SSH Config',
  'extension:java, js, json, sql, yaml, yml, conf, config, jsp',
  'extension:php, py, go, bat, cfg, env, exs, ini, pem, ppk, cs',
];

export const GITHUB_DORK_PRESETS = [
  {
    id: 'domain_creds',
    labelKey: 'pages.dorkPresetDomainCreds',
    template: '"{target}" (password OR passwd OR secret OR token)',
    defaultTarget: 'example.com',
  },
  {
    id: 'api_keys',
    labelKey: 'pages.dorkPresetApiKeys',
    template: '"{target}" (api_key OR apikey OR access_key OR AKIA)',
    defaultTarget: 'example.com',
  },
  {
    id: 'db_conn',
    labelKey: 'pages.dorkPresetDbConn',
    template: '"{target}" (jdbc OR mongodb OR redis OR mysql OR postgresql)',
    defaultTarget: 'example.com',
  },
  {
    id: 'config_files',
    labelKey: 'pages.dorkPresetConfigFiles',
    template: '"{target}" (filename:.env OR filename:application.yml OR filename:config)',
    defaultTarget: 'example.com',
  },
  {
    id: 'org_secrets',
    labelKey: 'pages.dorkPresetOrgSecrets',
    template: 'org:{target} (password OR secret OR token OR webhook)',
    defaultTarget: 'your-org',
  },
];

export const GITHUB_CRON_PRESETS = [
  { cron: '*/30 * * * *', labelKey: 'pages.cronEvery30Min' },
  { cron: '0 * * * *', labelKey: 'pages.cronEveryHour' },
  { cron: '0 */6 * * *', labelKey: 'pages.cronEvery6Hours' },
  { cron: '0 2 * * *', labelKey: 'pages.cronDaily2Am' },
];

export const REDTEAM_TOOL_PRESETS = [
  { repo: 'projectdiscovery/nuclei', category: 'Scanner' },
  { repo: 'projectdiscovery/subfinder', category: 'Recon' },
  { repo: 'projectdiscovery/httpx', category: 'Probe' },
  { repo: 'chaitin/xray', category: 'Scanner' },
  { repo: 'ffuf/ffuf', category: 'Fuzz' },
  { repo: 'sqlmapproject/sqlmap', category: 'Exploit' },
  { repo: 'trufflesecurity/trufflehog', category: 'Secrets' },
  { repo: 'zricethezav/gitleaks', category: 'Secrets' },
  { repo: 'BishopFox/sliver', category: 'C2' },
  { repo: 'EnableSecurity/wafw00f', category: 'Fingerprint' },
];

export function applyDorkPreset(currentKeyword, preset) {
  const raw = (currentKeyword || '').trim();
  const looksLikeBareTarget = raw && !raw.includes(' ') && !raw.includes(':') && !raw.includes('(');
  const target = looksLikeBareTarget ? raw.replace(/^["']|["']$/g, '') : preset.defaultTarget;
  return preset.template.replace('{target}', target);
}

export function extractKeywordTerms(keyword) {
  if (!keyword || typeof keyword !== 'string') return [];
  const cleaned = keyword
    .replace(/\b(?:org|repo|user|language|extension|filename|path|in):(?:"[^"]*"|[^\s]+)/gi, ' ')
    .replace(/\b(?:AND|OR|NOT)\b/g, ' ')
    .replace(/[()"']/g, ' ');
  const terms = cleaned
    .split(/\s+/)
    .map(t => t.trim())
    .filter(t => t.length >= 2);
  return [...new Set(terms)].sort((a, b) => b.length - a.length);
}

const SECRET_REGEX = /(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._-]{12,}|(?:jdbc:[a-z0-9:]+|mongodb(?:\+srv)?:\/\/|redis:\/\/|mysql:\/\/|postgres(?:ql)?:\/\/)[^\s'"<>]+|\b(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|app[_-]?secret|client[_-]?secret)\b\s*[:=]\s*['"]?[^\s'"`#;]{3,})/gi;
const NETWORK_REGEX = /(?:https?:\/\/[^\s'"<>)\]]+|\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})(?::\d{1,5})?\b)/gi;

function collectMatches(line, regex, kind) {
  const spans = [];
  regex.lastIndex = 0;
  let match;
  while ((match = regex.exec(line)) !== null) {
    if (!match[0]) {
      regex.lastIndex += 1;
      continue;
    }
    spans.push({ start: match.index, end: match.index + match[0].length, kind });
  }
  return spans;
}

export function tokenizeCodeLine(line, terms = []) {
  if (!line) return [{ text: ' ', kind: 'plain' }];

  const spans = [];
  if (terms.length > 0) {
    const escaped = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const kwRegex = new RegExp(`(${escaped.join('|')})`, 'gi');
    spans.push(...collectMatches(line, kwRegex, 'keyword'));
  }
  spans.push(...collectMatches(line, SECRET_REGEX, 'secret'));
  spans.push(...collectMatches(line, NETWORK_REGEX, 'network'));

  if (spans.length === 0) {
    return [{ text: line, kind: 'plain' }];
  }

  const priority = { keyword: 3, secret: 2, network: 1 };
  spans.sort((a, b) => (a.start - b.start) || (priority[b.kind] - priority[a.kind]));

  const accepted = [];
  let cursor = 0;
  for (const sp of spans) {
    if (sp.start < cursor) continue;
    accepted.push(sp);
    cursor = sp.end;
  }

  const tokens = [];
  let pos = 0;
  for (const sp of accepted) {
    if (sp.start > pos) {
      tokens.push({ text: line.slice(pos, sp.start), kind: 'plain' });
    }
    tokens.push({ text: line.slice(sp.start, sp.end), kind: sp.kind });
    pos = sp.end;
  }
  if (pos < line.length) {
    tokens.push({ text: line.slice(pos), kind: 'plain' });
  }
  return tokens;
}

export function tokenizeCodeSnippet(content, keyword = '') {
  const raw = typeof content === 'string' ? content : '';
  const terms = extractKeywordTerms(keyword);
  const lines = raw.split(/\r?\n/);
  return lines.map((line, index) => ({
    lineNumber: index + 1,
    tokens: tokenizeCodeLine(line, terms),
  }));
}

export function parseMultilineList(text) {
  if (!text || typeof text !== 'string') return [];
  const items = text
    .split(/[\n,;]+/)
    .map(v => v.trim())
    .filter(Boolean);
  return [...new Set(items)];
}

export function extractRepoSlugFromApiUrl(repoUrl) {
  if (!repoUrl || typeof repoUrl !== 'string') return '';
  return repoUrl
    .replace(/^https?:\/\/api\.github\.com\/repos\//i, '')
    .replace(/^https?:\/\/github\.com\//i, '')
    .replace(/\.git$/i, '')
    .replace(/\/+$/, '');
}

export function toGithubWebUrl(repoUrl) {
  const slug = extractRepoSlugFromApiUrl(repoUrl);
  return slug ? `https://github.com/${slug}` : repoUrl;
}

export function buildGitCloneCmd(repoFullNameOrUrl) {
  const slug = extractRepoSlugFromApiUrl(repoFullNameOrUrl);
  return slug ? `git clone https://github.com/${slug}.git` : '';
}
