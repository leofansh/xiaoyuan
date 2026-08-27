/**
 * i18n - Internationalization module for Xiaoyuan Tutor
 */

const I18n = {
  currentLang: 'zh',
  translations: null,
  
  // Initialize i18n
  async init() {
    // Load saved language preference
    const savedLang = localStorage.getItem('xiaoyuan_lang');
    if (savedLang && (savedLang === 'zh' || savedLang === 'en')) {
      this.currentLang = savedLang;
    }
    
    // Load translations
    try {
      const resp = await fetch('/i18n/translations.json');
      this.translations = await resp.json();
    } catch (e) {
      console.error('Failed to load translations:', e);
      return;
    }
    
    // Apply translations to page
    this.applyTranslations();
  },
  
  // Get translation by key
  t(key) {
    if (!this.translations || !this.translations[this.currentLang]) {
      return key;
    }
    return this.translations[this.currentLang][key] || key;
  },
  
  // Set language and reapply
  setLang(lang) {
    if (lang !== 'zh' && lang !== 'en') return;
    this.currentLang = lang;
    localStorage.setItem('xiaoyuan_lang', lang);
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    this.applyTranslations();
  },
  
  // Apply translations to all elements with data-i18n attribute
  applyTranslations() {
    // Text content
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const text = this.t(key);
      if (text) el.textContent = text;
    });
    
    // Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const text = this.t(key);
      if (text) el.placeholder = text;
    });
    
    // Titles (tooltips)
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const text = this.t(key);
      if (text) el.title = text;
    });
    
    // Update page title
    document.title = this.t('app.title');
    
    // Update language buttons state
    document.querySelectorAll('.lang-btn').forEach(btn => {
      const lang = btn.getAttribute('data-lang');
      btn.classList.toggle('active', lang === this.currentLang);
    });
  }
};

// Export for use in app.js
window.I18n = I18n;
