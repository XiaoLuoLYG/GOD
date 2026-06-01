import { fetchCustom } from './fetch';

export type PackageType = 'map' | 'agent' | 'experiment';

export type PackageValidation = {
  ok: boolean;
  errors: string[];
  warnings: string[];
};

export type PackagePreview = {
  preview_token: string;
  package_type: PackageType;
  resource_id: string;
  display_name: string;
  validation: PackageValidation;
  dependencies: Array<{ type: string; id: string }>;
  conflict: boolean;
  install_path: string;
};

export type PackageInstallResult = {
  status: string;
  package_type?: PackageType;
  resource_id?: string;
  install_path?: string;
};

async function responseError(response: Response): Promise<Error> {
  const text = await response.text();
  try {
    const payload = JSON.parse(text);
    return new Error(typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail || payload));
  } catch {
    return new Error(text || response.statusText);
  }
}

export async function previewPackage(file: File): Promise<PackagePreview> {
  const body = new FormData();
  body.append('file', file);
  const response = await fetchCustom('/api/v1/god/packages/import-preview', {
    method: 'POST',
    body,
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.json();
}

export async function installPackage(
  previewToken: string,
  conflictStrategy: 'save_as' | 'overwrite' | 'cancel',
  requestedId?: string,
): Promise<PackageInstallResult> {
  const response = await fetchCustom('/api/v1/god/packages/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      preview_token: previewToken,
      conflict_strategy: conflictStrategy,
      requested_id: requestedId || undefined,
    }),
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.json();
}

export async function cancelPackagePreview(previewToken: string): Promise<void> {
  const response = await fetchCustom('/api/v1/god/packages/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      preview_token: previewToken,
      conflict_strategy: 'cancel',
    }),
  });
  if (!response.ok) {
    throw await responseError(response);
  }
}
