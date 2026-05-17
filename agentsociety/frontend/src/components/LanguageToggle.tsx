import { GlobalOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import type { ButtonProps } from 'antd';
import { useTranslation } from 'react-i18next';

type LanguageToggleProps = Omit<ButtonProps, 'children' | 'icon' | 'onClick'> & {
    showLabel?: boolean;
};

export default function LanguageToggle({
    showLabel = true,
    title,
    ...buttonProps
}: LanguageToggleProps) {
    const { t, i18n } = useTranslation();
    const isEnglish = i18n.language?.startsWith('en');
    const nextLanguage = isEnglish ? 'zh' : 'en';
    const label = t(isEnglish ? 'common.language.switchToChinese' : 'common.language.switchToEnglish');

    return (
        <Button
            {...buttonProps}
            aria-label={label}
            title={title ?? label}
            icon={<GlobalOutlined />}
            onClick={() => {
                void i18n.changeLanguage(nextLanguage);
            }}
        >
            {showLabel ? label : null}
        </Button>
    );
}
