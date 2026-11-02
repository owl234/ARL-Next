import { createI18n } from 'vue-i18n';
import zhCN from './zh-CN.js';
import enUS from './en-US.js';
import ruRU from './ru-RU.js';

export const DEFAULT_LOCALE = 'zh-CN';
export const LOCALE_STORAGE_KEY = 'arl_locale';
export const SUPPORTED_LOCALES = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
  { value: 'ru-RU', label: 'Русский' },
];

const loadedLocales = new Set(['zh-CN', 'en-US', 'ru-RU']);

export const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
    'ru-RU': ruRU,
  },
});

function applyLocaleState(locale) {
  i18n.global.locale.value = locale;
  if (typeof document !== 'undefined') document.documentElement.lang = locale;
  try {
    globalThis.localStorage?.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // 浏览器禁用存储时，当前页面仍可切换语言。
  }
}

export function loadLocaleMessages(locale) {
  return Promise.resolve(loadedLocales.has(locale));
}

export function setLocale(locale) {
  if (!SUPPORTED_LOCALES.some(option => option.value === locale)) return false;
  applyLocaleState(locale);
  return true;
}

export function initializeLocale() {
  let saved;
  try {
    saved = globalThis.localStorage?.getItem(LOCALE_STORAGE_KEY);
  } catch {
    // 无法读取偏好时使用默认中文。
  }
  const target = SUPPORTED_LOCALES.some(option => option.value === saved) ? saved : DEFAULT_LOCALE;
  setLocale(target);
}
