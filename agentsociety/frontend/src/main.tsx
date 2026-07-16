import ReactDOM from 'react-dom/client'
import './index.css'
import './i18n'
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'
import { ConfigProvider, ThemeConfig } from 'antd'
import enUS from 'antd/locale/en_US'
import zhCN from 'antd/locale/zh_CN'
import { useTranslation } from 'react-i18next'
import PixelReplay from './pages/PixelReplay'
import AgentBuilder from './pages/AgentBuilder'
import SetupPage from './pages/Setup'
import SkillsPage from './pages/Skills'
import MapStudioPage from './pages/MapStudio'

// Under code-server path proxy (e.g. /proxy/5174/), keep router + asset base aligned.
const routerBasename = (() => {
    const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
    return base === '' ? undefined : base
})()

const router = createBrowserRouter([
    {
        path: "/",
        element: <PixelReplay />,
    },
    {
        path: "/pixel-replay",
        element: <PixelReplay />,
    },
    {
        path: "/pixel-replay/:hypothesisId/:experimentId",
        element: <PixelReplay />,
    },
    {
        path: "/agent-builder",
        element: <AgentBuilder />,
    },
    {
        path: "/setup",
        element: <SetupPage />,
    },
    {
        path: "/map-studio",
        element: <MapStudioPage />,
    },
    {
        path: "/skills",
        element: <SkillsPage />,
    },
    {
        path: "*",
        element: <Navigate to="/" />,
    }
], { basename: routerBasename })

const theme: ThemeConfig = {
    token: {
        colorPrimary: "#2d91a3",
        colorInfo: "#2d91a3",
        colorSuccess: "#56a66f",
        colorWarning: "#e8a33f",
        colorError: "#d85f67",
        borderRadius: 8,
        colorText: "#26343a",
        colorTextSecondary: "#667982",
        colorBgContainer: "#fffdf8",
        colorBgLayout: "#f1f8f7",
        colorBorder: "#d4e7e5",
        fontFamily: '"Avenir Next", "Geist", "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif',
    },
    components: {
        Layout: {
            lightSiderBg: "#eef8f6",
            headerBg: "#fffdf8",
        },
        Button: {
            algorithm: true,
            colorBgContainer: "#fffdf8",
            controlHeight: 36,
        },
        Select: {
            colorBgContainer: "#fffdf8",
        },
        Card: {
            colorBgContainer: "#fffdf8",
        },
        Table: {
            headerBg: "#eaf7f5",
            rowHoverBg: "rgba(45, 145, 163, 0.06)",
        }
    }
};

const App = () => {
    const { i18n } = useTranslation();
    const antdLocale = i18n.language?.startsWith('en') ? enUS : zhCN;

    return (
        <ConfigProvider theme={theme} locale={antdLocale}>
            <RouterProvider router={router} />
        </ConfigProvider>
    );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
    <App />
)
