export interface UserRef {
  id: number;
  username: string;
}

export interface FilePermissions {
  can_read: boolean;
  can_update: boolean;
  can_share: boolean;
  can_delete: boolean;
}

export interface FileItem {
  id: string;
  name: string;
  content_type: string;
  size_bytes: number;
  current_version: number;
  created_at: string;
  updated_at: string;
  owner: UserRef;
  updated_by: UserRef;
  permissions: FilePermissions;
}

export interface FileListResponse {
  items: FileItem[];
  total: number;
}

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
}
