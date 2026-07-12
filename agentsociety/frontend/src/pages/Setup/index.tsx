import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Button,
    Card,
    Col,
    Divider,
    Form,
    Input,
    InputNumber,
    Modal,
    Row,
    Select,
    Space,
    Steps,
    Table,
    Tabs,
    Tag,
    Tooltip,
    Typography,
    message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
    ApiOutlined,
    CheckCircleOutlined,
    CompassOutlined,
    DeleteOutlined,
    EditOutlined,
    ExperimentOutlined,
    ImportOutlined,
    PlayCircleOutlined,
    QuestionCircleOutlined,
    RobotOutlined,
    SaveOutlined,
    ThunderboltOutlined,
    UserAddOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchCustom } from '../../components/fetch';
import LanguageToggle from '../../components/LanguageToggle';
import PackageImportModal from '../../components/PackageImportModal';
import type { PackageInstallResult } from '../../components/packageImport';
import {
    localizeMapDisplayName,
    localizeMapLocationName,
    type LocalizedFields,
} from '../../utils/runtimeLocalization';
import { AgentEditorModal, type AgentEditorSaveMeta } from '../AgentBuilder/AgentEditorModal';
import {
    jsonStringify,
    parseJsonObject,
    type AgentFormValues,
    type AgentRecord,
} from '../AgentBuilder/agentEditor';
import './style.css';

const { Text, Title, Paragraph } = Typography;

const DEFAULT_COMMON_SKILL_IDS = [
    'routine.daily',
    'social.reply',
    'memory.record',
    'map.navigate',
    'safety.respond',
];

const DEFAULT_PERSONAL_SKILL_IDS = [
    'community.coordinate',
    'conflict.mediate',
    'first_aid.basic',
    'notice.write',
    'messaging.group',
];

type RedactedValue = {
    configured: boolean;
    value: string;
};

type MapLocation = {
    id: string;
    name: string;
    aliases?: string[];
    localized?: LocalizedFields;
    interaction_ids?: string[];
};

type MapValidationStatus = {
    ok: boolean;
    errors: string[];
    warnings: string[];
};

type MapPackageSummary = {
    map_id: string;
    display_name: string;
    localized?: LocalizedFields;
    manifest_config_path: string;
    location_count: number;
    interaction_count: number;
    character_count: number;
    locations: MapLocation[];
    validation_status: MapValidationStatus;
};

type SetupStatus = {
    workspace_path: string;
    env_file: string;
    model_config: Record<string, RedactedValue>;
    current_experiment?: {
        hypothesis_id?: string;
        experiment_id?: string;
        workspace_path?: string;
    } | null;
    setup_mode?: boolean;
    default_experiment?: {
        key?: string;
        label?: string;
        description?: string;
        map_id?: string;
        hypothesis_id?: string;
        experiment_id?: string;
        workspace_path?: string;
        config_exists?: boolean;
    };
    default_experiments?: Array<{
        key: string;
        label: string;
        description?: string;
        localized?: Record<string, { label?: string; description?: string }>;
        map_id: string;
        hypothesis_id: string;
        experiment_id: string;
        workspace_path: string;
        config_exists: boolean;
        replay_db_exists?: boolean;
        public_slug?: string;
        image?: string;
        tags?: string[];
        agent_pack?: string;
        replay_slug?: string;
    }>;
    needs_setup: boolean;
    selected_map_id: string;
    maps: MapPackageSummary[];
    map_locations: MapLocation[];
};

type DraftPayload = {
    experiment_context: Record<string, any>;
    init_config: {
        env_modules: Array<{ module_type: string; kwargs: Record<string, any> }>;
        agents: AgentRecord[];
        codegen_router?: Record<string, any>;
    };
    steps: Record<string, any>;
    readme: string;
    warnings: string[];
};

type CompleteRoleVisualsResponse = {
    draft: DraftPayload;
    results: Array<{ agent_id: number; name: string; status: string; filename?: string; error?: string }>;
    completed_count: number;
    failed_count: number;
};

type LatestDraftPayload = {
    generated_at: string;
    basics?: Partial<BasicsForm>;
    draft: DraftPayload;
};

type LaunchResult = {
    hypothesis_id: string;
    experiment_id: string;
    workspace_path: string;
};

type ModelForm = {
    GOD_LLM_API_KEY?: string;
    GOD_LLM_API_BASE?: string;
    GOD_LLM_MODEL?: string;
    GOD_EMBEDDING_API_KEY?: string;
    GOD_EMBEDDING_API_BASE?: string;
    GOD_EMBEDDING_MODEL?: string;
    GOD_BACKEND_HOST?: string;
    GOD_BACKEND_PORT?: string;
    GOD_FRONTEND_PORT?: string;
};

type BasicsForm = {
    title: string;
    background: string;
    agent_count: number;
    map_id: string;
    language: string;
    start_t: string;
    num_steps: number;
    tick: number;
    movement_tiles_per_second: number;
    movement_min_steps_per_trip: number;
};

const fetchJson = async <T,>(url: string, options?: RequestInit): Promise<T> => {
    const response = await fetchCustom(url, options);
    if (!response.ok) {
        throw new Error(await response.text());
    }
    return response.json();
};

const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error));

const compactJson = (value: any, length = 140) => {
    const text = JSON.stringify(value ?? {});
    return text.length > length ? `${text.slice(0, length)}...` : text;
};

const agentName = (agent: AgentRecord) => (
    String(agent.kwargs?.name || agent.kwargs?.profile?.name || `Agent ${agent.agent_id}`)
);

const agentCharacterSprite = (agent: AgentRecord) => (
    String(agent.kwargs?.profile?.appearance?.character_sprite || '')
);

const roleImageCount = (agents: AgentRecord[]) => (
    agents.filter((agent) => agentCharacterSprite(agent)).length
);

const help = (text: string) => (
    <Tooltip title={text}>
        <QuestionCircleOutlined className="setup-help-icon" />
    </Tooltip>
);

const hasHan = (value: string) => /[\u4e00-\u9fff]/.test(value);

const formLabel = (label: string, tooltip: string) => (
    <Space size={6}>
        <span>{label}</span>
        {help(tooltip)}
    </Space>
);

const getEnvModule = (draft: DraftPayload) => draft.init_config.env_modules[0];

const cloneDraft = (draft: DraftPayload): DraftPayload => JSON.parse(JSON.stringify(draft));

const BASICS_STORAGE_KEY = 'god.setup.basics';

const defaultBasicsZh: BasicsForm = {
    title: 'Virtual Eden Civic Morning',
    background: '请生成一个明亮、边界清晰的虚拟小镇晨间协作实验：居民、店主、学生和协调员围绕公共通知、日常任务和互助事件行动，重点观察信息传播、协作和情绪变化。',
    agent_count: 10,
    map_id: 'the_ville',
    language: 'zh',
    start_t: '2026-05-11T08:20:00+08:00',
    num_steps: 4,
    tick: 1800,
    movement_tiles_per_second: 8,
    movement_min_steps_per_trip: 3,
};

const defaultBasicsEn: BasicsForm = {
    title: 'Virtual Eden Civic Morning',
    background: 'Generate a bright, bounded virtual-town civic morning. Residents, shopkeepers, students, and coordinators respond to public notices, daily tasks, and mutual-aid events. Focus on information flow, cooperation, and emotional changes.',
    agent_count: 10,
    map_id: 'the_ville',
    language: 'en',
    start_t: '2026-05-11T08:20:00+08:00',
    num_steps: 4,
    tick: 1800,
    movement_tiles_per_second: 8,
    movement_min_steps_per_trip: 3,
};

