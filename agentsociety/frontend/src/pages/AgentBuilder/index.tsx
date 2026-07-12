import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Button,
    Card,
    Col,
    Divider,
    Form,
    Input,
    Modal,
    Popconfirm,
    Radio,
    Row,
    Select,
    Space,
    Table,
    Tag,
    Tooltip,
    Typography,
    Upload,
    message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
    DeleteOutlined,
    EditOutlined,
    ExportOutlined,
    FolderOpenOutlined,
    ImportOutlined,
    PlusOutlined,
    SaveOutlined,
    UploadOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageToggle from '../../components/LanguageToggle';
import { fetchCustom } from '../../components/fetch';
import PackageImportModal from '../../components/PackageImportModal';
import { localizeMapDisplayName, localizeMapLocationName } from '../../utils/runtimeLocalization';
import { AgentEditorModal, type AgentEditorSaveMeta, type AgentStudioLocation } from './AgentEditorModal';
import {
    jsonStringify,
    type AgentClassInfo,
    type AgentFormValues,
    type AgentRecord,
} from './agentEditor';
import './agentStudio.css';

const { Text, Paragraph } = Typography;

type UnknownRecord = Record<string, unknown>;

type InitConfigPayload = {
    env_modules: Array<{ module_type: string; kwargs: UnknownRecord }>;
    agents: AgentRecord[];
    codegen_router?: { final_summary_enabled?: boolean };
};

type InitConfigResponse = {
    config: InitConfigPayload;
    path: string;
    experiment_context?: UnknownRecord | null;
    map_id?: string | null;
    map_locations?: AgentStudioLocation[];
};

type ImportPreviewRow = {
    row_index: number;
    valid: boolean;
    errors: string[];
    agent?: AgentRecord;
    raw?: UnknownRecord;
};

type ImportPreview = {
    rows: ImportPreviewRow[];
    valid_count: number;
    invalid_count: number;
};

type AgentPackSprite = {
    path: string;
    name?: string;
    frame_width?: number;
    frame_height?: number;
};

type AgentPackAgent = {
    id: string;
    name: string;
    profile?: Record<string, any>;
    runtime?: {
        agent_type?: string;
        kwargs?: Record<string, any>;
    };
    sprite?: AgentPackSprite;
};

type AgentPackSummary = {
    pack_id: string;
    display_name: string;
    scope: 'global' | 'map';
    map_id?: string | null;
    agents: AgentPackAgent[];
};

const agentPackSelectionKey = (pack: AgentPackSummary) => JSON.stringify({
    scope: pack.scope,
    map_id: pack.map_id || null,
    pack_id: pack.pack_id,
});

type AgentBuilderPanelProps = {
    initialWorkspacePath?: string;
    initialHypothesisId?: string;
    initialExperimentId?: string;
    embedded?: boolean;
    autoLoad?: boolean;
    autoSaveOnAgentSave?: boolean;
    onSaved?: () => void | Promise<void>;
};

type DefaultProfile = {
    name: string;
    role: string;
    persona: string;
    goal: string;
};

const DEFAULT_PROFILE: DefaultProfile = {
    name: '',
    role: 'Town resident',
    persona: 'Proactive, reliable, and ready to coordinate with other residents based on current town conditions',
    goal: 'Join daily town coordination and respond to environment changes in the next step.',
};

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

const DEFAULT_JIUWEN_KWARGS = {
    jiuwenclaw_ws_url: 'ws://127.0.0.1:19092',
    session_id: 'god_town_live_agent_1',
    mode: 'agent.plan',
    trusted_dirs: [] as string[],
    enable_memory: true,
    enable_skill_runtime: true,
    common_skill_ids: DEFAULT_COMMON_SKILL_IDS,
    skill_ids: DEFAULT_PERSONAL_SKILL_IDS,
    request_timeout: 900,
    channel_id: 'agentsociety',
};
const STORAGE_KEY = 'agentsociety.agentBuilder.workspacePath';
const SHARED_JIUWEN_KWARG_KEYS = [
    'jiuwenclaw_ws_url',
    'channel_id',
    'mode',
    'trusted_dirs',
    'enable_memory',
    'experiment_context',
    'request_timeout',
] as const;

const EMPTY_AGENTS: AgentRecord[] = [];

