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
    DeleteOutlined,
    EditOutlined,
    ExperimentOutlined,
    GlobalOutlined,
    PlayCircleOutlined,
    QuestionCircleOutlined,
    RobotOutlined,
    SaveOutlined,
    ThunderboltOutlined,
    UserAddOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchCustom } from '../../components/fetch';
import { AgentEditorModal } from '../AgentBuilder/AgentEditorModal';
import {
    jsonStringify,
    parseJsonObject,
    type AgentFormValues,
    type AgentRecord,
} from '../AgentBuilder/agentEditor';
import './style.css';

const { Text, Title, Paragraph } = Typography;

type RedactedValue = {
    configured: boolean;
    value: string;
};

type MapLocation = {
    id: string;
    name: string;
    aliases?: string[];
    interaction_ids?: string[];
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
        hypothesis_id?: string;
        experiment_id?: string;
        workspace_path?: string;
        config_exists?: boolean;
    };
    needs_setup: boolean;
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

const help = (text: string) => (
    <Tooltip title={text}>
        <QuestionCircleOutlined className="setup-help-icon" />
    </Tooltip>
);

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
    title: '斯坦福监狱实验适配模拟',
    background: '请生成一个安全、边界清晰的社会角色压力模拟：参与者被分配为管理者、观察者、普通参与者等角色，重点观察权力、规则、协作和情绪变化，不允许羞辱、伤害或强迫行为。',
    agent_count: 10,
    language: 'zh',
    start_t: '2026-05-11T08:20:00+08:00',
    num_steps: 4,
    tick: 1800,
    movement_tiles_per_second: 8,
    movement_min_steps_per_trip: 3,
};

