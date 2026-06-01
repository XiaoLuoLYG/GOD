import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Button,
    Card,
    Form,
    Input,
    InputNumber,
    Segmented,
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
    AimOutlined,
    BlockOutlined,
    CheckCircleOutlined,
    CloudUploadOutlined,
    CompassOutlined,
    ExportOutlined,
    EditOutlined,
    KeyOutlined,
    PlayCircleOutlined,
    ReloadOutlined,
    RocketOutlined,
    SaveOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchCustom } from '../../components/fetch';
import LanguageToggle from '../../components/LanguageToggle';
import './style.css';

const { Text, Title } = Typography;
const MAP_WIDTH = 140;
const MAP_HEIGHT = 100;

type MapValidationStatus = {
    ok: boolean;
    errors: string[];
    warnings: string[];
};

type MapStudioLocation = {
    id: string;
    name: string;
    aliases?: string[];
    localized?: Record<string, Record<string, unknown>>;
    anchor_tile: { x: number; y: number };
    scene_type?: string;
    bounds?: { x: number; y: number; w: number; h: number } | null;
    interaction_ids?: string[];
    visual_asset?: string | null;
};

type MapStudioInteraction = {
    id: string;
    name: string;
    description?: string;
    localized?: Record<string, Record<string, unknown>>;
    allowed_location_ids?: string[];
    effects?: Record<string, unknown>;
};

type MapDraft = {
    draft_id: string;
    map_id: string;
    prompt: string;
    status: string;
    package_path: string;
    preview_url: string;
    map_image_url: string;
    style_reference_used?: string;
    collision_data?: number[];
    locations: MapStudioLocation[];
    interactions: MapStudioInteraction[];
    validation: MapValidationStatus;
    warnings: string[];
};

type PublishResponse = {
    map_id: string;
    setup_url: string;
    package_path: string;
    validation: MapValidationStatus;
};

type RedactedConfigValue = {
    configured: boolean;
    value: string;
};

type SetupStatus = {
    image_model_config?: Record<string, RedactedConfigValue>;
};

type ImageConfigForm = {
    image_api_key: string;
    image_api_base: string;
    image_model: string;
    image_provider: string;
};

type BrushMode = 'anchor' | 'walkable' | 'blocked';

const fetchJson = async <T,>(url: string, options?: RequestInit): Promise<T> => {
    const response = await fetchCustom(url, options);
    if (!response.ok) {
        const text = await response.text();
        try {
            const payload = JSON.parse(text);
            const detail = payload?.detail;
            if (typeof detail === 'string') {
                throw new Error(detail);
            }
            if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
                throw new Error(detail.message);
            }
            throw new Error(JSON.stringify(detail ?? payload));
        } catch (error) {
            if (error instanceof SyntaxError) {
                throw new Error(text);
            }
            throw error;
        }
    }
    return response.json();
};

const toErrorText = (error: unknown) => (error instanceof Error ? error.message : String(error));

const localizeName = (location: MapStudioLocation, language: string) => {
    const localized = language.startsWith('en') ? location.localized?.en : location.localized?.zh;
    const value = localized?.name;
    return typeof value === 'string' && value.trim() ? value : location.name || location.id;
};

const clampTile = (value: number, max: number) => Math.max(0, Math.min(max - 1, Math.round(value)));

const DEFAULT_IMAGE_CONFIG: ImageConfigForm = {
    image_api_key: '',
    image_api_base: 'https://api.openai.com/v1',
    image_model: 'gpt-image-1.5',
    image_provider: 'openai',
};