const isRecord = (value: unknown): value is UnknownRecord => (
    Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

const asRecord = (value: unknown): UnknownRecord => isRecord(value) ? value : {};

const asStringRecord = (value: unknown): Record<string, string> => Object.fromEntries(
    Object.entries(asRecord(value)).map(([key, item]) => [key, stringValue(item)])
);

const omitKeys = (value: UnknownRecord, keys: string[]) => Object.fromEntries(
    Object.entries(value).filter(([key]) => !keys.includes(key))
);

const getAgentName = (agent: AgentRecord) => {
    const kwargs = agent.kwargs || {};
    const profile = kwargs.profile;
    return String(kwargs.name || (profile && profile.name) || `Agent_${agent.agent_id}`);
};

const getEnvModule = (config: InitConfigPayload | null) => config?.env_modules?.[0];

const stringValue = (value: unknown) => String(value || '').trim();

const basename = (value: string) => value.split('/').filter(Boolean).pop() || value;

const stem = (value: string) => basename(value).replace(/\.[^.]+$/, '');

const storableCharacterAsset = (value: unknown): UnknownRecord | undefined => {
    if (!isRecord(value)) return undefined;
    const asset = value;
    const cleaned = Object.fromEntries(
        [
            'sprite_name',
            'filename',
            'image_url',
            'frame_width',
            'frame_height',
            'source_photo_name',
            'generated_from_photo',
            'source',
        ]
            .map((key) => [key, asset[key]])
            .filter(([, item]) => item !== undefined && item !== null && item !== '')
    );
    return cleaned.sprite_name && cleaned.filename ? cleaned : undefined;
};

const normalizeStudioProfile = (
    profile: UnknownRecord,
    mapId: string,
    initialLocation?: string,
) => {
    const currentStudio = asRecord(profile.agent_studio);
    const appearance = asRecord(profile.appearance);
    const personality = asRecord(profile.personality);
    const routine = asRecord(profile.routine);
    const source = asRecord(currentStudio.source);
    const selectedChoices = asStringRecord(currentStudio.selected_choices);
    const customChoices = asStringRecord(currentStudio.custom_choices);
    const legacyChoices: Record<string, unknown> = {
        identity_role: profile.role,
        identity_function: profile.scenario_role || profile.role,
        appearance_form: appearance.form,
        appearance_eyes: appearance.eyes,
        appearance_hair: appearance.hair,
        appearance_style: appearance.style,
        personality_core: personality.core || profile.persona,
        personality_social: personality.social,
        personality_decision: personality.decision,
        personality_mood: personality.mood,
        routine_goal: routine.goal || profile.goal,
        routine_habit: routine.habit || profile.daily_routine,
        relationship_style: routine.relationship_style || profile.relationships,
    };
    Object.entries(legacyChoices).forEach(([key, raw]) => {
        const value = stringValue(raw);
        if (!value) return;
        if (!selectedChoices[key]) selectedChoices[key] = value;
        if (!customChoices[key] && !asRecord(currentStudio.selected_choices)[key]) customChoices[key] = value;
    });
    selectedChoices.initial_location = stringValue(
        initialLocation || selectedChoices.initial_location || routine.initial_location
    );
    const studioRest = omitKeys(currentStudio, ['groups']);
    const characterAsset = storableCharacterAsset(
        currentStudio.character_asset || source.character_asset || appearance.character_asset
    );
    return {
        ...profile,
        agent_studio: {
            version: 1,
            ...studioRest,
            source: {
                ...source,
                prompt: stringValue(source.prompt),
                mbti: stringValue(profile.mbti || source.mbti) || undefined,
                photo_name: stringValue(source.photo_name || appearance.photo_reference) || undefined,
                character_asset: characterAsset,
            },
            selected_choices: selectedChoices,
            custom_choices: customChoices,
            map_id: mapId,
            character_asset: characterAsset,
        },
    };
};

const normalizeAgentsForStudio = (config: InitConfigPayload, mapId: string): InitConfigPayload => {
    const initialLocations = getEnvModule(config)?.kwargs?.initial_locations || {};
    return {
        ...config,
        agents: (config.agents || []).map((agent) => {
            const profile = agent.kwargs?.profile;
            if (!profile || typeof profile !== 'object' || Array.isArray(profile)) {
                return agent;
            }
            const nextProfile = normalizeStudioProfile(
                profile,
                mapId,
                stringValue(initialLocations[String(agent.agent_id)]),
            );
            return {
                ...agent,
                kwargs: {
                    ...agent.kwargs,
                    profile: nextProfile,
                },
            };
        }),
    };
};

const shortJson = (value: unknown, maxLength = 120) => {
    const text = JSON.stringify(value ?? {});
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
};

const hasHan = (value: string) => /[\u4e00-\u9fff]/.test(value);

const getDuplicateIds = (agents: AgentRecord[]) => {
    const seen = new Set<number>();
    const duplicates = new Set<number>();
    agents.forEach((agent) => {
        if (seen.has(agent.agent_id)) {
            duplicates.add(agent.agent_id);
        }
        seen.add(agent.agent_id);
    });
    return duplicates;
};

const findDefaultAgentType = (classes: AgentClassInfo[]) => {
    if (classes.some((item) => item.type === 'JiuwenClawAgent')) {
        return 'JiuwenClawAgent';
    }
    if (classes.some((item) => item.type === 'PersonAgent')) {
        return 'PersonAgent';
    }
    return classes[0]?.type || 'JiuwenClawAgent';
};

const pickSharedJiuwenKwargs = (kwargs: UnknownRecord | undefined) => {
    const shared: UnknownRecord = {};
    if (!kwargs) return shared;
    SHARED_JIUWEN_KWARG_KEYS.forEach((key) => {
        if (key in kwargs) {
            shared[key] = kwargs[key];
        }
    });
    return shared;
};

const normalizePersonalSkillIds = (value: unknown) => {
    if (!Array.isArray(value)) return DEFAULT_PERSONAL_SKILL_IDS;
    const result: string[] = [];
    value.forEach((item) => {
        const skillId = String(item || '').trim();
        if (skillId && !result.includes(skillId)) {
            result.push(skillId);
        }
    });
    return result.length ? result.slice(0, 5) : DEFAULT_PERSONAL_SKILL_IDS;
};

const normalizeJiuwenRuntimeAgent = (agent: AgentRecord): AgentRecord => {
    if (agent.agent_type !== 'JiuwenClawAgent') return agent;
    const kwargs = { ...(agent.kwargs || {}) };
    delete kwargs.enable_daily_life;
    delete kwargs.daily_life_skill_path;
    delete kwargs.skill_runtime_skill_names;
    return {
        ...agent,
        kwargs: {
            ...kwargs,
            enable_skill_runtime: true,
            common_skill_ids: DEFAULT_COMMON_SKILL_IDS,
            skill_ids: normalizePersonalSkillIds(kwargs.skill_ids),
        },
    };
};

const buildDefaultAgentValues = (
    nextId: number,
    classes: AgentClassInfo[],
    currentAgents: AgentRecord[],
    workspacePath: string,
    defaultProfile: DefaultProfile,
    experimentContext?: UnknownRecord | null,
): AgentFormValues => {
    const agentType = findDefaultAgentType(classes);
    const existing = currentAgents.find((agent) => agent.agent_type === agentType);
    const sharedExisting = pickSharedJiuwenKwargs(existing?.kwargs);
    const name = agentType === 'JiuwenClawAgent' ? `Jiuwen Agent ${nextId}` : `Agent_${nextId}`;
    const profile = {
        ...defaultProfile,
        name,
        scenario: String(experimentContext?.background || ''),
    };
    const kwargs: UnknownRecord = agentType === 'JiuwenClawAgent'
        ? {
            ...DEFAULT_JIUWEN_KWARGS,
            ...sharedExisting,
            trusted_dirs: Array.isArray(sharedExisting.trusted_dirs)
                ? sharedExisting.trusted_dirs
                : (workspacePath ? [workspacePath.replace(/\/quick_experiments$/, '')] : DEFAULT_JIUWEN_KWARGS.trusted_dirs),
            experiment_context: experimentContext || sharedExisting.experiment_context,
            enable_skill_runtime: true,
            common_skill_ids: DEFAULT_COMMON_SKILL_IDS,
            skill_ids: DEFAULT_PERSONAL_SKILL_IDS,
        }
        : {};

    if (typeof kwargs.session_id === 'string') {
        kwargs.session_id = kwargs.session_id.match(/_agent_\d+$/)
            ? kwargs.session_id.replace(/_agent_\d+$/, `_agent_${nextId}`)
            : `${kwargs.session_id}_agent_${nextId}`;
    }

    return {
        agent_id: nextId,
        agent_type: agentType,
        name,
        profile_json: jsonStringify(profile),
        kwargs_json: jsonStringify(kwargs),
    };
};

export const AgentBuilderPanel: React.FC<AgentBuilderPanelProps> = ({
    initialWorkspacePath,
    initialHypothesisId,
    initialExperimentId,
    embedded = false,
    autoLoad = false,
    autoSaveOnAgentSave = false,
    onSaved,
}) => {
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const explicitWorkspacePath = initialWorkspacePath || searchParams.get('workspace_path') || '';
    const explicitHypothesisId = initialHypothesisId || searchParams.get('hypothesis_id') || '';
    const explicitExperimentId = initialExperimentId || searchParams.get('experiment_id') || '';
    const [workspacePath, setWorkspacePath] = useState(
        explicitWorkspacePath ||
        localStorage.getItem(STORAGE_KEY) ||
        import.meta.env.VITE_WORKSPACE_PATH ||
        ''
    );
    const [hypothesisId, setHypothesisId] = useState(explicitHypothesisId || '1');
    const [experimentId, setExperimentId] = useState(explicitExperimentId || '1');
    const [configPath, setConfigPath] = useState('');
    const [config, setConfig] = useState<InitConfigPayload | null>(null);
    const [experimentContext, setExperimentContext] = useState<UnknownRecord | null>(null);
    const [mapId, setMapId] = useState('the_ville');
    const [mapLocations, setMapLocations] = useState<AgentStudioLocation[]>([]);
    const [agentClasses, setAgentClasses] = useState<AgentClassInfo[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [agentModalOpen, setAgentModalOpen] = useState(false);
    const [editingAgentId, setEditingAgentId] = useState<number | null>(null);
    const [agentInitialValues, setAgentInitialValues] = useState<AgentFormValues | null>(null);
    const [importModalOpen, setImportModalOpen] = useState(false);
    const [importFormat, setImportFormat] = useState<'auto' | 'csv' | 'json'>('auto');
    const [importContent, setImportContent] = useState('');
    const [importMode, setImportMode] = useState<'append' | 'replace'>('append');
    const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
    const [agentPackModalOpen, setAgentPackModalOpen] = useState(false);
    const [agentPacks, setAgentPacks] = useState<AgentPackSummary[]>([]);
    const [agentPacksLoading, setAgentPacksLoading] = useState(false);
    const [selectedAgentPackId, setSelectedAgentPackId] = useState<string>();
    const [agentPackImportMode, setAgentPackImportMode] = useState<'append' | 'replace'>('append');
    const [agentPackLocationOverrides, setAgentPackLocationOverrides] = useState<Record<string, string>>({});
    const [agentPackZipImportOpen, setAgentPackZipImportOpen] = useState(false);
    const [form] = Form.useForm<AgentFormValues>();

    const agents = config?.agents ?? EMPTY_AGENTS;
    const hasExplicitContext = Boolean(explicitWorkspacePath && explicitHypothesisId && explicitExperimentId);
    const duplicateIds = useMemo(() => getDuplicateIds(agents), [agents]);
    const hasInvalidAgents = agents.some((agent) => !agent.kwargs || agent.kwargs.id !== agent.agent_id) || duplicateIds.size > 0;
    const defaultProfile = useMemo<DefaultProfile>(() => ({
        ...DEFAULT_PROFILE,
        role: t('agentBuilder.defaults.role'),
        persona: t('agentBuilder.defaults.persona'),
        goal: t('agentBuilder.defaults.goal'),
    }), [t]);
    const agentPackOptions = useMemo(() => agentPacks.map((pack) => ({
        value: agentPackSelectionKey(pack),
        label: `${pack.display_name || pack.pack_id} · ${pack.agents.length} · ${
            pack.scope === 'map'
                ? localizeMapDisplayName({ map_id: pack.map_id || mapId, display_name: pack.map_id || mapId }, i18n.language)
                : 'global'
        }`,
    })), [agentPacks, i18n.language, mapId]);
    const selectedAgentPack = useMemo(
        () => agentPacks.find((pack) => agentPackSelectionKey(pack) === selectedAgentPackId),
        [agentPacks, selectedAgentPackId],
    );

    useEffect(() => {
        if (!selectedAgentPack) {
            setAgentPackLocationOverrides({});
            return;
        }
        const fallbackLocation = mapLocations[0]?.id || '';
        setAgentPackLocationOverrides(Object.fromEntries(
            selectedAgentPack.agents.map((agent) => {
                const routine = asRecord(agent.profile?.routine);
                const initial = stringValue(routine.initial_location);
                const validInitial = mapLocations.some((location) => location.id === initial);
                return [String(agent.id), validInitial ? initial : fallbackLocation];
            })
        ));
    }, [selectedAgentPack, mapLocations]);

    const endpointBase = `/api/v1/experiment-configs/${encodeURIComponent(hypothesisId)}/${encodeURIComponent(experimentId)}`;
    const query = `workspace_path=${encodeURIComponent(workspacePath)}`;
    const jsonPreviewText = (value: unknown, maxLength?: number) => {
        const text = jsonStringify(value);
        if (i18n.language?.startsWith('en') && hasHan(text)) {
            return t('agentBuilder.messages.nonEnglishStoredData');
        }
        return maxLength ? shortJson(value, maxLength) : text;
    };

    useEffect(() => {
        fetchCustom('/api/v1/modules/agent_classes')
            .then((response) => response.ok ? response.json() : Promise.reject(response))
            .then((payload) => setAgentClasses(Object.values(payload.agents || {})))
            .catch((error) => {
                console.error(error);
                message.warning(t('agentBuilder.messages.classesLoadFailed'));
            });
    }, [t]);

    const updateUrlState = () => {
        const params = new URLSearchParams();
        if (workspacePath) params.set('workspace_path', workspacePath);
        if (hypothesisId) params.set('hypothesis_id', hypothesisId);
        if (experimentId) params.set('experiment_id', experimentId);
        if (!embedded) {
            setSearchParams(params);
        }
        if (workspacePath) {
            localStorage.setItem(STORAGE_KEY, workspacePath);
        }
    };

    const loadConfig = async () => {
        if (!workspacePath || !hypothesisId || !experimentId) {
            message.warning(t('agentBuilder.messages.requiredPath'));
            return;
        }
        setLoading(true);
        try {
            updateUrlState();
            const response = await fetchCustom(`${endpointBase}/init?${query}`);
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json() as InitConfigResponse;
            const resolvedMapId = stringValue(
                payload.map_id || payload.experiment_context?.map_id || payload.config.env_modules?.[0]?.kwargs?.map_id
            ) || 'the_ville';
            const normalizedConfig = normalizeAgentsForStudio(payload.config, resolvedMapId);
            setConfig(normalizedConfig);
            setConfigPath(payload.path);
            setExperimentContext(payload.experiment_context || null);
            setMapId(resolvedMapId);
            setMapLocations(payload.map_locations || []);
            message.success(t('agentBuilder.messages.loaded'));
        } catch (error) {
            message.error(t('agentBuilder.messages.loadFailed', { error: error instanceof Error ? error.message : String(error) }));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (autoLoad) {
            loadConfig();
        }
        // Auto-load is only intended for the initial embedded mount.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoLoad]);

    useEffect(() => {
        if (!agentPackModalOpen || !config) return;
        let cancelled = false;
        setAgentPacksLoading(true);
        fetchCustom(`/api/v1/god/agent-packs?map_id=${encodeURIComponent(mapId)}`)
            .then(async (response) => {
                if (!response.ok) throw new Error(await response.text());
                return response.json();
            })
            .then((payload) => {
                if (cancelled) return;
                const packs = Array.isArray(payload.agent_packs) ? payload.agent_packs : [];
                setAgentPacks(packs);
                setSelectedAgentPackId((current) => (
                    current && packs.some((pack: AgentPackSummary) => agentPackSelectionKey(pack) === current)
                        ? current
                        : packs[0] ? agentPackSelectionKey(packs[0]) : undefined
                ));
            })
            .catch((error) => {
                if (!cancelled) {
                    setAgentPacks([]);
                    setSelectedAgentPackId(undefined);
                    message.warning(t('agentBuilder.import.agentPackLoadFailed', { error: error instanceof Error ? error.message : String(error) }));
                }
            })
            .finally(() => {
                if (!cancelled) setAgentPacksLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [agentPackModalOpen, config, mapId, t]);

    const persistConfig = async (targetConfig: InitConfigPayload | null = config) => {
        if (!targetConfig) return false;
        setSaving(true);
        try {
            const response = await fetchCustom(`${endpointBase}/init?${query}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(targetConfig),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json() as InitConfigResponse;
            const resolvedMapId = payload.map_id || mapId;
            setConfig(normalizeAgentsForStudio(payload.config, resolvedMapId));
            setConfigPath(payload.path);
            setExperimentContext(payload.experiment_context || experimentContext);
            setMapId(resolvedMapId);
            setMapLocations(payload.map_locations || mapLocations);
            message.success(t('agentBuilder.messages.saved'));
            return true;
        } catch (error) {
            message.error(t('agentBuilder.messages.saveFailed', { error: error instanceof Error ? error.message : String(error) }));
            return false;
        } finally {
            setSaving(false);
        }
    };

    const saveConfig = async () => {
        if (await persistConfig()) {
            await onSaved?.();
        }
    };

    const openCreateAgent = () => {
        const nextId = agents.length ? Math.max(...agents.map((agent) => agent.agent_id)) + 1 : 1;
        const values = buildDefaultAgentValues(nextId, agentClasses, agents, workspacePath, defaultProfile, experimentContext);
        setEditingAgentId(null);
        setAgentInitialValues(values);
        form.setFieldsValue(values);
        setAgentModalOpen(true);
    };

    const openEditAgent = (agent: AgentRecord) => {
        const profile = asRecord(agent.kwargs?.profile);
        const name = agent.kwargs?.name;
        const extraKwargs = omitKeys(agent.kwargs || {}, ['id', 'name', 'profile']);
        const values = {
            agent_id: agent.agent_id,
            agent_type: agent.agent_type,
            name: String(name || profile.name || `Agent_${agent.agent_id}`),
            profile_json: jsonStringify(profile),
            kwargs_json: jsonStringify(extraKwargs),
        };
        setEditingAgentId(agent.agent_id);
        setAgentInitialValues(values);
        form.setFieldsValue(values);
        setAgentModalOpen(true);
    };

    const syncEnvForAgents = (
        baseConfig: InitConfigPayload,
        nextAgents: AgentRecord[],
        touchedAgent?: AgentRecord,
        meta?: AgentEditorSaveMeta,
    ): InitConfigPayload => {
        const envModules = baseConfig.env_modules.map((module, index) => {
            if (index !== 0) return module;
            const currentLocations = module.kwargs.initial_locations && typeof module.kwargs.initial_locations === 'object'
                ? module.kwargs.initial_locations
                : {};
            const nextLocations = { ...currentLocations };
            if (touchedAgent) {
                const nextLocation = (
                    meta?.initial_location
                    || nextLocations[String(touchedAgent.agent_id)]
                    || mapLocations[0]?.id
                );
                if (nextLocation) {
                    nextLocations[String(touchedAgent.agent_id)] = nextLocation;
                } else {
                    delete nextLocations[String(touchedAgent.agent_id)];
                }
            }
            Object.keys(nextLocations).forEach((agentId) => {
                if (!nextAgents.some((item) => String(item.agent_id) === agentId)) {
                    delete nextLocations[agentId];
                }
            });
            return {
                ...module,
                kwargs: {
                    ...module.kwargs,
                    map_id: module.kwargs.map_id || mapId,
                    agent_id_name_pairs: nextAgents.map((item) => [item.agent_id, getAgentName(item)]),
                    initial_locations: nextLocations,
                },
            };
        });
        return { ...baseConfig, agents: nextAgents, env_modules: envModules };
    };

    const agentPackAssetUrl = (pack: AgentPackSummary, sprite: AgentPackSprite) => {
        const mapParam = pack.scope === 'map' && pack.map_id
            ? `?map_id=${encodeURIComponent(pack.map_id)}`
            : '';
        return `/api/v1/god/agent-packs/${encodeURIComponent(pack.pack_id)}/assets/${sprite.path}${mapParam}`;
    };

    const buildAgentFromPack = (
        pack: AgentPackSummary,
        packAgent: AgentPackAgent,
        nextId: number,
    ): { agent: AgentRecord; initialLocation: string } => {
        const profile = { ...(packAgent.profile || {}) };
        const knownLocations = new Set(mapLocations.map((location) => location.id));
        const routine = asRecord(profile.routine);
        const rawInitialLocation = stringValue(routine.initial_location);
        const overrideLocation = agentPackLocationOverrides[String(packAgent.id)];
        const initialLocation = overrideLocation || (knownLocations.has(rawInitialLocation)
            ? rawInitialLocation
            : mapLocations[0]?.id || '');
        profile.routine = {
            ...routine,
            initial_location: initialLocation,
        };
        profile.name = stringValue(profile.name || packAgent.name) || `Agent ${nextId}`;
        profile.agent_pack = {
            pack_id: pack.pack_id,
            agent_id: packAgent.id,
            scope: pack.scope,
            map_id: pack.map_id || undefined,
        };
        if (packAgent.sprite?.path) {
            const filename = basename(packAgent.sprite.path);
            const spriteName = packAgent.sprite.name || stem(filename);
            const source = {
                agent_pack: pack.pack_id,
                scope: pack.scope,
                map_id: pack.map_id || undefined,
            };
            profile.appearance = {
                ...asRecord(profile.appearance),
                character_asset: {
                    sprite_name: spriteName,
                    filename,
                    image_url: agentPackAssetUrl(pack, packAgent.sprite),
                    frame_width: Number(packAgent.sprite.frame_width || 32),
                    frame_height: Number(packAgent.sprite.frame_height || 32),
                    source,
                },
                character_sprite: spriteName,
                character_sprite_filename: filename,
                character_sprite_source: source,
            };
        }
        const runtime = asRecord(packAgent.runtime);
        const runtimeKwargs = { ...asRecord(runtime.kwargs) };
        delete runtimeKwargs.id;
        delete runtimeKwargs.name;
        delete runtimeKwargs.profile;
        const agent = normalizeJiuwenRuntimeAgent({
            agent_id: nextId,
            agent_type: stringValue(runtime.agent_type) || findDefaultAgentType(agentClasses),
            kwargs: {
                ...runtimeKwargs,
                id: nextId,
                name: String(profile.name),
                profile: normalizeStudioProfile(profile, mapId, initialLocation),
            },
        });
        return { agent, initialLocation };
    };

    const importSelectedAgentPack = async () => {
        if (!config || !selectedAgentPack) {
            message.warning(t('agentBuilder.import.agentPackRequired'));
            return;
        }
        const startId = agentPackImportMode === 'replace'
            ? 1
            : (agents.length ? Math.max(...agents.map((agent) => agent.agent_id)) + 1 : 1);
        const imported = selectedAgentPack.agents.map((packAgent, index) => (
            buildAgentFromPack(selectedAgentPack, packAgent, startId + index)
        ));
        const importedAgents = imported.map((item) => item.agent);
        const nextAgents = agentPackImportMode === 'replace'
            ? importedAgents
            : [...agents, ...importedAgents];
        const importedLocations = Object.fromEntries(
            imported
                .filter((item) => item.initialLocation)
                .map((item) => [String(item.agent.agent_id), item.initialLocation])
        );
        const baseConfig = syncEnvForAgents(config, nextAgents);
        const nextConfig = {
            ...baseConfig,
            env_modules: baseConfig.env_modules.map((module, index) => index === 0 ? {
                ...module,
                kwargs: {
                    ...module.kwargs,
                    initial_locations: {
                        ...asRecord(module.kwargs.initial_locations),
                        ...importedLocations,
                    },
                },
            } : module),
        };
        if (autoSaveOnAgentSave) {
            if (!(await persistConfig(nextConfig))) return;
            await onSaved?.();
        } else {
            setConfig(nextConfig);
        }
        setAgentPackModalOpen(false);
        message.success(t('agentBuilder.messages.imported', { count: importedAgents.length }));
    };

    const handleAgentPackZipInstalled = async () => {
        setAgentPackZipImportOpen(false);
        setAgentPackModalOpen(true);
    };

    const exportAgents = async () => {
        if (!config) return;
        const initialLocations = asStringRecord(getEnvModule(config)?.kwargs?.initial_locations);
        try {
            const response = await fetchCustom('/api/v1/god/agent-packs/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pack_id: `${hypothesisId}-${experimentId}-agents`,
                    display_name: `${hypothesisId} ${experimentId} Agents`,
                    agents,
                    initial_locations: initialLocations,
                }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `${hypothesisId}-${experimentId}-agent-pack.zip`;
            link.click();
            URL.revokeObjectURL(url);
            message.success(t('agentBuilder.messages.exported'));
        } catch (error) {
            message.error(error instanceof Error ? error.message : String(error));
        }
    };

    const upsertAgent = async (agent: AgentRecord, meta?: AgentEditorSaveMeta) => {
        if (!config) return;
        const normalizedAgent = normalizeJiuwenRuntimeAgent(agent);
        const nextAgents = editingAgentId === null
            ? [...agents, normalizedAgent]
            : agents.map((item) => item.agent_id === editingAgentId ? normalizedAgent : item);
        if (getDuplicateIds(nextAgents).size > 0 || nextAgents.some((item) => !item.kwargs || item.kwargs.id !== item.agent_id)) {
            message.error(t('agentBuilder.messages.invalidAgents'));
            return;
        }
        const nextConfig = syncEnvForAgents(config, nextAgents, normalizedAgent, meta);
        if (autoSaveOnAgentSave) {
            if (!(await persistConfig(nextConfig))) {
                return;
            }
            setAgentModalOpen(false);
            await onSaved?.();
            return;
        }
        setConfig(nextConfig);
        setAgentModalOpen(false);
    };

    const deleteAgent = (agentId: number) => {
        if (!config) return;
        const nextAgents = agents.filter((agent) => agent.agent_id !== agentId);
        setConfig(syncEnvForAgents(config, nextAgents));
    };

    const previewImport = async () => {
        if (!importContent.trim()) {
            message.warning(t('agentBuilder.messages.importContentRequired'));
            return;
        }
        try {
            const response = await fetchCustom(`${endpointBase}/agents/import-preview?${query}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: importContent, format: importFormat }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json();
            setImportPreview(payload);
            message.success(t('agentBuilder.messages.previewReady', { valid: payload.valid_count, invalid: payload.invalid_count }));
        } catch (error) {
            message.error(t('agentBuilder.messages.previewFailed', { error: error instanceof Error ? error.message : String(error) }));
        }
    };

    const applyImport = async () => {
        if (!importPreview) return;
        const validAgents = importPreview.rows
            .filter((row) => row.valid && row.agent)
            .map((row) => row.agent as AgentRecord);
        if (!validAgents.length) {
            message.warning(t('agentBuilder.messages.noValidRows'));
            return;
        }
        try {
            const response = await fetchCustom(`${endpointBase}/agents/apply?${query}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agents: validAgents,
                    mode: importMode,
                    sync_agent_id_name_pairs: true,
                }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            const payload = await response.json();
            setConfig(normalizeAgentsForStudio(payload.config, mapId));
            setConfigPath(payload.path);
            setImportModalOpen(false);
            setImportPreview(null);
            setImportContent('');
            if (payload.warnings?.length) {
                message.warning(payload.warnings.join(' '));
            } else {
                message.success(t('agentBuilder.messages.imported', { count: validAgents.length }));
            }
        } catch (error) {
            message.error(t('agentBuilder.messages.applyImportFailed', { error: error instanceof Error ? error.message : String(error) }));
        }
    };

    const agentColumns: ColumnsType<AgentRecord> = [
        {
            title: 'ID',
            dataIndex: 'agent_id',
            width: 90,
            sorter: (a, b) => a.agent_id - b.agent_id,
        },
        {
            title: t('agentBuilder.columns.name'),
            render: (_, record) => getAgentName(record),
        },
        {
            title: t('agentBuilder.columns.agentType'),
            dataIndex: 'agent_type',
            render: (value: string) => <Tag color="blue">{value}</Tag>,
        },
        {
            title: t('agentBuilder.columns.profile'),
            render: (_, record) => (
                <Tooltip title={<pre style={{ margin: 0 }}>{jsonPreviewText(record.kwargs?.profile)}</pre>}>
                    <Text code>{jsonPreviewText(record.kwargs?.profile, 120)}</Text>
                </Tooltip>
            ),
        },
        {
            title: t('agentBuilder.columns.kwargs'),
            render: (_, record) => {
                const rest = omitKeys(record.kwargs || {}, ['profile']);
                return (
                    <Tooltip title={<pre style={{ margin: 0 }}>{jsonPreviewText(rest)}</pre>}>
                        <Text code>{jsonPreviewText(rest, 120)}</Text>
                    </Tooltip>
                );
            },
        },
        {
            title: t('agentBuilder.columns.status'),
            width: 130,
            render: (_, record) => {
                if (duplicateIds.has(record.agent_id)) {
                    return <Tag color="red">{t('agentBuilder.status.duplicateId')}</Tag>;
                }
                if (record.kwargs?.id !== record.agent_id) {
                    return <Tag color="orange">{t('agentBuilder.status.idMismatch')}</Tag>;
                }
                return <Tag color="green">{t('agentBuilder.status.valid')}</Tag>;
            },
        },
        {
            title: t('agentBuilder.columns.actions'),
            width: 110,
            render: (_, record) => (
                <Space size="small">
                    <Tooltip title={t('agentBuilder.actions.edit')}>
                        <Button size="small" icon={<EditOutlined />} onClick={() => openEditAgent(record)} />
                    </Tooltip>
                    <Popconfirm title={t('agentBuilder.messages.deleteConfirm')} onConfirm={() => deleteAgent(record.agent_id)}>
                        <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                </Space>
            ),
        },
    ];

    const previewColumns: ColumnsType<ImportPreviewRow> = [
        { title: t('agentBuilder.columns.row'), dataIndex: 'row_index', width: 80 },
        {
            title: t('agentBuilder.columns.status'),
            width: 110,
            render: (_, row) => row.valid
                ? <Tag color="green">{t('agentBuilder.status.valid')}</Tag>
                : <Tag color="red">{t('agentBuilder.status.invalid')}</Tag>,
        },
        {
            title: t('agentBuilder.columns.agent'),
            render: (_, row) => row.agent ? `${row.agent.agent_id} · ${getAgentName(row.agent)} · ${row.agent.agent_type}` : '-',
        },
        {
            title: t('agentBuilder.columns.errors'),
            render: (_, row) => row.errors.length ? row.errors.join('; ') : '-',
        },
    ];

    const content = (
        <>
            <Card
                className="agent-studio-shell-card"
                title={t('agentBuilder.title')}
                extra={
                    <Space wrap>
                        <LanguageToggle />
                        <Button icon={<FolderOpenOutlined />} onClick={loadConfig} loading={loading}>
                            {t('agentBuilder.actions.load')}
                        </Button>
                        <Button
                            type="primary"
                            icon={<SaveOutlined />}
                            onClick={saveConfig}
                            disabled={!config || hasInvalidAgents}
                            loading={saving}
                        >
                            {t('agentBuilder.actions.save')}
                        </Button>
                    </Space>
                }
            >
                    <Row gutter={[12, 12]}>
                        <Col xs={24} lg={12}>
                            <Input
                                addonBefore={t('agentBuilder.fields.workspace')}
                                value={workspacePath}
                                onChange={(event) => setWorkspacePath(event.target.value)}
                                placeholder="/path/to/workspace"
                            />
                        </Col>
                        <Col xs={12} lg={6}>
                            <Input
                                addonBefore={t('agentBuilder.fields.hypothesis')}
                                value={hypothesisId}
                                onChange={(event) => setHypothesisId(event.target.value)}
                            />
                        </Col>
                        <Col xs={12} lg={6}>
                            <Input
                                addonBefore={t('agentBuilder.fields.experiment')}
                                value={experimentId}
                                onChange={(event) => setExperimentId(event.target.value)}
                            />
                        </Col>
                    </Row>

                    {configPath && (
                        <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
                            {t('agentBuilder.messages.loadedFrom')} <Text code>{configPath}</Text>
                        </Paragraph>
                    )}

                    <Divider />

                    <Space wrap className="agent-studio-action-bar">
                        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateAgent} disabled={!config}>
                            {t('agentBuilder.actions.addAgent')}
                        </Button>
                        <Button icon={<ImportOutlined />} onClick={() => setImportModalOpen(true)} disabled={!config}>
                            {t('agentBuilder.actions.batchImport')}
                        </Button>
                        <Button icon={<ImportOutlined />} onClick={() => setAgentPackModalOpen(true)} disabled={!config}>
                            {t('agentBuilder.actions.addFromAgentPack')}
                        </Button>
                        <Button icon={<ImportOutlined />} onClick={() => setAgentPackZipImportOpen(true)} disabled={!config}>
                            {t('agentBuilder.actions.importAgentPackZip')}
                        </Button>
                        <Button icon={<ExportOutlined />} onClick={exportAgents} disabled={!config || !agents.length}>
                            {t('agentBuilder.actions.exportAll')}
                        </Button>
                        <Tag>{t('agentBuilder.messages.agentCount', { count: agents.length })}</Tag>
                    </Space>

                    {hasInvalidAgents && (
                        <Alert
                            type="warning"
                            showIcon
                            message={t('agentBuilder.messages.invalidAgents')}
                            style={{ marginBottom: 12 }}
                        />
                    )}

                    <Table
                        rowKey={(record) => `${record.agent_id}-${record.agent_type}-${getAgentName(record)}`}
                        columns={agentColumns}
                        dataSource={agents}
                        loading={loading}
                        pagination={{ pageSize: 10, showSizeChanger: true }}
                        scroll={{ x: 900 }}
                    />
            </Card>

            <AgentEditorModal
                open={agentModalOpen}
                editingAgentId={editingAgentId}
                form={form}
                initialValues={agentInitialValues}
                agentClasses={agentClasses}
                experimentContext={experimentContext || agents[0]?.kwargs?.experiment_context || agents[0]?.kwargs?.profile?.experiment_context || {}}
                mapId={mapId}
                mapLocations={mapLocations}
                existingAgents={agents}
                initialLocation={editingAgentId === null ? undefined : getEnvModule(config)?.kwargs?.initial_locations?.[String(editingAgentId)]}
                defaultInitialLocation={mapLocations[0]?.id}
                onSave={upsertAgent}
                onCancel={() => setAgentModalOpen(false)}
            />

            <Modal
                title={t('agentBuilder.import.title')}
                open={importModalOpen}
                onCancel={() => setImportModalOpen(false)}
                footer={[
                    <Button key="cancel" onClick={() => setImportModalOpen(false)}>{t('agentBuilder.actions.cancel')}</Button>,
                    <Button key="preview" onClick={previewImport}>{t('agentBuilder.actions.preview')}</Button>,
                    <Button key="apply" type="primary" disabled={!importPreview?.valid_count} onClick={applyImport}>
                        {t('agentBuilder.actions.applyValidRows')}
                    </Button>,
                ]}
                width="82vw"
                destroyOnHidden
            >
                <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    <Alert
                        type="info"
                        showIcon
                        message={t('agentBuilder.import.help')}
                    />
                    <Row gutter={12}>
                        <Col span={12}>
                            <Radio.Group value={importFormat} onChange={(event) => setImportFormat(event.target.value)}>
                                <Radio.Button value="auto">{t('agentBuilder.import.auto')}</Radio.Button>
                                <Radio.Button value="csv">CSV</Radio.Button>
                                <Radio.Button value="json">JSON</Radio.Button>
                            </Radio.Group>
                        </Col>
                        <Col span={12} style={{ textAlign: 'right' }}>
                            <Radio.Group value={importMode} onChange={(event) => setImportMode(event.target.value)}>
                                <Radio.Button value="append">{t('agentBuilder.import.append')}</Radio.Button>
                                <Radio.Button value="replace">{t('agentBuilder.import.replace')}</Radio.Button>
                            </Radio.Group>
                        </Col>
                    </Row>
                    <Upload.Dragger
                        beforeUpload={(file) => {
                            file.text().then(setImportContent);
                            return false;
                        }}
                        maxCount={1}
                        accept=".csv,.json"
                    >
                        <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                        <p className="ant-upload-text">{t('agentBuilder.import.dropText')}</p>
                    </Upload.Dragger>
                    <Input.TextArea
                        rows={10}
                        value={importContent}
                        onChange={(event) => setImportContent(event.target.value)}
                        placeholder={t('agentBuilder.import.contentPlaceholder')}
                        spellCheck={false}
                    />
                    {importPreview && (
                        <Table
                            rowKey="row_index"
                            size="small"
                            columns={previewColumns}
                            dataSource={importPreview.rows}
                            pagination={{ pageSize: 8 }}
                            scroll={{ x: 720 }}
                            title={() => (
                                <Space>
                                    <Tag color="green">{t('agentBuilder.import.validCount', { count: importPreview.valid_count })}</Tag>
                                    <Tag color={importPreview.invalid_count ? 'red' : 'default'}>
                                        {t('agentBuilder.import.invalidCount', { count: importPreview.invalid_count })}
                                    </Tag>
                                </Space>
                            )}
                        />
                    )}
                </Space>
            </Modal>

            <Modal
                title={t('agentBuilder.import.agentPackTitle')}
                open={agentPackModalOpen}
                onCancel={() => setAgentPackModalOpen(false)}
                footer={[
                    <Button key="cancel" onClick={() => setAgentPackModalOpen(false)}>{t('agentBuilder.actions.cancel')}</Button>,
                    <Button key="import" type="primary" disabled={!selectedAgentPack} onClick={importSelectedAgentPack}>
                        {t('agentBuilder.actions.addFromAgentPack')}
                    </Button>,
                ]}
                destroyOnHidden
            >
                <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    <Alert type="info" showIcon message={t('agentBuilder.import.agentPackHelp')} />
                    <Select
                        loading={agentPacksLoading}
                        value={selectedAgentPackId}
                        onChange={setSelectedAgentPackId}
                        options={agentPackOptions}
                        placeholder={agentPackOptions.length ? t('agentBuilder.import.agentPackPlaceholder') : t('agentBuilder.import.agentPackEmpty')}
                        showSearch
                        optionFilterProp="label"
                    />
                    <Radio.Group value={agentPackImportMode} onChange={(event) => setAgentPackImportMode(event.target.value)}>
                        <Radio.Button value="append">{t('agentBuilder.import.append')}</Radio.Button>
                        <Radio.Button value="replace">{t('agentBuilder.import.replace')}</Radio.Button>
                    </Radio.Group>
                    {selectedAgentPack && (
                        <Table<AgentPackAgent>
                            size="small"
                            pagination={false}
                            rowKey={(record) => String(record.id)}
                            dataSource={selectedAgentPack.agents}
                            scroll={{ x: 520 }}
                            columns={[
                                {
                                    title: t('agentBuilder.import.agent'),
                                    render: (_, record) => record.name || record.id,
                                },
                                {
                                    title: t('agentBuilder.import.initialLocation'),
                                    render: (_, record) => (
                                        <Select
                                            style={{ width: '100%' }}
                                            value={agentPackLocationOverrides[String(record.id)] || mapLocations[0]?.id}
                                            options={mapLocations.map((location) => ({
                                                value: location.id,
                                                label: localizeMapLocationName(mapId, location, i18n.language),
                                            }))}
                                            disabled={!mapLocations.length}
                                            placeholder={t('agentBuilder.studio.locationUnavailable')}
                                            onChange={(value) => setAgentPackLocationOverrides((current) => ({
                                                ...current,
                                                [String(record.id)]: value,
                                            }))}
                                        />
                                    ),
                                },
                            ]}
                        />
                    )}
                </Space>
            </Modal>
            <PackageImportModal
                open={agentPackZipImportOpen}
                expectedType="agent"
                onCancel={() => setAgentPackZipImportOpen(false)}
                onInstalled={handleAgentPackZipInstalled}
            />
        </>
    );

    if (embedded) {
        return content;
    }

    if (!embedded && !hasExplicitContext) {
        return (
            <div className="agent-builder-page">
                <Card className="agent-studio-empty-state" title={t('agentBuilder.empty.title')}>
                    <Alert
                        type="info"
                        showIcon
                        message={t('agentBuilder.empty.message')}
                        description={t('agentBuilder.empty.description')}
                        style={{ marginBottom: 16 }}
                    />
                    <Space wrap>
                        <Button type="primary" onClick={() => navigate('/setup')}>
                            {t('agentBuilder.empty.backToSetup')}
                        </Button>
                    </Space>
                </Card>
            </div>
        );
    }

    return (
        <div className="agent-builder-page">
            {content}
        </div>
    );
};

const AgentBuilder: React.FC = () => <AgentBuilderPanel />;

export default AgentBuilder;
