import { GithubOutlined, ExperimentOutlined, ApiOutlined, TeamOutlined, GlobalOutlined, NodeIndexOutlined, SettingOutlined, RocketOutlined, ThunderboltOutlined, AppstoreAddOutlined } from "@ant-design/icons";
import { Menu, MenuProps, Space, Dropdown } from "antd";
import { Link } from "react-router-dom";
import Account from "./components/Account";
import { useTranslation } from 'react-i18next';
import { WITH_AUTH } from "./components/fetch";
import LanguageToggle from "./components/LanguageToggle";
// import Account from "./components/Account";

const RootMenu = ({ selectedKey, style }: {
    selectedKey: string,
    style?: React.CSSProperties
}) => {
    const { t } = useTranslation();

    const agentItems: MenuProps['items'] = [
        {
            key: '/agent-templates',
            label: <Link to="/agent-templates">{t('menu.agentTemplates')}</Link>,
            icon: <SettingOutlined />,
        },
        {
            key: '/profiles',
            label: <Link to="/profiles">{t('menu.profiles')}</Link>,
            icon: <TeamOutlined />,
        },
        {
            key: '/agent-builder',
            label: <Link to="/agent-builder">{t('menu.agentBuilder')}</Link>,
            icon: <AppstoreAddOutlined />,
        },
        {
            key: '/skills',
            label: <Link to="/skills">{t('menu.skills')}</Link>,
            icon: <ThunderboltOutlined />,
        },
    ];

    const menuItems: MenuProps['items'] = [
        {
            key: '/llms',
            label: <Link to="/llms">{t('menu.llmConfigs')}</Link>,
            icon: <ApiOutlined />,
        },
        {
            key: '/maps',
            label: <Link to="/maps">{t('menu.maps')}</Link>,
            icon: <GlobalOutlined />,
        },
        {
            key: '/agents',
            label: (
                <Dropdown menu={{ items: agentItems }} placement="bottomLeft" arrow>
                    <div>
                        <Link to="/agents"><Space><TeamOutlined />{t('menu.agents')}</Space></Link>
                    </div>
                </Dropdown>
            ),

        },
        {
            key: '/workflows',
            label: <Link to="/workflows">{t('menu.workflows')}</Link>,
            icon: <NodeIndexOutlined />,
        },
        {
            key: "/console",
            label: <Link to="/console">{t('menu.experiments')}</Link>,
            icon: <ExperimentOutlined />,
        },
        { key: "/survey", label: <Link to="/survey">{t('menu.survey')}</Link> },
        ...(WITH_AUTH ? [{ key: "/bill", label: <Link to="/bill">{t('menu.bill')}</Link> }] : []),
    ];

    menuItems.push({ key: "/Documentation", label: <Link to="https://agentsociety.readthedocs.io/en/latest/" rel="noopener noreferrer" target="_blank"><Space>{t('menu.documentation')}</Space></Link> });
    menuItems.push({ key: "/V2", label: <Link to="https://agentsociety2.fiblab.net" rel="noopener noreferrer" target="_blank"><Space><RocketOutlined />{t('menu.v2')}</Space></Link> });
    menuItems.push({ key: "/Github", label: <Link to="https://github.com/tsinghua-fib-lab/agentsociety/" rel="noopener noreferrer" target="_blank"><Space>{t('menu.github')}<GithubOutlined /></Space></Link> });

    const menuStyle: React.CSSProperties = {
        ...style,
        display: 'flex',
        flex: '1 1 auto',
        minWidth: 0,
        width: 'auto',
        alignItems: 'center',
        overflow: 'hidden',
    };

    return (
        <div style={{ display: 'flex', width: '100%', minWidth: 0 }}>
            <Menu
                theme="dark"
                mode="horizontal"
                items={menuItems}
                selectedKeys={[selectedKey]}
                style={menuStyle}
            />
            <div style={{
                marginLeft: 'auto',
                display: 'flex',
                alignItems: 'center',
                flex: '0 0 auto',
                minWidth: WITH_AUTH ? '320px' : 'max-content',
                justifyContent: 'flex-end',
                position: 'relative',
                zIndex: 2
            }}>
                <LanguageToggle
                    type="text"
                    showLabel={false}
                    style={{ color: 'white' }}
                />
                {WITH_AUTH && <Account />}
            </div>
        </div>
    );
};

export default RootMenu;