const defaultBasics = defaultBasicsZh;

const defaultBasicsForLanguage = (language?: string) => (
    language?.startsWith('en') ? defaultBasicsEn : defaultBasicsZh
);

const normalizeBasicsValues = (
    values: Partial<BasicsForm> = {},
    defaults: BasicsForm = defaultBasics
): BasicsForm => ({
    title: String(values.title || defaults.title).trim() || defaults.title,
    background: String(values.background || defaults.background).trim() || defaults.background,
    agent_count: Number(values.agent_count || defaults.agent_count),
    map_id: String(values.map_id || defaults.map_id || 'the_ville').trim() || 'the_ville',
    language: values.language || defaults.language,
    start_t: String(values.start_t || defaults.start_t).trim() || defaults.start_t,
    num_steps: Number(values.num_steps || defaults.num_steps),
    tick: Number(values.tick || defaults.tick),
    movement_tiles_per_second: Number(
        values.movement_tiles_per_second || defaults.movement_tiles_per_second
    ),
    movement_min_steps_per_trip: Number(
        values.movement_min_steps_per_trip || defaults.movement_min_steps_per_trip
    ),
});

const withLocalizedBasicsText = (
    values: Partial<BasicsForm>,
    defaults: BasicsForm,
): BasicsForm => normalizeBasicsValues({
    ...values,
    title: defaults.title,
    background: defaults.background,
    language: defaults.language,
}, defaults);

const loadStoredBasics = (defaults: BasicsForm = defaultBasics): BasicsForm => {
    if (typeof window === 'undefined') {
        return defaults;
    }
    try {
        const raw = window.localStorage.getItem(BASICS_STORAGE_KEY);
        if (!raw) {
            return defaults;
        }
        const normalized = normalizeBasicsValues(JSON.parse(raw), defaults);
        return normalized.language !== defaults.language
            ? withLocalizedBasicsText(normalized, defaults)
            : normalized;
    } catch {
        return defaults;
    }
};

const saveStoredBasics = (values: BasicsForm) => {
    if (typeof window === 'undefined') {
        return;
    }
    window.localStorage.setItem(BASICS_STORAGE_KEY, JSON.stringify(values));
};

const replayPathForLaunch = (result: LaunchResult) => (
    `/pixel-replay/${encodeURIComponent(result.hypothesis_id)}/${encodeURIComponent(result.experiment_id)}?workspace_path=${encodeURIComponent(result.workspace_path)}`
);

const basicsMatch = (left: BasicsForm, right: BasicsForm) => (
    left.title === right.title
    && left.background === right.background
    && left.agent_count === right.agent_count
    && left.map_id === right.map_id
    && left.language === right.language
    && left.start_t === right.start_t
    && left.num_steps === right.num_steps
    && left.tick === right.tick
    && left.movement_tiles_per_second === right.movement_tiles_per_second
    && left.movement_min_steps_per_trip === right.movement_min_steps_per_trip
);

