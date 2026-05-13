import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translations
import enCommon from './locales/en/common';
import zhCommon from './locales/zh/common';
import enLLM from './locales/en/llm';
import zhLLM from './locales/zh/llm';
import enHome from './locales/en/home';
import zhHome from './locales/zh/home';
import enSurvey from './locales/en/survey';
import zhSurvey from './locales/zh/survey';
import enConsole from './locales/en/console';
import zhConsole from './locales/zh/console';
import enReplay from './locales/en/replay';
import zhReplay from './locales/zh/replay';
import enBill from './locales/en/bill';
import zhBill from './locales/zh/bill';
import enAgent from './locales/en/agent';
import zhAgent from './locales/zh/agent';
import enMap from './locales/en/map';
import zhMap from './locales/zh/map';
import enWorkflow from './locales/en/workflow';
import zhWorkflow from './locales/zh/workflow';
import enTemplate from './locales/en/template';
import zhTemplate from './locales/zh/template';
import enProfile from './locales/en/profile';
import zhProfile from './locales/zh/profile';
import enExperiment from './locales/en/experiment';
import zhExperiment from './locales/zh/experiment';
import enSkill from './locales/en/skill';
import zhSkill from './locales/zh/skill';
import enSetup from './locales/en/setup';
import zhSetup from './locales/zh/setup';

// Combine translations
const resources = {
    en: {
        translation: {
            ...enCommon,
            llm: enLLM,
            home: enHome,
            survey: enSurvey,
            console: enConsole,
            replay: enReplay,
            bill: enBill,
            agent: enAgent,
            map: enMap,
            workflow: enWorkflow,
            template: enTemplate,
            profile: enProfile,
            experiment: enExperiment,
            skill: enSkill,
            setup: enSetup,
        }
    },
    zh: {
        translation: {
            ...zhCommon,
            llm: zhLLM,
            home: zhHome,
            survey: zhSurvey,
            console: zhConsole,
            replay: zhReplay,
            bill: zhBill,
            agent: zhAgent,
            map: zhMap,
            workflow: zhWorkflow,
            template: zhTemplate,
            profile: zhProfile,
            experiment: zhExperiment,
            skill: zhSkill,
            setup: zhSetup,
        }
    }
};

i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
        debug: true,
        fallbackLng: 'zh',
        interpolation: {
            escapeValue: false,
        },
        resources
    });

export default i18n;
