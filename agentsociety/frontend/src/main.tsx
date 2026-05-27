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
])

const theme: ThemeConfig = {
    token: {
        colorPrimary: "#0000CC",
        colorInfo: "#0000CC",
        borderRadius: 16,
        colorBgContainer: "#FFFFFF",
        colorBgLayout: "#FFFFFF",
    },
    components: {
        Layout: {
            lightSiderBg: "#F8F8F8",
            headerBg: "#FFFFFF",
        },
        Button: {
            algorithm: true,
            colorBgContainer: "#FFFFFF",
        },
        Select: {
            colorBgContainer: "#FFFFFF",
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