export default function SetupPage() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { t, i18n } = useTranslation();
    const copy = (key: string, values?: Record<string, unknown>) => (
        t(`setup.${key}`, values) as string
    );
    const localizedDefaultBasics = useMemo(
        () => defaultBasicsForLanguage(i18n.language),
        [i18n.language]
    );
    const [messageApi, messageContextHolder] = message.useMessage();
    const [status, setStatus] = useState<SetupStatus | null>(null);
    const [currentStep, setCurrentStep] = useState(0);
    const [draft, setDraft] = useState<DraftPayload | null>(null);
    const [loadingStatus, setLoadingStatus] = useState(true);
    const [savingModel, setSavingModel] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [startingDefault, setStartingDefault] = useState<string | null>(null);
    const [builtinModalOpen, setBuiltinModalOpen] = useState(false);
    const [latestDraftAvailable, setLatestDraftAvailable] = useState(false);
    const [launchPending, setLaunchPending] = useState<LaunchResult | null>(null);
    const [packageImportOpen, setPackageImportOpen] = useState<false | 'map' | 'experiment'>(false);
    const [agentModalOpen, setAgentModalOpen] = useState(false);
    const [editingAgentId, setEditingAgentId] = useState<number | null>(null);
    const [completingRoleImages, setCompletingRoleImages] = useState(false);
    const [contextJsonText, setContextJsonText] = useState('');
    const [stepsJsonText, setStepsJsonText] = useState('');
    const [contextJsonError, setContextJsonError] = useState<string | null>(null);
    const [stepsJsonError, setStepsJsonError] = useState<string | null>(null);
    const [basicsValues, setBasicsValues] = useState<BasicsForm>(() => loadStoredBasics(localizedDefaultBasics));
    const basicsRef = useRef<BasicsForm>(basicsValues);
    const previousDefaultBasicsRef = useRef<BasicsForm>(localizedDefaultBasics);
    const requestedMapId = String(searchParams.get('map_id') || '').trim();
    const [agentForm] = Form.useForm<AgentFormValues>();
    const [modelForm] = Form.useForm<ModelForm>();
    const [basicsForm] = Form.useForm<BasicsForm>();
    const selectedMapId = String(
        draft?.init_config?.env_modules?.[0]?.kwargs?.map_id
        || basicsValues.map_id
        || status?.selected_map_id
        || 'the_ville'
    );
    const selectedMap = useMemo(() => (
        (status?.maps || []).find((item) => item.map_id === selectedMapId)
        || (status?.maps || []).find((item) => item.map_id === status?.selected_map_id)
        || (status?.maps || [])[0]
    ), [selectedMapId, status?.maps, status?.selected_map_id]);
    const mapLocations = selectedMap?.locations?.length ? selectedMap.locations : (status?.map_locations || []);
    const mapDisplayName = (item: MapPackageSummary | undefined, fallback = basicsValues.map_id) => (
        localizeMapDisplayName(item || { map_id: fallback, display_name: fallback }, i18n.language)
    );
    const locationDisplayName = (location: MapLocation) => (
        localizeMapLocationName(selectedMap?.map_id || selectedMapId, location, i18n.language)
    );
    const defaultExperimentLocale = (item: NonNullable<SetupStatus['default_experiments']>[number]) => (
        item.localized?.[i18n.language?.startsWith('zh') ? 'zh' : 'en'] || {}
    );
    const defaultExperimentLabel = (item: NonNullable<SetupStatus['default_experiments']>[number]) => (
        t(`setup.defaultExperiments.${item.key}.label`, {
            defaultValue: defaultExperimentLocale(item).label || item.label,
        }) as string
    );
    const defaultExperimentDescription = (item: NonNullable<SetupStatus['default_experiments']>[number]) => (
        t(`setup.defaultExperiments.${item.key}.description`, {
            defaultValue: defaultExperimentLocale(item).description
                || item.description
                || `${item.hypothesis_id} / ${item.experiment_id}`,
        }) as string
    );
    const mapOptions = useMemo(() => (
        (status?.maps || []).map((item) => ({
            value: item.map_id,
            label: `${mapDisplayName(item)} (${item.location_count}/${item.interaction_count})`,
            disabled: !item.validation_status?.ok,
        }))
    ), [i18n.language, status?.maps]);
    const locationOptions = useMemo(() => (
        mapLocations.map((location) => ({
            value: location.id,
            label: i18n.language?.startsWith('en') && hasHan(location.id)
                ? locationDisplayName(location)
                : `${locationDisplayName(location)} (${location.id})`,
        }))
    ), [i18n.language, mapLocations, selectedMap?.map_id, selectedMapId]);
    const mapManifestDescription = (map: MapPackageSummary) => {
        const path = map.manifest_config_path || '';
        if (i18n.language?.startsWith('en') && hasHan(path)) {
            return copy('basics.mapManifestHidden');
        }
        return path;
    };
    const draftJsonHasErrors = Boolean(contextJsonError || stepsJsonError);

    const renderLaunchPendingAlert = (marginBottom = 18) => (
        launchPending ? (
            <Alert
                type="success"
                showIcon
                message={copy('launchPending.title')}
                description={(
                    <Space direction="vertical" size={4}>
                        <Text>{copy('launchPending.description')}</Text>
                        <Text code>
                            {launchPending.hypothesis_id} / experiment_{launchPending.experiment_id}
                        </Text>
                    </Space>
                )}
                style={{ marginBottom }}
            />
        ) : null
    );

    const loadStatus = async (): Promise<SetupStatus | null> => {
        setLoadingStatus(true);
        try {
            const payload = await fetchJson<SetupStatus>('/api/v1/god/setup/status');
            setStatus(payload);
            const storedBasics = basicsRef.current;
            const defaultMapId = localizedDefaultBasics.map_id || 'the_ville';
            const selectedMapId = payload.selected_map_id || defaultMapId;
            const requestedMapExists = requestedMapId
                ? (payload.maps || []).some((item) => item.map_id === requestedMapId)
                : false;
            const selectedMapExists = (payload.maps || []).some((item) => item.map_id === selectedMapId);
            if (requestedMapExists) {
                syncBasicsValues({ ...storedBasics, map_id: requestedMapId });
                basicsForm.setFieldsValue({ map_id: requestedMapId });
                setCurrentStep(2);
            } else if (selectedMapExists && storedBasics.map_id === defaultMapId && selectedMapId !== defaultMapId) {
                syncBasicsValues({ ...storedBasics, map_id: selectedMapId });
                basicsForm.setFieldsValue({ map_id: selectedMapId });
            }
            modelForm.setFieldsValue({
                GOD_LLM_API_BASE: payload.model_config.GOD_LLM_API_BASE?.value || 'https://api.openai.com/v1',
                GOD_LLM_MODEL: payload.model_config.GOD_LLM_MODEL?.value || '',
                GOD_EMBEDDING_API_BASE: payload.model_config.GOD_EMBEDDING_API_BASE?.value || '',
                GOD_EMBEDDING_MODEL: payload.model_config.GOD_EMBEDDING_MODEL?.value || 'text-embedding-3-large',
                GOD_BACKEND_HOST: payload.model_config.GOD_BACKEND_HOST?.value || '127.0.0.1',
                GOD_BACKEND_PORT: payload.model_config.GOD_BACKEND_PORT?.value || '8001',
                GOD_FRONTEND_PORT: payload.model_config.GOD_FRONTEND_PORT?.value || '5174',
            });
            void loadLatestDraft(false);
            return payload;
        } catch (error) {
            messageApi.error(copy('messages.loadStatusFailed', { error: errorText(error) }));
            return null;
        } finally {
            setLoadingStatus(false);
        }
    };

    useEffect(() => {
        loadStatus();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!draft) {
            setContextJsonText('');
            setStepsJsonText('');
            setContextJsonError(null);
            setStepsJsonError(null);
            return;
        }
        setContextJsonText(jsonStringify(draft.experiment_context));
        setStepsJsonText(jsonStringify(draft.steps));
        setContextJsonError(null);
        setStepsJsonError(null);
    }, [draft]);

    useEffect(() => {
        if (currentStep === 2) {
            basicsForm.setFieldsValue(basicsValues);
        }
        // Only sync when entering the step; while typing, Form owns the live cursor state.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentStep]);

    const saveModelConfig = async () => {
        const values = await modelForm.validateFields();
        setSavingModel(true);
        try {
            const payload = await persistModelConfig(values);
            setStatus(payload);
            messageApi.success(copy('messages.modelSaved'));
            setCurrentStep(1);
        } catch (error) {
            messageApi.error(copy('messages.saveModelFailed', { error: errorText(error) }));
        } finally {
            setSavingModel(false);
        }
    };

    const cleanModelValues = (values: ModelForm) => Object.fromEntries(
        Object.entries(values).filter(([, value]) => value !== undefined && String(value).trim() !== '')
    );

    const persistModelConfig = async (values: ModelForm) => fetchJson<SetupStatus>('/api/v1/god/setup/model-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cleanModelValues(values)),
    });

    const completeLaunch = (result: LaunchResult, setupMode: boolean, delayMs: number) => {
        if (setupMode) {
            setLaunchPending(result);
            return;
        }
        window.setTimeout(() => {
            navigate(replayPathForLaunch(result));
        }, delayMs);
    };

    const syncBasicsValues = (values: Partial<BasicsForm>) => {
        const normalized = normalizeBasicsValues(values, localizedDefaultBasics);
        basicsRef.current = normalized;
        setBasicsValues(normalized);
        saveStoredBasics(normalized);
        return normalized;
    };

    const handlePackageInstalled = async (result: PackageInstallResult) => {
        setPackageImportOpen(false);
        const nextStatus = await loadStatus();
        if (result.package_type === 'map' && result.resource_id) {
            const normalized = syncBasicsValues({ ...basicsRef.current, map_id: result.resource_id });
            basicsForm.setFieldsValue(normalized);
            setCurrentStep(2);
        }
        if (result.package_type === 'experiment') {
            messageApi.success(copy('messages.experimentImported', { id: result.resource_id || '' }));
            if (nextStatus) {
                setStatus(nextStatus);
            }
            const hypothesisId = result.hypothesis_id || result.resource_id || result.current_experiment?.hypothesis_id;
            if (hypothesisId) {
                completeLaunch(
                    {
                        hypothesis_id: hypothesisId,
                        experiment_id: result.experiment_id || result.current_experiment?.experiment_id || '1',
                        workspace_path: result.workspace_path
                            || result.current_experiment?.workspace_path
                            || nextStatus?.workspace_path
                            || status?.workspace_path
                            || '',
                    },
                    Boolean(nextStatus?.setup_mode || status?.setup_mode),
                    700,
                );
            }
        }
    };

    const loadLatestDraft = async (navigateToDraft = false) => {
        try {
            const response = await fetchCustom('/api/v1/god/setup/latest-draft');
            if (response.status === 404) {
                setLatestDraftAvailable(false);
                return false;
            }
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json() as LatestDraftPayload;
            setLatestDraftAvailable(true);
            setDraft((current) => (!current || navigateToDraft ? payload.draft : current));
            if (payload.basics) {
                const latestMatchesUiLanguage = payload.basics.language === localizedDefaultBasics.language;
                if (navigateToDraft || latestMatchesUiLanguage) {
                    const normalized = syncBasicsValues({ ...basicsRef.current, ...payload.basics });
                    basicsForm.setFieldsValue(normalized);
                }
            }
            if (navigateToDraft) {
                setCurrentStep(4);
            }
            return true;
        } catch (error) {
            messageApi.warning(copy('messages.loadLatestDraftFailed', { error: errorText(error) }));
            return false;
        }
    };

    useEffect(() => {
        const previousDefaults = previousDefaultBasicsRef.current;
        if (basicsRef.current.language !== localizedDefaultBasics.language) {
            const next = withLocalizedBasicsText(basicsRef.current, localizedDefaultBasics);
            basicsRef.current = next;
            setBasicsValues(next);
            saveStoredBasics(next);
            basicsForm.setFieldsValue(next);
            previousDefaultBasicsRef.current = localizedDefaultBasics;
            return;
        }
        if (basicsMatch(basicsRef.current, previousDefaults)) {
            basicsRef.current = localizedDefaultBasics;
            setBasicsValues(localizedDefaultBasics);
            saveStoredBasics(localizedDefaultBasics);
            basicsForm.setFieldsValue(localizedDefaultBasics);
        }
        previousDefaultBasicsRef.current = localizedDefaultBasics;
    }, [basicsForm, localizedDefaultBasics]);

    const persistBasicsFromForm = async () => {
        const values = await basicsForm.validateFields();
        const normalized = syncBasicsValues(values);
        basicsForm.setFieldsValue(normalized);
        return normalized;
    };

    const goToStep = async (targetStep: number) => {
        if (currentStep === 2 && targetStep > 2) {
            try {
                await persistBasicsFromForm();
            } catch {
                return;
            }
        }
        setCurrentStep(targetStep);
    };

    const generateDraft = async () => {
        const modelValues = await modelForm.validateFields();
        const basicsPayload = currentStep === 2
            ? await persistBasicsFromForm()
            : basicsRef.current;
        setGenerating(true);
        try {
            const payload = await fetchJson<DraftPayload>('/api/v1/god/setup/generate-draft', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_config: modelValues,
                    basics: basicsPayload,
                }),
            });
            setDraft(payload);
            setLatestDraftAvailable(true);
            setCurrentStep(4);
            messageApi.success(copy('messages.draftGenerated'));
        } catch (error) {
            messageApi.error(copy('messages.generateDraftFailed', { error: errorText(error) }));
        } finally {
            setGenerating(false);
        }
    };

    const startDefaultExperiment = async (experimentKey: string) => {
        const modelValues = await modelForm.validateFields();
        if (!status?.model_config.GOD_LLM_API_KEY?.configured && !String(modelValues.GOD_LLM_API_KEY || '').trim()) {
            messageApi.error(copy('messages.apiKeyRequired'));
            return;
        }
        setStartingDefault(experimentKey);
        try {
            const nextStatus = await persistModelConfig(modelValues);
            setStatus(nextStatus);
            const result = await fetchJson<LaunchResult>('/api/v1/god/setup/start-default', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ experiment_key: experimentKey }),
            });
            const setupMode = Boolean(nextStatus.setup_mode || status?.setup_mode);
            messageApi.success(setupMode ? copy('messages.defaultQueued') : copy('messages.defaultStarted'));
            setBuiltinModalOpen(false);
            completeLaunch(result, setupMode, 700);
        } catch (error) {
            messageApi.error(copy('messages.defaultStartFailed', { error: errorText(error) }));
        } finally {
            setStartingDefault(null);
        }
    };

    const validateContextJsonText = (text: string) => {
        try {
            parseJsonObject(text, 'experiment_context');
            setContextJsonError(null);
        } catch (error) {
            setContextJsonError(errorText(error));
        }
    };

    const validateStepsJsonText = (text: string) => {
        try {
            parseJsonObject(text, 'steps');
            setStepsJsonError(null);
        } catch (error) {
            setStepsJsonError(errorText(error));
        }
    };

    const draftFromJsonText = () => {
        if (!draft) return null;
        const next = cloneDraft(draft);
        next.experiment_context = parseJsonObject(contextJsonText, 'experiment_context');
        next.steps = parseJsonObject(stepsJsonText, 'steps');
        next.init_config.agents = next.init_config.agents.map((agent) => ({
            ...agent,
            kwargs: {
                ...agent.kwargs,
                experiment_context: next.experiment_context,
                profile: {
                    ...(agent.kwargs?.profile || {}),
                    scenario: String(next.experiment_context.background || ''),
                },
            },
        }));
        return next;
    };

    const commitDraftJsonEdits = () => {
        try {
            const next = draftFromJsonText();
            if (!next) return null;
            setContextJsonError(null);
            setStepsJsonError(null);
            setDraft(next);
            return next;
        } catch (error) {
            const message = errorText(error);
            if (message.includes('experiment_context')) {
                setContextJsonError(message);
            } else if (message.includes('steps')) {
                setStepsJsonError(message);
            }
            messageApi.error(copy('edit.fixDraftJsonBeforeLaunch'));
            return null;
        }
    };

    const updateContextJson = (text: string) => {
        if (!draft) return;
        try {
            const next = cloneDraft(draft);
            next.experiment_context = parseJsonObject(text, 'experiment_context');
            next.init_config.agents = next.init_config.agents.map((agent) => ({
                ...agent,
                kwargs: {
                    ...agent.kwargs,
                    experiment_context: next.experiment_context,
                    profile: {
                        ...(agent.kwargs?.profile || {}),
                        scenario: String(next.experiment_context.background || ''),
                    },
                },
            }));
            setDraft(next);
            setContextJsonError(null);
            messageApi.success(copy('messages.contextUpdated'));
        } catch (error) {
            const message = errorText(error);
            setContextJsonError(message);
            messageApi.error(copy('edit.contextJsonInvalid', { error: message }));
        }
    };

    const updateStepsJson = (text: string) => {
        if (!draft) return;
        try {
            const next = cloneDraft(draft);
            next.steps = parseJsonObject(text, 'steps');
            setDraft(next);
            setStepsJsonError(null);
            messageApi.success(copy('messages.stepsUpdated'));
        } catch (error) {
            const message = errorText(error);
            setStepsJsonError(message);
            messageApi.error(copy('edit.stepsJsonInvalid', { error: message }));
        }
    };

    const updateEnvField = (key: string, value: any) => {
        if (!draft) return;
        if (value === null || value === undefined) return;
        const next = cloneDraft(draft);
        const env = getEnvModule(next);
        env.kwargs[key] = value;
        setDraft(next);
    };

    const updateInitialLocation = (agentId: number, locationId: string) => {
        if (!draft) return;
        const next = cloneDraft(draft);
        const env = getEnvModule(next);
        env.kwargs.initial_locations = {
            ...(env.kwargs.initial_locations || {}),
            [String(agentId)]: locationId,
        };
        setDraft(next);
    };

    const openAgentModal = (agent?: AgentRecord) => {
        if (!draft) return;
        if (agent) {
            const { id: _id, name, profile, ...rest } = agent.kwargs || {};
            setEditingAgentId(agent.agent_id);
            agentForm.setFieldsValue({
                agent_id: agent.agent_id,
                agent_type: agent.agent_type,
                name: String(name || profile?.name || `Agent ${agent.agent_id}`),
                profile_json: jsonStringify(profile || {}),
                kwargs_json: jsonStringify(rest),
            });
        } else {
            const nextId = draft.init_config.agents.length
                ? Math.max(...draft.init_config.agents.map((item) => item.agent_id)) + 1
                : 1;
            setEditingAgentId(null);
            agentForm.setFieldsValue({
                agent_id: nextId,
                agent_type: 'JiuwenClawAgent',
                name: `Jiuwen Agent ${nextId}`,
                profile_json: jsonStringify({
                    name: `Jiuwen Agent ${nextId}`,
                    role: 'participant',
                    persona: copy('edit.defaultPersona'),
                    scenario: draft.experiment_context.background || '',
                    scenario_role: 'participant',
                }),
                kwargs_json: jsonStringify({
                    jiuwenclaw_ws_url: 'ws://127.0.0.1:19092',
                    session_id: `generated_agent_${nextId}`,
                    mode: 'agent.plan',
                    trusted_dirs: [],
                    enable_memory: true,
                    enable_skill_runtime: true,
                    common_skill_ids: DEFAULT_COMMON_SKILL_IDS,
                    skill_ids: DEFAULT_PERSONAL_SKILL_IDS,
                    request_timeout: 900,
                    channel_id: 'agentsociety',
                    experiment_context: draft.experiment_context,
                }),
            });
        }
        setAgentModalOpen(true);
    };

    const saveAgent = async (baseAgent: AgentRecord, meta?: AgentEditorSaveMeta) => {
        if (!draft) return;
        const profile = baseAgent.kwargs?.profile && typeof baseAgent.kwargs.profile === 'object'
            ? baseAgent.kwargs.profile
            : {};
        const profileWithoutSkills = { ...profile };
        delete profileWithoutSkills.skills;
        const cleanKwargs = { ...(baseAgent.kwargs || {}) };
        delete cleanKwargs.enable_daily_life;
        delete cleanKwargs.daily_life_skill_path;
        delete cleanKwargs.skill_runtime_skill_names;
        const agent: AgentRecord = {
            ...baseAgent,
            kwargs: {
                ...cleanKwargs,
                experiment_context: draft.experiment_context,
                enable_skill_runtime: true,
                common_skill_ids: Array.isArray(cleanKwargs.common_skill_ids) ? cleanKwargs.common_skill_ids : DEFAULT_COMMON_SKILL_IDS,
                skill_ids: Array.isArray(cleanKwargs.skill_ids) ? cleanKwargs.skill_ids : DEFAULT_PERSONAL_SKILL_IDS,
                profile: {
                    ...profileWithoutSkills,
                    scenario: profile.scenario || String(draft.experiment_context.background || ''),
                    scenario_role: profile.scenario_role || profile.role || 'participant',
                },
            },
        };
        const next = cloneDraft(draft);
        next.init_config.agents = editingAgentId === null
            ? [...next.init_config.agents, agent]
            : next.init_config.agents.map((item) => item.agent_id === editingAgentId ? agent : item);
        const env = getEnvModule(next);
        env.kwargs.agent_id_name_pairs = next.init_config.agents.map((item) => [item.agent_id, agentName(item)]);
        const nextInitialLocation = meta?.initial_location
            || env.kwargs.initial_locations?.[String(agent.agent_id)]
            || locationOptions[0]?.value
            || '';
        env.kwargs.initial_locations = {
            ...(env.kwargs.initial_locations || {}),
        };
        if (nextInitialLocation) {
            env.kwargs.initial_locations[String(agent.agent_id)] = nextInitialLocation;
        } else {
            delete env.kwargs.initial_locations[String(agent.agent_id)];
        }
        setDraft(next);
        setAgentModalOpen(false);
    };

    const completeRoleImages = async () => {
        if (!draft) return;
        setCompletingRoleImages(true);
        try {
            const result = await fetchJson<CompleteRoleVisualsResponse>('/api/v1/god/setup/agent-studio/complete-role-visuals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ draft }),
            });
            setDraft(result.draft);
            if (result.failed_count > 0) {
                messageApi.warning(copy('messages.roleImagesPartial', {
                    completed: result.completed_count,
                    failed: result.failed_count,
                }));
            } else {
                messageApi.success(copy('messages.roleImagesCompleted', {
                    completed: result.completed_count,
                }));
            }
        } catch (error) {
            messageApi.error(copy('messages.roleImagesFailed', { error: errorText(error) }));
        } finally {
            setCompletingRoleImages(false);
        }
    };

    const deleteAgent = (agentId: number) => {
        if (!draft) return;
        const next = cloneDraft(draft);
        next.init_config.agents = next.init_config.agents.filter((agent) => agent.agent_id !== agentId);
        const env = getEnvModule(next);
        env.kwargs.agent_id_name_pairs = next.init_config.agents.map((agent) => [agent.agent_id, agentName(agent)]);
        if (env.kwargs.initial_locations) {
            delete env.kwargs.initial_locations[String(agentId)];
        }
        setDraft(next);
    };

    const publishAndStart = async () => {
        if (!draft) return;
        if (draftJsonHasErrors) {
            messageApi.error(copy('edit.fixDraftJsonBeforeLaunch'));
            return;
        }
        const publishDraft = commitDraftJsonEdits();
        if (!publishDraft) return;
        const modelValues = await modelForm.validateFields();
        setPublishing(true);
        try {
            const result = await fetchJson<LaunchResult & { warnings?: string[] }>('/api/v1/god/setup/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    draft: publishDraft,
                    model_config: modelValues,
                    start_immediately: true,
                }),
            });
            const setupMode = Boolean(status?.setup_mode);
            messageApi.success(setupMode ? copy('messages.publishedQueued') : copy('messages.published'));
            setCurrentStep(5);
            completeLaunch(result, setupMode, 1000);
        } catch (error) {
            messageApi.error(copy('messages.publishFailed', { error: errorText(error) }));
        } finally {
            setPublishing(false);
        }
    };

    const agentColumns: ColumnsType<AgentRecord> = [
        { title: copy('edit.table.id'), dataIndex: 'agent_id', width: 70 },
        { title: copy('edit.table.name'), render: (_, record) => agentName(record), width: 180 },
        {
            title: copy('edit.table.role'),
            render: (_, record) => String(record.kwargs?.profile?.role || record.kwargs?.profile?.scenario_role || '-'),
            width: 180,
        },
        {
            title: copy('edit.table.initialLocation'),
            width: 260,
            render: (_, record) => (
                <Select
                    value={getEnvModule(draft!).kwargs.initial_locations?.[String(record.agent_id)]}
                    options={locationOptions}
                    style={{ width: '100%' }}
                    onChange={(value) => updateInitialLocation(record.agent_id, value)}
                />
            ),
        },
        {
            title: copy('edit.table.profile'),
            render: (_, record) => (
                <Tooltip title={<pre className="setup-json-preview">{jsonStringify(record.kwargs?.profile)}</pre>}>
                    <Text code>{compactJson(record.kwargs?.profile)}</Text>
                </Tooltip>
            ),
        },
        {
            title: copy('edit.table.roleImage'),
            width: 150,
            render: (_, record) => (
                agentCharacterSprite(record)
                    ? <Tag color="green">{copy('edit.roleImageReady')}</Tag>
                    : <Tag>{copy('edit.roleImageMissing')}</Tag>
            ),
        },
        {
            title: copy('edit.table.actions'),
            width: 104,
            render: (_, record) => (
                <Space size={6}>
                    <Tooltip title={copy('edit.table.editAgent')}>
                        <Button
                            size="small"
                            icon={<EditOutlined />}
                            aria-label={copy('edit.table.editAgent')}
                            title={copy('edit.table.editAgent')}
                            onClick={() => openAgentModal(record)}
                        />
                    </Tooltip>
                    <Tooltip title={copy('edit.table.deleteAgent')}>
                        <Button
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                            aria-label={copy('edit.table.deleteAgent')}
                            title={copy('edit.table.deleteAgent')}
                            onClick={() => deleteAgent(record.agent_id)}
                        />
                    </Tooltip>
                </Space>
            ),
        },
    ];

    const renderModelStep = () => (
        <Card className="setup-card" title={<Space><ApiOutlined />{copy('model.title')}</Space>}>
            <Alert
                type="info"
                showIcon
                message={copy('model.notice')}
                style={{ marginBottom: 18 }}
            />
            {renderLaunchPendingAlert()}
            <Form form={modelForm} layout="vertical">
                <Row gutter={16}>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_API_KEY"
                            label={formLabel(copy('model.apiKey'), copy('model.apiKeyTooltip'))}
                        >
                            <Input.Password placeholder={status?.model_config.GOD_LLM_API_KEY?.configured ? copy('model.apiKeyConfiguredPlaceholder') : copy('model.apiKeyPlaceholder')} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_API_BASE"
                            label={formLabel(copy('model.apiBase'), copy('model.apiBaseTooltip'))}
                            rules={[{ required: true }]}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_MODEL"
                            label={formLabel(copy('model.modelName'), copy('model.modelTooltip'))}
                            rules={[{ required: true, message: copy('model.modelRequired') }]}
                        >
                            <Input placeholder={copy('model.modelPlaceholder')} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_API_KEY"
                            label={formLabel(copy('model.embeddingKey'), copy('model.embeddingKeyTooltip'))}
                        >
                            <Input.Password placeholder={status?.model_config.GOD_EMBEDDING_API_KEY?.configured ? copy('model.embeddingConfiguredPlaceholder') : copy('model.embeddingPlaceholder')} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_API_BASE"
                            label={formLabel(copy('model.embeddingBase'), copy('model.embeddingBaseTooltip'))}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_MODEL"
                            label={formLabel(copy('model.embeddingModel'), copy('model.embeddingModelTooltip'))}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item name="GOD_BACKEND_HOST" label={formLabel(copy('model.backendHost'), copy('model.backendHostTooltip'))}>
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={8}>
                        <Form.Item name="GOD_BACKEND_PORT" label={formLabel(copy('model.backendPort'), copy('model.backendPortTooltip'))}>
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={8}>
                        <Form.Item name="GOD_FRONTEND_PORT" label={formLabel(copy('model.frontendPort'), copy('model.frontendPortTooltip'))}>
                            <Input />
                        </Form.Item>
                    </Col>
                </Row>
            </Form>
            <Space wrap>
                <Button icon={<SaveOutlined />} loading={savingModel} onClick={saveModelConfig}>
                    {copy('model.save')}
                </Button>
                <Tag>{status?.model_config.GOD_LLM_API_KEY?.configured ? copy('model.apiKeyConfigured') : copy('model.apiKeyMissing')}</Tag>
                <Text type="secondary">{status?.env_file}</Text>
            </Space>
        </Card>
    );

    const renderBuiltInExperimentModal = () => (
        <Modal
            title={copy('choice.builtinModalTitle')}
            open={builtinModalOpen}
            onCancel={() => setBuiltinModalOpen(false)}
            footer={null}
            width="min(860px, 92vw)"
        >
            <div className="setup-built-in-list">
                {(status?.default_experiments || []).map((item) => (
                    <div className="setup-built-in-item" key={item.key}>
                        <Space direction="vertical" size={10} style={{ width: '100%' }}>
                            <Space wrap>
                                <Title level={4} style={{ margin: 0 }}>{defaultExperimentLabel(item)}</Title>
                                <Tag>{mapDisplayName((status?.maps || []).find((map) => map.map_id === item.map_id), item.map_id)}</Tag>
                            </Space>
                            <Text type="secondary">{defaultExperimentDescription(item)}</Text>
                            <Text code>{item.hypothesis_id} / experiment_{item.experiment_id}</Text>
                            <Space wrap>
                                <Button
                                    type="primary"
                                    icon={<PlayCircleOutlined />}
                                    loading={startingDefault === item.key}
                                    disabled={!item.config_exists}
                                    onClick={() => startDefaultExperiment(item.key)}
                                >
                                    {copy('choice.openDefault')}
                                </Button>
                            </Space>
                        </Space>
                    </div>
                ))}
            </div>
        </Modal>
    );

    const renderExperimentChoiceStep = () => (
        <Card className="setup-card" title={<Space><ExperimentOutlined />{copy('choice.title')}</Space>}>
            {renderLaunchPendingAlert()}
            <Alert
                type="info"
                showIcon
                message={copy('choice.notice')}
                description={copy('choice.description')}
                style={{ marginBottom: 18 }}
            />
            <div className="setup-choice-grid">
                <div className="setup-choice-panel">
                    <Space direction="vertical" size={10} style={{ width: '100%' }}>
                        <Title level={4} style={{ margin: 0 }}>{copy('choice.builtinTitle')}</Title>
                        <Text type="secondary">{copy('choice.builtinDescription')}</Text>
                        <Button
                            type="primary"
                            icon={<ExperimentOutlined />}
                            onClick={() => setBuiltinModalOpen(true)}
                        >
                            {copy('choice.chooseBuiltin')}
                        </Button>
                    </Space>
                </div>
                <div className="setup-choice-panel">
                    <Space direction="vertical" size={10} style={{ width: '100%' }}>
                        <Title level={4} style={{ margin: 0 }}>{copy('choice.importTitle')}</Title>
                        <Text type="secondary">{copy('choice.importDescription')}</Text>
                        <Button icon={<ImportOutlined />} onClick={() => setPackageImportOpen('experiment')}>
                            {copy('choice.importExperiment')}
                        </Button>
                    </Space>
                </div>
                <div className="setup-choice-panel">
                    <Space direction="vertical" size={10} style={{ width: '100%' }}>
                        <Title level={4} style={{ margin: 0 }}>{copy('choice.customTitle')}</Title>
                        <Text type="secondary">{copy('choice.customDescription')}</Text>
                        <Button icon={<EditOutlined />} onClick={() => setCurrentStep(2)}>
                            {copy('choice.createCustom')}
                        </Button>
                    </Space>
                </div>
            </div>
        </Card>
    );

    const renderBasicsStep = () => (
        <Card className="setup-card" title={<Space><ExperimentOutlined />{copy('basics.title')}</Space>}>
            <Alert
                type="warning"
                showIcon
                message={copy('basics.notice')}
                style={{ marginBottom: 18 }}
            />
            <Form
                form={basicsForm}
                layout="vertical"
                initialValues={basicsValues}
                onValuesChange={(_, allValues) => {
                    syncBasicsValues({ ...basicsRef.current, ...allValues });
                }}
            >
                <Row gutter={16}>
                    <Col xs={24} lg={12}>
                        <Form.Item
                            name="title"
                            label={formLabel(copy('basics.experimentTitle'), copy('basics.experimentTitleTooltip'))}
                        >
                            <Input placeholder={copy('basics.experimentTitlePlaceholder')} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            label={formLabel(copy('basics.mapPackage'), copy('basics.mapPackageTooltip'))}
                        >
                            <div className="setup-map-picker">
                                <Form.Item name="map_id" noStyle>
                                    <Select
                                        options={mapOptions}
                                        placeholder="the_ville"
                                        optionFilterProp="label"
                                        showSearch
                                        style={{ width: '100%' }}
                                    />
                                </Form.Item>
                                <Tooltip title={copy('basics.importMap')}>
                                    <Button
                                        aria-label={copy('basics.importMap')}
                                        className="setup-map-import-button"
                                        icon={<ImportOutlined />}
                                        onClick={() => setPackageImportOpen('map')}
                                    />
                                </Tooltip>
                            </div>
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="agent_count"
                            label={formLabel(copy('basics.agentCount'), copy('basics.agentCountTooltip'))}
                        >
                            <InputNumber min={1} max={50} placeholder="10" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="num_steps"
                            label={formLabel(copy('basics.initialSteps'), copy('basics.initialStepsTooltip'))}
                        >
                            <InputNumber min={1} max={100} placeholder="4" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="tick"
                            label={formLabel(copy('basics.tick'), copy('basics.tickTooltip'))}
                        >
                            <InputNumber min={1} placeholder="1800" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="start_t"
                            label={formLabel(copy('basics.startTime'), copy('basics.startTimeTooltip'))}
                        >
                            <Input placeholder="2026-05-11T08:20:00+08:00" />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="movement_tiles_per_second"
                            label={formLabel(copy('basics.movementSpeed'), copy('basics.movementSpeedTooltip'))}
                        >
                            <InputNumber min={0.1} step={0.5} placeholder="8" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={4}>
                        <Form.Item
                            name="movement_min_steps_per_trip"
                            label={formLabel(copy('basics.minSteps'), copy('basics.minStepsTooltip'))}
                        >
                            <InputNumber min={1} placeholder="3" style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="language"
                            label={formLabel(copy('basics.outputLanguage'), copy('basics.outputLanguageTooltip'))}
                        >
                            <Select options={[{ value: 'zh', label: copy('basics.chinese') }, { value: 'en', label: copy('basics.english') }]} />
                        </Form.Item>
                    </Col>
                    <Col span={24}>
                        <Form.Item
                            name="background"
                            label={formLabel(copy('basics.background'), copy('basics.backgroundTooltip'))}
                        >
                            <Input.TextArea
                                rows={8}
                                placeholder={copy('basics.backgroundPlaceholder')}
                            />
                        </Form.Item>
                    </Col>
                </Row>
            </Form>
            {selectedMap && (
                <Alert
                    type={selectedMap.validation_status?.ok ? 'info' : 'warning'}
                    showIcon
                    message={copy('basics.mapSummary', {
                        map: mapDisplayName(selectedMap),
                        locations: selectedMap.location_count,
                        interactions: selectedMap.interaction_count,
                        characters: selectedMap.character_count,
                    })}
                    description={
                        selectedMap.validation_status?.ok
                            ? mapManifestDescription(selectedMap)
                            : selectedMap.validation_status?.errors?.join(' ')
                    }
                    style={{ marginBottom: 16 }}
                />
            )}
            {selectedMap && selectedMap.character_count === 0 && (
                <Alert
                    type="info"
                    showIcon
                    message={copy('basics.noRoleImagesTitle')}
                    description={copy('basics.noRoleImagesDescription')}
                    style={{ marginBottom: 16 }}
                />
            )}
            <Space>
                <Button onClick={() => setCurrentStep(1)}>{copy('basics.back')}</Button>
                <Button
                    type="primary"
                    onClick={async () => {
                        try {
                            await persistBasicsFromForm();
                            setCurrentStep(3);
                        } catch {
                            // Ant Design has already marked the invalid fields.
                        }
                    }}
                >
                    {copy('basics.continue')}
                </Button>
            </Space>
        </Card>
    );

    const renderGenerateStep = () => (
        <Card className="setup-card" title={<Space><RobotOutlined />{copy('generate.title')}</Space>}>
            <div className="setup-generate-panel">
                <div>
                    <Title level={4}>{copy('generate.heading')}</Title>
                    <Paragraph type="secondary">
                        {copy('generate.description')}
                    </Paragraph>
                    <Space wrap>
                        <Tag color="blue">{copy('generate.tagMap', { map: mapDisplayName(selectedMap) })}</Tag>
                        <Tag color="green">{copy('generate.tagProfiles')}</Tag>
                        <Tag color="purple">{copy('generate.tagCopy')}</Tag>
                    </Space>
                </div>
                <Button
                    type="primary"
                    size="large"
                    icon={<ThunderboltOutlined />}
                    loading={generating}
                    onClick={generateDraft}
                >
                    {copy('generate.generate')}
                </Button>
            </div>
            <Divider />
            <Alert
                type="info"
                showIcon
                message={copy('generate.previewTitle')}
                description={(
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        <Text>{copy('generate.previewExperimentTitle', { title: basicsValues.title })}</Text>
                        <Text>{copy('generate.previewMap', { map: mapDisplayName(selectedMap) })}</Text>
                        <Text>
                            {copy('generate.previewSchedule', {
                                agents: basicsValues.agent_count,
                                steps: basicsValues.num_steps,
                                tick: basicsValues.tick,
                                start: basicsValues.start_t,
                            })}
                        </Text>
                        <Text>
                            {copy('generate.previewMovement', {
                                speed: basicsValues.movement_tiles_per_second,
                                minSteps: basicsValues.movement_min_steps_per_trip,
                            })}
                        </Text>
                        <Paragraph style={{ marginBottom: 0 }}>
                            {copy('generate.previewBackground', { background: basicsValues.background })}
                        </Paragraph>
                    </Space>
                )}
                style={{ marginBottom: 16 }}
            />
            <Space>
                <Button onClick={() => setCurrentStep(2)}>{copy('generate.back')}</Button>
                <Button
                    disabled={!draft && !latestDraftAvailable}
                    onClick={async () => {
                        if (draft) {
                            setCurrentStep(4);
                            return;
                        }
                        const loaded = await loadLatestDraft(true);
                        if (!loaded) {
                            messageApi.info(copy('generate.noDraft'));
                        }
                    }}
                >
                    {copy('generate.viewDraft')}
                </Button>
            </Space>
        </Card>
    );

    const renderEditStep = () => {
        if (!draft) {
            return (
                <Card className="setup-card">
                    <Alert type="info" showIcon message={copy('generate.noDraft')} />
                </Card>
            );
        }
        const env = getEnvModule(draft);
        return (
            <Card className="setup-card" title={<Space><EditOutlined />{copy('edit.title')}</Space>}>
                {draft.warnings?.length > 0 && (
                    <Alert
                        type="warning"
                        showIcon
                        message={copy('edit.mapWarning')}
                        description={draft.warnings.join(' ')}
                        style={{ marginBottom: 16 }}
                    />
                )}
                <Tabs
                    items={[
                        {
                            key: 'context',
                            label: copy('edit.contextTab'),
                            children: (
                                <Space direction="vertical" style={{ width: '100%' }}>
                                    <Alert
                                        type="info"
                                        showIcon
                                        message={copy('edit.contextNotice')}
                                    />
                                    <Input.TextArea
                                        rows={16}
                                        value={contextJsonText}
                                        status={contextJsonError ? 'error' : undefined}
                                        spellCheck={false}
                                        onChange={(event) => {
                                            setContextJsonText(event.target.value);
                                            validateContextJsonText(event.target.value);
                                        }}
                                        onBlur={(event) => updateContextJson(event.target.value)}
                                    />
                                    {contextJsonError && (
                                        <Alert
                                            type="error"
                                            showIcon
                                            message={copy('edit.contextJsonInvalid', { error: contextJsonError })}
                                        />
                                    )}
                                </Space>
                            ),
                        },
                        {
                            key: 'agents',
                            label: copy('edit.agentsTab', { count: draft.init_config.agents.length }),
                            children: (
                                <>
                                    <Space wrap style={{ marginBottom: 12 }}>
                                        <Button type="primary" icon={<UserAddOutlined />} onClick={() => openAgentModal()}>
                                            {copy('edit.addAgent')}
                                        </Button>
                                        <Button loading={completingRoleImages} onClick={completeRoleImages}>
                                            {copy('edit.completeRoleImages')}
                                        </Button>
                                        <Tag>{copy('edit.roleImageCount', {
                                            completed: roleImageCount(draft.init_config.agents),
                                            total: draft.init_config.agents.length,
                                        })}</Tag>
                                    </Space>
                                    <Alert
                                        type="info"
                                        showIcon
                                        message={copy('edit.roleImageNotice')}
                                        style={{ marginBottom: 12 }}
                                    />
                                    <Table
                                        rowKey="agent_id"
                                        columns={agentColumns}
                                        dataSource={draft.init_config.agents}
                                        pagination={{ pageSize: 8 }}
                                    />
                                </>
                            ),
                        },
                        {
                            key: 'env',
                            label: copy('edit.envTab'),
                            children: (
                                <Row gutter={16}>
                                    <Col xs={24} lg={8}>
                                        <Text strong>{copy('edit.groupName')}</Text>
                                        <Input
                                            value={env.kwargs.default_group_name}
                                            onChange={(event) => updateEnvField('default_group_name', event.target.value)}
                                            style={{ marginTop: 8 }}
                                        />
                                    </Col>
                                    <Col xs={12} lg={8}>
                                        <Text strong>{copy('edit.movementSpeed')}</Text>
                                        <InputNumber
                                            value={env.kwargs.movement_tiles_per_second}
                                            min={0.1}
                                            step={0.5}
                                            onChange={(value) => updateEnvField('movement_tiles_per_second', value)}
                                            style={{ width: '100%', marginTop: 8 }}
                                        />
                                    </Col>
                                    <Col xs={12} lg={8}>
                                        <Text strong>{copy('edit.minSteps')}</Text>
                                        <InputNumber
                                            value={env.kwargs.movement_min_steps_per_trip}
                                            min={1}
                                            onChange={(value) => updateEnvField('movement_min_steps_per_trip', value)}
                                            style={{ width: '100%', marginTop: 8 }}
                                        />
                                    </Col>
                                </Row>
                            ),
                        },
                        {
                            key: 'steps',
                            label: copy('edit.stepsTab'),
                            children: (
                                <>
                                    <Input.TextArea
                                        rows={16}
                                        value={stepsJsonText}
                                        status={stepsJsonError ? 'error' : undefined}
                                        spellCheck={false}
                                        onChange={(event) => {
                                            setStepsJsonText(event.target.value);
                                            validateStepsJsonText(event.target.value);
                                        }}
                                        onBlur={(event) => updateStepsJson(event.target.value)}
                                    />
                                    {stepsJsonError && (
                                        <Alert
                                            type="error"
                                            showIcon
                                            message={copy('edit.stepsJsonInvalid', { error: stepsJsonError })}
                                            style={{ marginTop: 12 }}
                                        />
                                    )}
                                </>
                            ),
                        },
                    ]}
                />
                <Divider />
                <Space>
                    <Button onClick={() => setCurrentStep(3)}>{copy('edit.backToGenerate')}</Button>
                    <Button
                        type="primary"
                        disabled={draftJsonHasErrors}
                        onClick={() => {
                            const next = commitDraftJsonEdits();
                            if (next) {
                                setCurrentStep(5);
                            }
                        }}
                    >
                        {copy('edit.confirmLaunch')}
                    </Button>
                </Space>
                {draftJsonHasErrors && (
                    <Alert
                        type="error"
                        showIcon
                        message={copy('edit.fixDraftJsonBeforeLaunch')}
                        style={{ marginTop: 16 }}
                    />
                )}
            </Card>
        );
    };

    const renderConfirmStep = () => (
        <Card className="setup-card" title={<Space><CheckCircleOutlined />{copy('confirm.title')}</Space>}>
            {draft ? (
                <>
                    {renderLaunchPendingAlert(16)}
                    <div className="setup-confirm-grid">
                        <div>
                            <Text type="secondary">{copy('confirm.experimentTitle')}</Text>
                            <Title level={4}>{String(draft.experiment_context.title || copy('confirm.customExperiment'))}</Title>
                        </div>
                        <div>
                            <Text type="secondary">{copy('confirm.agentCount')}</Text>
                            <Title level={4}>{draft.init_config.agents.length}</Title>
                        </div>
                        <div>
                            <Text type="secondary">{copy('confirm.workspace')}</Text>
                            <Paragraph copyable>{status?.workspace_path}</Paragraph>
                        </div>
                    </div>
                    <Alert
                        type="success"
                        showIcon
                        message={copy('confirm.safeCopyTitle')}
                        description={copy('confirm.safeCopyDescription')}
                        style={{ marginBottom: 16 }}
                    />
                    <Space wrap>
                        <Button onClick={() => setCurrentStep(4)}>{copy('confirm.keepEditing')}</Button>
                        <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            loading={publishing}
                            disabled={draftJsonHasErrors}
                            onClick={publishAndStart}
                        >
                            {copy('confirm.saveAndLaunch')}
                        </Button>
                    </Space>
                    {draftJsonHasErrors && (
                        <Alert
                            type="error"
                            showIcon
                            message={copy('edit.fixDraftJsonBeforeLaunch')}
                            style={{ marginTop: 16 }}
                        />
                    )}
                </>
            ) : (
                <Alert type="info" showIcon message={copy('confirm.noPublishableDraft')} />
            )}
        </Card>
    );

    const stepItems = [
        { title: copy('steps.model'), icon: <ApiOutlined /> },
        { title: copy('steps.choose'), icon: <PlayCircleOutlined /> },
        { title: copy('steps.params'), icon: <ExperimentOutlined /> },
        { title: copy('steps.generate'), icon: <RobotOutlined /> },
        { title: copy('steps.edit'), icon: <EditOutlined /> },
        { title: copy('steps.launch'), icon: <PlayCircleOutlined /> },
    ];

    const content = [
        renderModelStep,
        renderExperimentChoiceStep,
        renderBasicsStep,
        renderGenerateStep,
        renderEditStep,
        renderConfirmStep,
    ][currentStep]();

    return (
        <div className="setup-page">
            {messageContextHolder}
            {currentStep !== 2 && <Form form={basicsForm} component={false} />}
            <div className="setup-shell">
                <div className="setup-header">
                    <div>
                        <Title level={2}>{copy('header.title')}</Title>
                        <Text type="secondary">
                            {copy('header.subtitle')}
                        </Text>
                    </div>
                    <Space wrap>
                        <LanguageToggle />
                        <Button icon={<CompassOutlined />} onClick={() => navigate('/map-studio')}>
                            {copy('header.mapStudio')}
                        </Button>
                        {status?.current_experiment?.hypothesis_id && (
                            <Button onClick={() => navigate(`/pixel-replay/${status.current_experiment?.hypothesis_id}/${status.current_experiment?.experiment_id || '1'}?workspace_path=${encodeURIComponent(status.current_experiment?.workspace_path || status.workspace_path)}`)}>
                                {copy('header.openCurrent')}
                            </Button>
                        )}
                        <Button onClick={loadStatus} loading={loadingStatus}>{copy('header.refreshStatus')}</Button>
                    </Space>
                </div>
                <Card className="setup-step-card" variant="borderless">
                    <Steps current={currentStep} items={stepItems} onChange={(nextStep) => { void goToStep(nextStep); }} />
                </Card>
                {content}
            </div>
            {draft && (
                <AgentEditorModal
                    open={agentModalOpen}
                    editingAgentId={editingAgentId}
                    form={agentForm}
                    width={980}
                    minAgentId={1}
                    experimentContext={draft.experiment_context}
                    mapId={selectedMapId}
                    mapLocations={mapLocations}
                    existingAgents={draft.init_config.agents}
                    initialLocation={editingAgentId === null ? undefined : getEnvModule(draft).kwargs.initial_locations?.[String(editingAgentId)]}
                    defaultInitialLocation={locationOptions[0]?.value}
                    onSave={saveAgent}
                    onCancel={() => setAgentModalOpen(false)}
                />
            )}
            {renderBuiltInExperimentModal()}
            <PackageImportModal
                open={Boolean(packageImportOpen)}
                expectedType={packageImportOpen || undefined}
                startExperimentOnInstall={packageImportOpen === 'experiment'}
                onCancel={() => setPackageImportOpen(false)}
                onInstalled={handlePackageInstalled}
            />
        </div>
    );
}
