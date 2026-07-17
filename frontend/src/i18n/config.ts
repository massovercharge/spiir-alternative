import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import da from './locales/da.json';
import en from './locales/en.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      da: { translation: da },
      en: { translation: en },
    },
    lng: 'da', // Default language
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already safes from xss
    },
  });

export default i18n;
