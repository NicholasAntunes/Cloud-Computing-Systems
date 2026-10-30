import type { ApiError, FileItem, FileListResponse } from '../types';

const MAX_FILE_SIZE = 100 * 1024 * 1024;
const MOCK_MODE = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_DATA !== 'false';

let accessToken: string | null = null;

const mockFiles: FileItem[] = [
  {
    id: '6f1c2a9e-3b7d-4e0a-9c51-2d8f0b7a4e13',
    name: 'Q3-project-overview.pdf',
    content_type: 'application/pdf',
    size_bytes: 2483021,
    current_version: 3,
    created_at: '2026-10-12T10:18:00Z',
    updated_at: '2026-10-29T14:42:00Z',
    owner: { id: 1, username: 'admin' },
    updated_by: { id: 1, username: 'admin' },
    permissions: { can_read: true, can_update: true, can_share: true, can_delete: true },
  },
  {
    id: '3d142fe1-87bd-49eb-b884-5c0fa0a84a02',
    name: 'brand-guidelines.png',
    content_type: 'image/png',
    size_bytes: 1845067,
    current_version: 2,
    created_at: '2026-10-08T08:30:00Z',
    updated_at: '2026-10-27T16:05:00Z',
    owner: { id: 1, username: 'admin' },
    updated_by: { id: 1, username: 'admin' },
    permissions: { can_read: true, can_update: true, can_share: true, can_delete: true },
  },
  {
    id: '75c27a1b-5587-4aeb-8e55-2ee7daf3b824',
    name: 'meeting-notes.docx',
    content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    size_bytes: 428192,
    current_version: 1,
    created_at: '2026-10-25T11:12:00Z',
    updated_at: '2026-10-25T11:12:00Z',
    owner: { id: 1, username: 'admin' },
    updated_by: { id: 1, username: 'admin' },
    permissions: { can_read: true, can_update: true, can_share: true, can_delete: true },
  },
  {
    id: 'ad159f63-54cc-417b-831a-562d0f44d20e',
    name: 'design-system.zip',
    content_type: 'application/zip',
    size_bytes: 16777216,
    current_version: 5,
    created_at: '2026-09-18T09:00:00Z',
    updated_at: '2026-10-21T13:26:00Z',
    owner: { id: 1, username: 'admin' },
    updated_by: { id: 1, username: 'admin' },
    permissions: { can_read: true, can_update: true, can_share: true, can_delete: true },
  },
];

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

function createApiError(code: string, message: string, details?: unknown): ApiError {
  return details === undefined ? { code, message } : { code, message, details };
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (typeof body === 'object' && body !== null && 'error' in body) {
      const error = body.error;
      if (typeof error === 'object' && error !== null && 'code' in error && 'message' in error) {
        return error as ApiError;
      }
    }
    if (typeof body === 'object' && body !== null && 'code' in body && 'message' in body) {
      return body as ApiError;
    }
    return createApiError('INTERNAL_ERROR', `Richiesta non riuscita (${response.status}).`, body);
  } catch {
    return createApiError('INTERNAL_ERROR', response.statusText || 'Errore imprevisto del server.');
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/api/')) {
    throw createApiError('INVALID_API_PATH', 'Le richieste devono usare un percorso relativo /api/.');
  }

  const headers = new Headers(init.headers);
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(path, { ...init, headers });

  if (!response.ok) throw await errorFromResponse(response);
  return response;
}

function mockDelay(): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, 250));
}

export async function fetchFiles(): Promise<FileListResponse> {
  if (MOCK_MODE) {
    await mockDelay();
    return {
      items: [...mockFiles].sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
      total: mockFiles.length,
    };
  }

  const response = await apiFetch('/api/files?limit=100&offset=0');
  return (await response.json()) as FileListResponse;
}

export async function uploadFile(file: File): Promise<FileItem> {
  if (file.size > MAX_FILE_SIZE) {
    throw createApiError('FILE_TOO_LARGE', 'Il file supera il limite consentito di 100 MB.');
  }
  if (file.size === 0) {
    throw createApiError('VALIDATION_ERROR', 'Non è possibile caricare un file vuoto.');
  }

  if (MOCK_MODE) {
    await mockDelay();
    const now = new Date().toISOString();
    const uploaded: FileItem = {
      id: crypto.randomUUID(),
      name: file.name,
      content_type: file.type || 'application/octet-stream',
      size_bytes: file.size,
      current_version: 1,
      created_at: now,
      updated_at: now,
      owner: { id: 1, username: 'admin' },
      updated_by: { id: 1, username: 'admin' },
      permissions: { can_read: true, can_update: true, can_share: true, can_delete: true },
    };
    mockFiles.unshift(uploaded);
    return uploaded;
  }

  const form = new FormData();
  form.append('file', file);
  const response = await apiFetch('/api/files', { method: 'POST', body: form });
  return (await response.json()) as FileItem;
}

export async function downloadFile(file: FileItem): Promise<void> {
  let blob: Blob;
  if (MOCK_MODE) {
    await mockDelay();
    blob = new Blob([`Contenuto dimostrativo di ${file.name}`], { type: file.content_type });
  } else {
    const response = await apiFetch(`/api/files/${encodeURIComponent(file.id)}/download`);
    blob = await response.blob();
  }

  const objectUrl = URL.createObjectURL(blob);
  const anchor = Object.assign(document.createElement('a'), {
    href: objectUrl,
    download: file.name,
  });
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