export default function MapStudioPage() {
    const navigate = useNavigate();
    const { t, i18n } = useTranslation();
    const copy = (key: string, values?: Record<string, unknown>) => (
        t(`mapStudio.${key}`, values) as string
    );
    const [messageApi, messageContextHolder] = message.useMessage();
    const [prompt, setPrompt] = useState(copy('generate.defaultPrompt'));
    const [referenceFile, setReferenceFile] = useState<File | null>(null);
    const [draft, setDraft] = useState<MapDraft | null>(null);
    const [selectedLocationId, setSelectedLocationId] = useState<string>('');
    const [brushMode, setBrushMode] = useState<BrushMode>('anchor');
    const [brushSize, setBrushSize] = useState(1);
    const [showCollisionOverlay, setShowCollisionOverlay] = useState(true);
    const [collisionStrokes, setCollisionStrokes] = useState<Array<Array<{ x: number; y: number; blocked: boolean }>>>([]);
    const [painting, setPainting] = useState(false);
    const [collisionEdits, setCollisionEdits] = useState<Array<{ x: number; y: number; blocked: boolean }>>([]);
    const [generating, setGenerating] = useState(false);
    const [saving, setSaving] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [imageConfigSaving, setImageConfigSaving] = useState(false);
    const [imageConfigLoading, setImageConfigLoading] = useState(true);
    const [imageConfig, setImageConfig] = useState<ImageConfigForm>(DEFAULT_IMAGE_CONFIG);
    const [imageConfigStatus, setImageConfigStatus] = useState({ configured: false, value: '' });
    const [imageConfigExpanded, setImageConfigExpanded] = useState(false);
    const [generationError, setGenerationError] = useState('');
    const [published, setPublished] = useState<PublishResponse | null>(null);
    const [publishMapId, setPublishMapId] = useState('');
    const [draggingId, setDraggingId] = useState<string | null>(null);
    const imageRef = useRef<HTMLImageElement | null>(null);
    const language = i18n.language || 'zh';

    const selectedLocation = useMemo(
        () => draft?.locations.find((item) => item.id === selectedLocationId) || draft?.locations[0],
        [draft?.locations, selectedLocationId],
    );

    const applyImageStatus = (status: SetupStatus, syncVisibleFields: boolean) => {
        const config = status.image_model_config || {};
        const apiKey = config.IMAGE_GEN_API_KEY;
        if (syncVisibleFields && !apiKey?.configured) {
            setImageConfigExpanded(true);
        }
        setImageConfigStatus({
            configured: Boolean(apiKey?.configured),
            value: apiKey?.value || '',
        });
        if (!syncVisibleFields) return;
        setImageConfig((current) => ({
            ...current,
            image_api_key: '',
            image_api_base: config.IMAGE_GEN_API_BASE?.value || current.image_api_base || DEFAULT_IMAGE_CONFIG.image_api_base,
            image_model: config.IMAGE_GEN_MODEL_NAME?.value || current.image_model || DEFAULT_IMAGE_CONFIG.image_model,
            image_provider: config.IMAGE_GEN_PROVIDER?.value || current.image_provider || DEFAULT_IMAGE_CONFIG.image_provider,
        }));
    };

    const loadImageStatus = async (syncVisibleFields = true) => {
        setImageConfigLoading(true);
        try {
            const status = await fetchJson<SetupStatus>('/api/v1/god/setup/status');
            applyImageStatus(status, syncVisibleFields);
        } catch (error) {
            messageApi.warning(toErrorText(error));
        } finally {
            setImageConfigLoading(false);
        }
    };

    useEffect(() => {
        void loadImageStatus(true);
        // The loader intentionally runs once when the workbench opens.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const imageConfigPayload = () => {
        const payload: Record<string, string> = {
            image_api_base: imageConfig.image_api_base.trim(),
            image_model: imageConfig.image_model.trim(),
            image_provider: imageConfig.image_provider.trim() || DEFAULT_IMAGE_CONFIG.image_provider,
        };
        if (imageConfig.image_api_key.trim()) {
            payload.image_api_key = imageConfig.image_api_key.trim();
        }
        return payload;
    };

    const appendImageConfigToForm = (form: FormData) => {
        Object.entries(imageConfigPayload()).forEach(([key, value]) => {
            if (value) form.append(key, value);
        });
    };

    const saveImageConfig = async () => {
        if (!imageConfig.image_api_key.trim() && !imageConfigStatus.configured) {
            messageApi.warning(copy('imageConfig.keyRequiredToSave'));
            return;
        }
        setImageConfigSaving(true);
        try {
            const status = await fetchJson<SetupStatus>('/api/v1/god/map-studio/image-config', {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ image_config: imageConfigPayload() }),
            });
            applyImageStatus(status, true);
            messageApi.success(copy('messages.imageConfigSaved'));
        } catch (error) {
            messageApi.error(toErrorText(error));
        } finally {
            setImageConfigSaving(false);
        }
    };

    const updateDraftLocation = (locationId: string, patch: Partial<MapStudioLocation>) => {
        setDraft((current) => {
            if (!current) return current;
            return {
                ...current,
                locations: current.locations.map((item) => (
                    item.id === locationId ? { ...item, ...patch } : item
                )),
            };
        });
    };

    const tileFromPointer = (event: React.PointerEvent<HTMLElement>) => {
        const image = imageRef.current;
        if (!image) return null;
        const rect = image.getBoundingClientRect();
        const x = clampTile(((event.clientX - rect.left) / Math.max(rect.width, 1)) * MAP_WIDTH, MAP_WIDTH);
        const y = clampTile(((event.clientY - rect.top) / Math.max(rect.height, 1)) * MAP_HEIGHT, MAP_HEIGHT);
        return { x, y };
    };

    const collisionKey = (x: number, y: number) => `${x}:${y}`;

    const collisionBaseStats = useMemo(() => {
        const values = draft?.collision_data || [];
        const savedBlocked = values.filter((value) => Boolean(value)).length;
        const total = values.length;
        return {
            savedBlocked,
            savedWalkable: total - savedBlocked,
            showSavedWalkableOverlay: savedBlocked > total / 2,
        };
    }, [draft?.collision_data]);

    const committedCollision = useMemo(() => {
        const cells = new Map<string, boolean>();
        draft?.collision_data?.forEach((value, index) => {
            const shouldShow = collisionBaseStats.showSavedWalkableOverlay ? !value : Boolean(value);
            if (!shouldShow) return;
            const x = index % MAP_WIDTH;
            const y = Math.floor(index / MAP_WIDTH);
            cells.set(collisionKey(x, y), !collisionBaseStats.showSavedWalkableOverlay);
        });
        return cells;
    }, [collisionBaseStats.showSavedWalkableOverlay, draft?.collision_data]);

    const pendingCollision = useMemo(() => {
        const cells = new Map<string, boolean>();
        collisionEdits.forEach((edit) => cells.set(collisionKey(edit.x, edit.y), edit.blocked));
        return cells;
    }, [collisionEdits]);

    const editsFromStrokes = (strokes: Array<Array<{ x: number; y: number; blocked: boolean }>>) => {
        const cells = new Map<string, { x: number; y: number; blocked: boolean }>();
        strokes.flat().forEach((edit) => cells.set(collisionKey(edit.x, edit.y), edit));
        return Array.from(cells.values());
    };

    const paintTile = (tile: { x: number; y: number }, startStroke = false) => {
        if (brushMode === 'anchor') return;
        const radius = Math.floor(brushSize / 2);
        const stroke = Array.from({ length: brushSize }, (_, yOffset) => (
            Array.from({ length: brushSize }, (_, xOffset) => {
                const x = clampTile(tile.x + xOffset - radius, MAP_WIDTH);
                const y = clampTile(tile.y + yOffset - radius, MAP_HEIGHT);
                return { x, y, blocked: brushMode === 'blocked' };
            })
        )).flat();
        const uniqueStroke = Array.from(
            new Map(stroke.map((edit) => [collisionKey(edit.x, edit.y), edit])).values(),
        );

        setCollisionStrokes((items) => {
            const next = startStroke || items.length === 0
                ? [...items, uniqueStroke]
                : items.map((item, index) => (
                    index === items.length - 1
                        ? Array.from(new Map([...item, ...uniqueStroke].map((edit) => [collisionKey(edit.x, edit.y), edit])).values())
                        : item
                ));
            setCollisionEdits(editsFromStrokes(next));
            return next;
        });
    };

    const overlayCells = useMemo(() => {
        if (!showCollisionOverlay) return [];
        const cells = new Map<string, { x: number; y: number; blocked: boolean; pending: boolean }>();
        committedCollision.forEach((blocked, key) => {
            const [x, y] = key.split(':').map(Number);
            cells.set(key, { x, y, blocked, pending: false });
        });
        pendingCollision.forEach((blocked, key) => {
            const [x, y] = key.split(':').map(Number);
            cells.set(key, { x, y, blocked, pending: true });
        });
        return Array.from(cells.values());
    }, [committedCollision, pendingCollision, showCollisionOverlay]);

    const collisionStats = useMemo(() => {
        const pendingBlocked = collisionEdits.filter((edit) => edit.blocked).length;
        return {
            savedBlocked: collisionBaseStats.savedBlocked,
            savedWalkable: collisionBaseStats.savedWalkable,
            pendingBlocked,
            pendingWalkable: collisionEdits.length - pendingBlocked,
        };
    }, [collisionBaseStats.savedBlocked, collisionBaseStats.savedWalkable, collisionEdits]);

    const undoCollisionStroke = () => {
        setCollisionStrokes((items) => {
            const next = items.slice(0, -1);
            setCollisionEdits(editsFromStrokes(next));
            return next;
        });
    };

    const submitDraft = async () => {
        if (!prompt.trim()) {
            messageApi.warning(copy('messages.enterPrompt'));
            return;
        }
        setGenerating(true);
        setGenerationError('');
        setPublished(null);
        try {
            let next: MapDraft;
            if (referenceFile) {
                const form = new FormData();
                form.append('prompt', prompt);
                form.append('file', referenceFile);
                appendImageConfigToForm(form);
                next = await fetchJson<MapDraft>('/api/v1/god/map-studio/drafts/upload', {
                    method: 'POST',
                    body: form,
                });
            } else {
                next = await fetchJson<MapDraft>('/api/v1/god/map-studio/drafts', {
                    method: 'POST',
                    headers: { 'content-type': 'application/json' },
                    body: JSON.stringify({ prompt, image_config: imageConfigPayload() }),
                });
            }
            setDraft(next);
            setSelectedLocationId(next.locations[0]?.id || '');
            setPublishMapId(next.map_id);
            setCollisionEdits([]);
            setCollisionStrokes([]);
            setImageConfig((current) => ({ ...current, image_api_key: '' }));
            void loadImageStatus(true);
            messageApi.success(copy('messages.generated'));
        } catch (error) {
            setGenerationError(toErrorText(error));
            messageApi.error(copy('messages.generateFailed'));
        } finally {
            setGenerating(false);
        }
    };

    const saveCalibration = async (locationsToPatch?: MapStudioLocation[]) => {
        if (!draft) return;
        setSaving(true);
        try {
            const payload = {
                locations: locationsToPatch || draft.locations,
                collision_edits: collisionEdits,
            };
            const next = await fetchJson<MapDraft>(`/api/v1/god/map-studio/drafts/${encodeURIComponent(draft.draft_id)}`, {
                method: 'PATCH',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify(payload),
            });
            setDraft(next);
            setCollisionEdits([]);
            setCollisionStrokes([]);
            messageApi.success(copy('messages.saved'));
        } catch (error) {
            messageApi.error(toErrorText(error));
        } finally {
            setSaving(false);
        }
    };

    const validateDraft = async () => {
        if (!draft) return;
        setSaving(true);
        try {
            const next = await fetchJson<MapDraft>(`/api/v1/god/map-studio/drafts/${encodeURIComponent(draft.draft_id)}/validate`, {
                method: 'POST',
            });
            setDraft(next);
            messageApi.success(next.validation.ok ? copy('messages.validationPassed') : copy('messages.validationNeedsFixes'));
        } catch (error) {
            messageApi.error(toErrorText(error));
        } finally {
            setSaving(false);
        }
    };

    const publishDraft = async () => {
        if (!draft) return;
        setPublishing(true);
        try {
            const result = await fetchJson<PublishResponse>(`/api/v1/god/map-studio/drafts/${encodeURIComponent(draft.draft_id)}/publish`, {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ map_id: publishMapId || draft.map_id }),
            });
            setPublished(result);
            messageApi.success(copy('messages.published'));
        } catch (error) {
            messageApi.error(toErrorText(error));
        } finally {
            setPublishing(false);
        }
    };

    const exportMapPack = async () => {
        const mapId = published?.map_id || publishMapId.trim() || draft?.map_id;
        if (!mapId) return;
        try {
            const response = await fetchCustom('/api/v1/god/map-packs/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    map_id: mapId,
                    draft_id: published ? undefined : draft?.draft_id,
                }),
            });
            if (!response.ok) {
                messageApi.error(await response.text());
                return;
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `${mapId}-map-pack.zip`;
            link.click();
            URL.revokeObjectURL(url);
            messageApi.success(copy('messages.exported'));
        } catch (error) {
            messageApi.error(toErrorText(error));
        }
    };

    const regenerateImage = async () => {
        if (!draft) return;
        setGenerating(true);
        setGenerationError('');
        try {
            const next = await fetchJson<MapDraft>(`/api/v1/god/map-studio/drafts/${encodeURIComponent(draft.draft_id)}/regenerate-image`, {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ image_config: imageConfigPayload() }),
            });
            setDraft(next);
            setCollisionEdits([]);
            setCollisionStrokes([]);
            setImageConfig((current) => ({ ...current, image_api_key: '' }));
            void loadImageStatus(true);
            messageApi.success(copy('messages.regenerated'));
        } catch (error) {
            setGenerationError(toErrorText(error));
            messageApi.error(copy('messages.generateFailed'));
        } finally {
            setGenerating(false);
        }
    };

    const commitPointerTile = (event: React.PointerEvent<HTMLElement>) => {
        if (!draft) return;
        const tile = tileFromPointer(event);
        if (!tile) return;
        if (brushMode !== 'anchor') {
            paintTile(tile);
            return;
        }
        const targetId = draggingId || selectedLocation?.id;
        if (!targetId) return;
        const nextLocation = draft.locations.find((item) => item.id === targetId);
        if (!nextLocation) return;
        const updated = { ...nextLocation, anchor_tile: tile };
        updateDraftLocation(targetId, { anchor_tile: tile });
        void saveCalibration([updated]);
    };

    const columns: ColumnsType<MapStudioLocation> = [
        {
            title: copy('calibrate.location'),
            dataIndex: 'name',
            width: 128,
            ellipsis: true,
            render: (_, record) => (
                <Button
                    className="map-studio-location-button"
                    type={record.id === selectedLocation?.id ? 'primary' : 'text'}
                    size="small"
                    title={localizeName(record, language)}
                    onClick={() => setSelectedLocationId(record.id)}
                >
                    {localizeName(record, language)}
                </Button>
            ),
        },
        {
            title: copy('calibrate.anchor'),
            width: 142,
            render: (_, record) => (
                <Space.Compact size="small">
                    <InputNumber
                        className="map-studio-anchor-input"
                        min={0}
                        max={MAP_WIDTH - 1}
                        value={record.anchor_tile.x}
                        onChange={(value) => updateDraftLocation(record.id, {
                            anchor_tile: { ...record.anchor_tile, x: Number(value || 0) },
                        })}
                    />
                    <InputNumber
                        className="map-studio-anchor-input"
                        min={0}
                        max={MAP_HEIGHT - 1}
                        value={record.anchor_tile.y}
                        onChange={(value) => updateDraftLocation(record.id, {
                            anchor_tile: { ...record.anchor_tile, y: Number(value || 0) },
                        })}
                    />
                </Space.Compact>
            ),
        },
        {
            title: copy('calibrate.type'),
            dataIndex: 'scene_type',
            width: 82,
            render: (value) => <Tag>{value || copy('calibrate.publicType')}</Tag>,
        },
    ];

    const renderCollisionHelp = () => {
        const hasSavedBlockedOverlay = overlayCells.some((cell) => !cell.pending && cell.blocked);
        const hasSavedWalkableOverlay = overlayCells.some((cell) => !cell.pending && !cell.blocked);
        const descriptionKey = hasSavedWalkableOverlay && !hasSavedBlockedOverlay
            ? 'calibrate.collisionHelpRoadDescription'
            : hasSavedBlockedOverlay
                ? 'calibrate.collisionHelpDescription'
                : 'calibrate.collisionHelpEmptyDescription';
        return (
            <div data-testid="collision-help">
                <Alert
                    className="map-studio-collision-help"
                    type="info"
                    showIcon
                    message={copy('calibrate.collisionHelpTitle')}
                    description={(
                        <div className="map-studio-collision-help-body">
                            <Text>{copy(descriptionKey)}</Text>
                            <div className="map-studio-legend">
                                {hasSavedBlockedOverlay && (
                                    <span className="map-studio-legend-item">
                                        <span className="map-studio-legend-swatch saved-blocked" />
                                        {copy('calibrate.legendSavedBlocked')}
                                    </span>
                                )}
                                {hasSavedWalkableOverlay && (
                                    <span className="map-studio-legend-item">
                                        <span className="map-studio-legend-swatch saved-walkable" />
                                        {copy('calibrate.legendSavedWalkable')}
                                    </span>
                                )}
                                <span className="map-studio-legend-item">
                                    <span className="map-studio-legend-swatch pending-blocked" />
                                    {copy('calibrate.legendPendingBlocked')}
                                </span>
                                <span className="map-studio-legend-item">
                                    <span className="map-studio-legend-swatch pending-walkable" />
                                    {copy('calibrate.legendPendingWalkable')}
                                </span>
                            </div>
                        </div>
                    )}
                />
            </div>
        );
    };

    return (
        <div className="map-studio-page">
            {messageContextHolder}
            <div className="map-studio-shell">
                <div className="map-studio-header">
                    <div>
                        <Title level={2}>{copy('header.title')}</Title>
                        <Text type="secondary">{copy('header.subtitle')}</Text>
                    </div>
                    <Space wrap>
                        <LanguageToggle />
                        <Button icon={<PlayCircleOutlined />} onClick={() => navigate('/setup')}>
                            {copy('header.back')}
                        </Button>
                    </Space>
                </div>

                <div className="map-studio-layout">
                    <div className="map-studio-canvas-panel">
                        <Card
                            className="map-studio-card"
                            title={<Space><CompassOutlined />{copy('canvas.title')}</Space>}
                            extra={draft && <Tag color={draft.validation.ok ? 'green' : 'orange'}>{draft.status}</Tag>}
                        >
                            {draft ? (
                                <div
                                    className="map-studio-canvas"
                                    data-brush={brushMode}
                                    onPointerDown={(event) => {
                                        if (brushMode === 'anchor') return;
                                        setPainting(true);
                                        const tile = tileFromPointer(event);
                                        if (tile) paintTile(tile, true);
                                    }}
                                    onPointerMove={(event) => {
                                        if (brushMode === 'anchor' && draggingId) {
                                            const tile = tileFromPointer(event);
                                            if (tile) updateDraftLocation(draggingId, { anchor_tile: tile });
                                        } else if (painting) {
                                            const tile = tileFromPointer(event);
                                            if (tile) paintTile(tile);
                                        }
                                    }}
                                    onPointerUp={(event) => {
                                        if (brushMode === 'anchor') commitPointerTile(event);
                                        setPainting(false);
                                        setDraggingId(null);
                                    }}
                                    onPointerLeave={() => {
                                        setPainting(false);
                                        setDraggingId(null);
                                    }}
                                >
                                    <img
                                        ref={imageRef}
                                        src={`${draft.preview_url}?t=${encodeURIComponent(draft.draft_id)}`}
                                        alt="Generated map preview"
                                        draggable={false}
                                    />
                                    {overlayCells.map((cell) => (
                                        <span
                                            key={collisionKey(cell.x, cell.y)}
                                            className={[
                                                'map-studio-collision-cell',
                                                cell.blocked ? 'blocked' : 'walkable',
                                                cell.pending ? 'pending' : '',
                                            ].filter(Boolean).join(' ')}
                                            style={{
                                                left: `${(cell.x / MAP_WIDTH) * 100}%`,
                                                top: `${(cell.y / MAP_HEIGHT) * 100}%`,
                                                width: `${100 / MAP_WIDTH}%`,
                                                height: `${100 / MAP_HEIGHT}%`,
                                            }}
                                        />
                                    ))}
                                    {draft.locations.map((location) => (
                                        <button
                                            key={location.id}
                                            className={`map-studio-marker ${location.id === selectedLocation?.id ? 'active' : ''}`}
                                            style={{
                                                left: `${(location.anchor_tile.x / MAP_WIDTH) * 100}%`,
                                                top: `${(location.anchor_tile.y / MAP_HEIGHT) * 100}%`,
                                            }}
                                            onPointerDown={(event) => {
                                                if (brushMode !== 'anchor') return;
                                                event.stopPropagation();
                                                setSelectedLocationId(location.id);
                                                setDraggingId(location.id);
                                            }}
                                            aria-label={copy('canvas.moveAnchor', {
                                                location: localizeName(location, language),
                                            })}
                                            type="button"
                                        >
                                            <AimOutlined />
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <div className="map-studio-empty">
                                    <RocketOutlined />
                                    <Text type="secondary">{copy('canvas.empty')}</Text>
                                </div>
                            )}
                        </Card>
                    </div>

                    <div className="map-studio-side">
                        <Card className="map-studio-card" title={<Space><RocketOutlined />{copy('generate.title')}</Space>}>
                            <Form layout="vertical">
                                <Form.Item label={copy('generate.worldPrompt')}>
                                    <Input.TextArea
                                        rows={3}
                                        value={prompt}
                                        onChange={(event) => setPrompt(event.target.value)}
                                    />
                                </Form.Item>
                                <Upload
                                    beforeUpload={(file) => {
                                        setReferenceFile(file);
                                        return false;
                                    }}
                                    maxCount={1}
                                    onRemove={() => setReferenceFile(null)}
                                >
                                    <Button icon={<CloudUploadOutlined />}>{copy('generate.referenceImage')}</Button>
                                </Upload>
                                <details
                                    className="map-studio-image-config"
                                    data-testid="map-image-config"
                                    open={imageConfigExpanded || (!imageConfigLoading && !imageConfigStatus.configured)}
                                    onToggle={(event) => setImageConfigExpanded(event.currentTarget.open)}
                                >
                                    <summary className="map-studio-image-config-summary">
                                        <Space size={8}>
                                            <KeyOutlined />
                                            <Text strong>{copy('imageConfig.title')}</Text>
                                        </Space>
                                        {imageConfigLoading ? (
                                            <Tag>{copy('imageConfig.checking')}</Tag>
                                        ) : imageConfigStatus.configured ? (
                                            <Tag color="green">{copy('imageConfig.configured', { value: imageConfigStatus.value })}</Tag>
                                        ) : (
                                            <Tag color="orange">{copy('imageConfig.notConfigured')}</Tag>
                                        )}
                                    </summary>
                                    <div className="map-studio-image-config-body">
                                        <Alert
                                            className="map-studio-status-alert"
                                            type={imageConfigStatus.configured ? 'success' : 'warning'}
                                            showIcon
                                            message={
                                                imageConfigStatus.configured
                                                    ? copy('imageConfig.readyMessage')
                                                    : copy('imageConfig.missingMessage')
                                            }
                                            description={
                                                imageConfigStatus.configured
                                                    ? copy('imageConfig.readyDescription')
                                                    : copy('imageConfig.missingDescription')
                                            }
                                        />
                                        <div className="map-studio-field-grid image-config">
                                            <Form.Item label="IMAGE_GEN_PROVIDER">
                                                <Select
                                                    value={imageConfig.image_provider}
                                                    onChange={(value) => setImageConfig((current) => ({ ...current, image_provider: value }))}
                                                    options={[{ value: 'openai', label: 'openai' }]}
                                                />
                                            </Form.Item>
                                            <Form.Item label="IMAGE_GEN_API_BASE">
                                                <Input
                                                    value={imageConfig.image_api_base}
                                                    onChange={(event) => setImageConfig((current) => ({ ...current, image_api_base: event.target.value }))}
                                                />
                                            </Form.Item>
                                            <Form.Item label="IMAGE_GEN_MODEL_NAME">
                                                <Input
                                                    value={imageConfig.image_model}
                                                    onChange={(event) => setImageConfig((current) => ({ ...current, image_model: event.target.value }))}
                                                />
                                            </Form.Item>
                                            <Form.Item label="IMAGE_GEN_API_KEY">
                                                <Input.Password
                                                    value={imageConfig.image_api_key}
                                                    onChange={(event) => setImageConfig((current) => ({ ...current, image_api_key: event.target.value }))}
                                                    placeholder={imageConfigStatus.configured ? copy('imageConfig.keepExistingKey') : copy('imageConfig.apiKeyPlaceholder')}
                                                    autoComplete="off"
                                                />
                                            </Form.Item>
                                        </div>
                                        <Space wrap>
                                            <Button icon={<SaveOutlined />} loading={imageConfigSaving} onClick={saveImageConfig}>
                                                {copy('imageConfig.save')}
                                            </Button>
                                            <Text type="secondary">{copy('imageConfig.localEnvNote')}</Text>
                                        </Space>
                                    </div>
                                </details>
                            </Form>
                            <Space wrap className="map-studio-actions">
                                <Button type="primary" icon={<RocketOutlined />} loading={generating} onClick={submitDraft}>
                                    {copy('generate.generateMap')}
                                </Button>
                                <Button icon={<ReloadOutlined />} disabled={!draft} loading={generating} onClick={regenerateImage}>
                                    {copy('generate.regenerate')}
                                </Button>
                            </Space>
                            {generationError && (
                                <Alert
                                    className="map-studio-status-alert"
                                    type="warning"
                                    showIcon
                                    closable
                                    onClose={() => setGenerationError('')}
                                    message={copy('generate.failureTitle')}
                                    description={generationError}
                                />
                            )}
                            {draft?.style_reference_used === 'god_default' && (
                                <Alert
                                    className="map-studio-status-alert"
                                    type="info"
                                    showIcon
                                    message={copy('generate.defaultStyleUsed')}
                                />
                            )}
                        </Card>

                        {!draft && (
                            <Card className="map-studio-card" title={<Space><EditOutlined />{copy('calibrate.title')}</Space>}>
                                {renderCollisionHelp()}
                            </Card>
                        )}

                        {draft && (
                            <Card
                                className="map-studio-card map-studio-workflow-card"
                                title={(
                                    <Space>
                                        <EditOutlined />
                                        {copy('calibrate.title')} / {copy('validate.title')}
                                    </Space>
                                )}
                            >
                                <div className="map-studio-workflow-stack">
                                    <Segmented
                                        block
                                        value={brushMode}
                                        onChange={(value) => setBrushMode(value as BrushMode)}
                                        options={[
                                            { label: copy('calibrate.anchor'), value: 'anchor', icon: <AimOutlined /> },
                                            { label: copy('calibrate.walkable'), value: 'walkable', icon: <CheckCircleOutlined /> },
                                            { label: copy('calibrate.blocked'), value: 'blocked', icon: <BlockOutlined /> },
                                        ]}
                                    />
                                    {renderCollisionHelp()}
                                    <div className="map-studio-workflow-controls">
                                        <Segmented
                                            value={brushSize}
                                            onChange={(value) => setBrushSize(Number(value))}
                                            options={[1, 3, 5].map((size) => ({
                                                label: copy('calibrate.brushSize', { size }),
                                                value: size,
                                            }))}
                                        />
                                        <Button onClick={() => setShowCollisionOverlay((value) => !value)}>
                                            {copy(showCollisionOverlay ? 'calibrate.hideCollision' : 'calibrate.showCollision')}
                                        </Button>
                                        <Button disabled={!collisionStrokes.length} onClick={undoCollisionStroke}>
                                            {copy('calibrate.undo')}
                                        </Button>
                                        <Button
                                            disabled={!collisionEdits.length}
                                            onClick={() => {
                                                setCollisionEdits([]);
                                                setCollisionStrokes([]);
                                            }}
                                        >
                                            {copy('calibrate.clearPending')}
                                        </Button>
                                    </div>
                                    <Table
                                        className="map-studio-location-table"
                                        rowKey="id"
                                        size="small"
                                        pagination={draft.locations.length > 5 ? { pageSize: 5, size: 'small' } : false}
                                        dataSource={draft.locations}
                                        columns={columns}
                                        tableLayout="fixed"
                                    />
                                    <div className="map-studio-calibration-footer">
                                        <Button loading={saving} onClick={() => saveCalibration()}>
                                            {copy('calibrate.saveAndValidate')}
                                        </Button>
                                        <div className="map-studio-stat-tags">
                                            <Tag color="red">{copy('calibrate.savedBlocked', { count: collisionStats.savedBlocked })}</Tag>
                                            <Tag color="green">{copy('calibrate.savedWalkable', { count: collisionStats.savedWalkable })}</Tag>
                                            <Tag color="orange">{copy('calibrate.pendingBlocked', { count: collisionStats.pendingBlocked })}</Tag>
                                            <Tag color="green">{copy('calibrate.pendingWalkable', { count: collisionStats.pendingWalkable })}</Tag>
                                        </div>
                                    </div>
                                    <div className="map-studio-validation-panel">
                                        {draft.warnings.map((warning) => (
                                            <Alert key={warning} type="warning" showIcon message={warning} />
                                        ))}
                                        <Alert
                                            type={draft.validation.ok ? 'success' : 'error'}
                                            showIcon
                                            message={draft.validation.ok ? copy('validate.passed') : copy('validate.failed')}
                                            description={
                                                draft.validation.ok
                                                    ? draft.package_path
                                                    : draft.validation.errors.join(' ')
                                            }
                                        />
                                        <div className="map-studio-validation-actions">
                                            <Input
                                                addonBefore={copy('validate.mapId')}
                                                value={publishMapId}
                                                onChange={(event) => setPublishMapId(event.target.value)}
                                            />
                                            <Space wrap>
                                                <Button loading={saving} onClick={validateDraft}>
                                                    {copy('validate.validate')}
                                                </Button>
                                                <Tooltip title={draft.validation.ok ? '' : copy('validate.publishDisabled')}>
                                                    <Button
                                                        type="primary"
                                                        icon={<CheckCircleOutlined />}
                                                        loading={publishing}
                                                        disabled={!draft.validation.ok}
                                                        onClick={publishDraft}
                                                    >
                                                        {copy('validate.publish')}
                                                    </Button>
                                                </Tooltip>
                                                <Button
                                                    icon={<ExportOutlined />}
                                                    disabled={!draft.validation.ok}
                                                    onClick={exportMapPack}
                                                >
                                                    {copy('validate.exportZip')}
                                                </Button>
                                            </Space>
                                        </div>
                                        {published && (
                                            <Alert
                                                type="success"
                                                showIcon
                                                message={copy('validate.published', { map: published.map_id })}
                                                description={published.package_path}
                                                action={(
                                                    <Button
                                                        size="small"
                                                        type="primary"
                                                        onClick={() => navigate(`/setup?map_id=${encodeURIComponent(published.map_id)}`)}
                                                    >
                                                        {copy('validate.useInSetup')}
                                                    </Button>
                                                )}
                                            />
                                        )}
                                    </div>
                                </div>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
