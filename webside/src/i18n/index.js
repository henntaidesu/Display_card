import { createI18n } from 'vue-i18n'
import { computed, ref } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import ja from 'element-plus/es/locale/lang/ja'
import en from 'element-plus/es/locale/lang/en'
import zhCNMessages from './locales/zh-CN'
import jaMessages from './locales/ja'
import enMessages from './locales/en'

const STORAGE_KEY = 'dc_locale'
const SUPPORTED = ['zh-CN', 'ja', 'en']

function detectLocale() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved && SUPPORTED.includes(saved)) return saved
  const nav = (navigator.language || 'zh-CN').toLowerCase()
  if (nav.startsWith('ja')) return 'ja'
  if (nav.startsWith('en')) return 'en'
  return 'zh-CN'
}

export const currentLocale = ref(detectLocale())

const i18n = createI18n({
  legacy: false,
  locale: currentLocale.value,
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCNMessages,
    ja: jaMessages,
    en: enMessages
  }
})

// Element Plus 自带的多语言（分页、日期选择器等内置文案）
export const elementLocales = { 'zh-CN': zhCn, ja, en }

export const elementLocale = computed(() => elementLocales[currentLocale.value] || zhCn)

export function setLocale(locale) {
  if (!SUPPORTED.includes(locale)) return
  currentLocale.value = locale
  i18n.global.locale.value = locale
  localStorage.setItem(STORAGE_KEY, locale)
  document.documentElement.setAttribute('lang', locale)
}

export const localeOptions = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'ja', label: '日本語' },
  { value: 'en', label: 'English' }
]

export default i18n