const defaultBasicsEn: BasicsForm = {
    title: 'Stanford Prison Adaptation',
    background: 'Generate a safe, bounded social role-pressure simulation. Participants are assigned roles such as coordinators, observers, and ordinary participants. Focus on power, rules, cooperation, and emotional changes without humiliation, harm, threats, or coercion.',
    agent_count: 10,
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

const loadStoredBasics = (defaults: BasicsForm = defaultBasics): BasicsForm => {
    if (typeof window === 'undefined') {
        return defaults;
    }
    try {
        const raw = window.localStorage.getItem(BASICS_STORAGE_KEY);
        return raw ? normalizeBasicsValues(JSON.parse(raw), defaults) : defaults;
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
    && left.language === right.language
    && left.start_t === right.start_t
    && left.num_steps === right.num_steps
    && left.tick === right.tick
    && left.movement_tiles_per_second === right.movement_tiles_per_second
    && left.movement_min_steps_per_trip === right.movement_min_steps_per_trip
);

export default function SetupPage() {
    const navigate = useNavigate();
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
    const [startingDefault, setStartingDefault] = useState(false);
    const [launchPending, setLaunchPending] = useState<LaunchResult | null>(null);
    const [agentModalOpen, setAgentModalOpen] = useState(false);
    const [editingAgentId, setEditingAgentId] = useState<number | null>(null);
    const [basicsValues, setBasicsValues] = useState<BasicsForm>(() => loadStoredBasics(localizedDefaultBasics));
    const basicsRef = useRef<BasicsForm>(basicsValues);
    const previousDefaultBasicsRef = useRef<BasicsForm>(localizedDefaultBasics);
    const [agentForm] = Form.useForm<AgentFormValues>();
    const [modelForm] = Form.useForm<ModelForm>();
    const [basicsForm] = Form.useForm<BasicsForm>();
    const nextLanguage = i18n.language?.startsWith('en') ? 'zh' : 'en';

    const locationOptions = useMemo(() => (
        (status?.map_locations || []).map((location) => ({
            value: location.id,
            label: `${location.name} (${location.id})`,
        }))
    ), [status?.map_locations]);

    const loadStatus = async () => {
        setLoadingStatus(true);
        try {
            const payload = await fetchJson<SetupStatus>('/api/v1/god/setup/status');
            setStatus(payload);
            modelForm.setFieldsValue({
                GOD_LLM_API_BASE: payload.model_config.GOD_LLM_API_BASE?.value || 'https://api.openai.com/v1',
                GOD_LLM_MODEL: payload.model_config.GOD_LLM_MODEL?.value || 'gpt-5.4',
                GOD_EMBEDDING_API_BASE: payload.model_config.GOD_EMBEDDING_API_BASE?.value || '',
                GOD_EMBEDDING_MODEL: payload.model_config.GOD_EMBEDDING_MODEL?.value || 'text-embedding-3-large',
                GOD_BACKEND_HOST: payload.model_config.GOD_BACKEND_HOST?.value || '127.0.0.1',
                GOD_BACKEND_PORT: payload.model_config.GOD_BACKEND_PORT?.value || '8001',
                GOD_FRONTEND_PORT: payload.model_config.GOD_FRONTEND_PORT?.value || '5174',
            });
        } catch (error) {
            messageApi.error(copy('messages.loadStatusFailed', { error: errorText(error) }));
        } finally {
            setLoadingStatus(false);
        }
    };

    useEffect(() => {
        loadStatus();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (currentStep === 1) {
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

    useEffect(() => {
        const previousDefaults = previousDefaultBasicsRef.current;
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
        if (currentStep === 1 && targetStep > 1) {
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
        const basicsPayload = currentStep === 1
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
            setCurrentStep(3);
            messageApi.success(copy('messages.draftGenerated'));
        } catch (error) {
            messageApi.error(copy('messages.generateDraftFailed', { error: errorText(error) }));
        } finally {
            setGenerating(false);
        }
    };

    const startDefaultExperiment = async () => {
        const modelValues = await modelForm.validateFields();
        if (!status?.model_config.GOD_LLM_API_KEY?.configured && !String(modelValues.GOD_LLM_API_KEY || '').trim()) {
            messageApi.error(copy('messages.apiKeyRequired'));
            return;
        }
        setStartingDefault(true);
        try {
            const nextStatus = await persistModelConfig(modelValues);
            setStatus(nextStatus);
            const result = await fetchJson<LaunchResult>('/api/v1/god/setup/start-default', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const setupMode = Boolean(nextStatus.setup_mode || status?.setup_mode);
            messageApi.success(setupMode ? copy('messages.defaultQueued') : copy('messages.defaultStarted'));
            completeLaunch(result, setupMode, 700);
        } catch (error) {
            messageApi.error(copy('messages.defaultStartFailed', { error: errorText(error) }));
        } finally {
            setStartingDefault(false);
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
            messageApi.success(copy('messages.contextUpdated'));
        } catch (error) {
            messageApi.error(errorText(error));
        }
    };

    const updateStepsJson = (text: string) => {
        if (!draft) return;
        try {
            const next = cloneDraft(draft);
            next.steps = parseJsonObject(text, 'steps');
            setDraft(next);
            messageApi.success(copy('messages.stepsUpdated'));
        } catch (error) {
            messageApi.error(errorText(error));
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
                    skills: ['observation', 'conversation'],
                    scenario: draft.experiment_context.background || '',
                    scenario_role: 'participant',
                }),
                kwargs_json: jsonStringify({
                    jiuwenclaw_ws_url: 'ws://127.0.0.1:19092',
                    session_id: `generated_agent_${nextId}`,
                    mode: 'agent.plan',
                    trusted_dirs: [],
                    enable_memory: true,
                    enable_daily_life: true,
                    enable_skill_runtime: true,
                    request_timeout: 900,
                    channel_id: 'agentsociety',
                    experiment_context: draft.experiment_context,
                }),
            });
        }
        setAgentModalOpen(true);
    };

    const saveAgent = async (baseAgent: AgentRecord) => {
        if (!draft) return;
        const profile = baseAgent.kwargs?.profile && typeof baseAgent.kwargs.profile === 'object'
            ? baseAgent.kwargs.profile
            : {};
        const agent: AgentRecord = {
            ...baseAgent,
            kwargs: {
                ...baseAgent.kwargs,
                experiment_context: draft.experiment_context,
                profile: {
                    ...profile,
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
        env.kwargs.initial_locations = {
            ...(env.kwargs.initial_locations || {}),
            [String(agent.agent_id)]: env.kwargs.initial_locations?.[String(agent.agent_id)] || locationOptions[0]?.value || 'park',
        };
        setDraft(next);
        setAgentModalOpen(false);
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
        const modelValues = await modelForm.validateFields();
        setPublishing(true);
        try {
            const result = await fetchJson<LaunchResult & { warnings?: string[] }>('/api/v1/god/setup/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    draft,
                    model_config: modelValues,
                    start_immediately: true,
                }),
            });
            const setupMode = Boolean(status?.setup_mode);
            messageApi.success(setupMode ? copy('messages.publishedQueued') : copy('messages.published'));
            setCurrentStep(4);
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
            title: copy('edit.table.actions'),
            width: 104,
            render: (_, record) => (
                <Space size={6}>
                    <Button size="small" icon={<EditOutlined />} onClick={() => openAgentModal(record)} />
                    <Button size="small" danger icon={<DeleteOutlined />} onClick={() => deleteAgent(record.agent_id)} />
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
            {launchPending && (
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
                    style={{ marginBottom: 18 }}
                />
            )}
            <Form form={modelForm} layout="vertical">
                <Row gutter={16}>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_API_KEY"
                            label={formLabel('API key', copy('model.apiKeyTooltip'))}
                        >
                            <Input.Password placeholder={status?.model_config.GOD_LLM_API_KEY?.configured ? copy('model.apiKeyConfiguredPlaceholder') : copy('model.apiKeyPlaceholder')} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_API_BASE"
                            label={formLabel('API base URL', copy('model.apiBaseTooltip'))}
                            rules={[{ required: true }]}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_LLM_MODEL"
                            label={formLabel('Model', copy('model.modelTooltip'))}
                            rules={[{ required: true }]}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_API_KEY"
                            label={formLabel('Embedding key', copy('model.embeddingKeyTooltip'))}
                        >
                            <Input.Password placeholder={status?.model_config.GOD_EMBEDDING_API_KEY?.configured ? copy('model.embeddingConfiguredPlaceholder') : copy('model.embeddingPlaceholder')} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_API_BASE"
                            label={formLabel('Embedding base URL', copy('model.embeddingBaseTooltip'))}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item
                            name="GOD_EMBEDDING_MODEL"
                            label={formLabel('Embedding model', copy('model.embeddingModelTooltip'))}
                        >
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={24} lg={8}>
                        <Form.Item name="GOD_BACKEND_HOST" label={formLabel('Backend host', copy('model.backendHostTooltip'))}>
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={8}>
                        <Form.Item name="GOD_BACKEND_PORT" label={formLabel('Backend port', copy('model.backendPortTooltip'))}>
                            <Input />
                        </Form.Item>
                    </Col>
                    <Col xs={12} lg={8}>
                        <Form.Item name="GOD_FRONTEND_PORT" label={formLabel('Frontend port', copy('model.frontendPortTooltip'))}>
                            <Input />
                        </Form.Item>
                    </Col>
                </Row>
            </Form>
            <Alert
                type="success"
                showIcon
                message={copy('model.fastPathTitle')}
                description={copy('model.fastPathDescription')}
                action={(
                    <Button
                        type="primary"
                        icon={<PlayCircleOutlined />}
                        loading={startingDefault}
                        disabled={status?.default_experiment?.config_exists === false}
                        onClick={startDefaultExperiment}
                    >
                        {copy('model.runDefault')}
                    </Button>
                )}
                style={{ marginBottom: 16 }}
            />
            <Space wrap>
                <Button icon={<SaveOutlined />} loading={savingModel} onClick={saveModelConfig}>
                    {copy('model.save')}
                </Button>
                <Tag>{status?.model_config.GOD_LLM_API_KEY?.configured ? copy('model.apiKeyConfigured') : copy('model.apiKeyMissing')}</Tag>
                <Text type="secondary">{status?.env_file}</Text>
            </Space>
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
            <Space>
                <Button onClick={() => setCurrentStep(0)}>{copy('basics.back')}</Button>
                <Button
                    type="primary"
                    onClick={async () => {
                        try {
                            await persistBasicsFromForm();
                            setCurrentStep(2);
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
                        <Tag color="blue">{copy('generate.tagMap')}</Tag>
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
                <Button onClick={() => setCurrentStep(1)}>{copy('generate.back')}</Button>
                <Button disabled={!draft} onClick={() => setCurrentStep(3)}>{copy('generate.viewDraft')}</Button>
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
                                        defaultValue={jsonStringify(draft.experiment_context)}
                                        spellCheck={false}
                                        onBlur={(event) => updateContextJson(event.target.value)}
                                    />
                                </Space>
                            ),
                        },
                        {
                            key: 'agents',
                            label: copy('edit.agentsTab', { count: draft.init_config.agents.length }),
                            children: (
                                <>
                                    <Space style={{ marginBottom: 12 }}>
                                        <Button type="primary" icon={<UserAddOutlined />} onClick={() => openAgentModal()}>
                                            {copy('edit.addAgent')}
                                        </Button>
                                    </Space>
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
                                <Input.TextArea
                                    rows={16}
                                    defaultValue={jsonStringify(draft.steps)}
                                    spellCheck={false}
                                    onBlur={(event) => updateStepsJson(event.target.value)}
                                />
                            ),
                        },
                    ]}
                />
                <Divider />
                <Space>
                    <Button onClick={() => setCurrentStep(2)}>{copy('edit.backToGenerate')}</Button>
                    <Button type="primary" onClick={() => setCurrentStep(4)}>{copy('edit.confirmLaunch')}</Button>
                </Space>
            </Card>
        );
    };

    const renderConfirmStep = () => (
        <Card className="setup-card" title={<Space><CheckCircleOutlined />{copy('confirm.title')}</Space>}>
            {draft ? (
                <>
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
                    <Space>
                        <Button onClick={() => setCurrentStep(3)}>{copy('confirm.keepEditing')}</Button>
                        <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            loading={publishing}
                            onClick={publishAndStart}
                        >
                            {copy('confirm.saveAndLaunch')}
                        </Button>
                    </Space>
                </>
            ) : (
                <Alert type="info" showIcon message={copy('confirm.noPublishableDraft')} />
            )}
        </Card>
    );

    const stepItems = [
        { title: copy('steps.model'), icon: <ApiOutlined /> },
        { title: copy('steps.params'), icon: <ExperimentOutlined /> },
        { title: copy('steps.generate'), icon: <RobotOutlined /> },
        { title: copy('steps.edit'), icon: <EditOutlined /> },
        { title: copy('steps.launch'), icon: <PlayCircleOutlined /> },
    ];

    const content = [
        renderModelStep,
        renderBasicsStep,
        renderGenerateStep,
        renderEditStep,
        renderConfirmStep,
    ][currentStep]();

    return (
        <div className="setup-page">
            {messageContextHolder}
            {currentStep !== 1 && <Form form={basicsForm} component={false} />}
            <div className="setup-shell">
                <div className="setup-header">
                    <div>
                        <Title level={2}>{copy('header.title')}</Title>
                        <Text type="secondary">
                            {copy('header.subtitle')}
                        </Text>
                    </div>
                    <Space>
                        <Button
                            icon={<GlobalOutlined />}
                            onClick={() => {
                                void i18n.changeLanguage(nextLanguage);
                            }}
                        >
                            {copy('header.language')}
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
            <AgentEditorModal
                open={agentModalOpen}
                editingAgentId={editingAgentId}
                form={agentForm}
                width={820}
                minAgentId={1}
                onSave={saveAgent}
                onCancel={() => setAgentModalOpen(false)}
            />
        </div>
    );
}
