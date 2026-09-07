export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type UserProfile = {
  id: string;
  email: string;
  display_name: string | null;
  bytes_used: number;
  bytes_limit: number;
};

export type StorageQuota = {
  bytes_used: number;
  bytes_limit: number;
  bytes_remaining: number;
  usage_percent: number;
};

export type ApiFolder = {
  id: string;
  name: string;
  parent_id: string | null;
  path: string;
  is_trashed: boolean;
  created_at: string;
  updated_at: string;
};

export type ApiFile = {
  id: string;
  name: string;
  folder_id: string | null;
  mime_type: string | null;
  size_bytes: number;
  status: string;
  is_trashed: boolean;
  created_at: string;
  updated_at: string;
};

export type FolderTreeNode = {
  id: string;
  name: string;
  parent_id: string | null;
  path: string;
  children: FolderTreeNode[];
};

export type TrashItem = {
  resource_type: string;
  resource_id: string;
  name: string;
  trashed_at: string | null;
  size_bytes: number | null;
};

export type ShareResponse = {
  id: string;
  resource_type: string;
  resource_id: string;
  grantee_user_id: string | null;
  role: string;
  token: string | null;
  expires_at: string | null;
  created_at: string;
};

export type SharedLinkAccess = {
  share_id: string;
  resource_type: string;
  resource_id: string;
  role: string;
  resource_name: string;
};
