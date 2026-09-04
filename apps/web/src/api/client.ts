import type {
  FileItem,
  FolderItem,
  SearchDriveResponse,
  StorageQuota,
  TokenResponse,
  UserProfile,
} from "./types";

const ACCESS_KEY = "fdrive_access_token";
const REFRESH_KEY = "fdrive_refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function storeTokens(tokens: TokenResponse): void {
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;
  try {
    const body = (await res.json()) as { detail?: string | { msg: string }[] };
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      message = body.detail[0].msg;
    }
  } catch {
    /* ignore */
  }
  return new ApiError(res.status, message);
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  auth = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(path, { ...options, headers });
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  registerAccount(email: string, password: string, displayName?: string) {
    return apiFetch<TokenResponse>(
      "/api/v1/auth/register-account",
      {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          display_name: displayName || null,
        }),
      },
      false,
    );
  },

  login(email: string, password: string) {
    return apiFetch<TokenResponse>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    );
  },

  logout() {
    const refresh = getRefreshToken();
    if (!refresh) return Promise.resolve();
    return apiFetch<void>(
      "/api/v1/auth/logout",
      { method: "POST", body: JSON.stringify({ refresh_token: refresh }) },
      false,
    ).catch(() => undefined);
  },

  getProfile() {
    return apiFetch<UserProfile>("/api/v1/account/profile");
  },

  getStorageQuota() {
    return apiFetch<StorageQuota>("/api/v1/account/storage-quota");
  },

  async listFolders(parentId?: string | null) {
    const q =
      parentId === undefined || parentId === null
        ? ""
        : `?parent_folder_id=${encodeURIComponent(parentId)}`;
    const data = await apiFetch<{ folders: FolderItem[] }>(
      `/api/v1/folders/list-folder-contents${q}`,
    );
    return data.folders;
  },

  createFolder(name: string, parentId?: string | null) {
    return apiFetch<FolderItem>("/api/v1/folders/create-folder", {
      method: "POST",
      body: JSON.stringify({ name, parent_folder_id: parentId ?? null }),
    });
  },

  listFolderFiles(folderId?: string | null) {
    const q =
      folderId === undefined || folderId === null
        ? ""
        : `?folder_id=${encodeURIComponent(folderId)}`;
    return apiFetch<FileItem[]>(`/api/v1/files/list-folder-files${q}`);
  },

  async requestUpload(file: File, folderId?: string | null) {
    const meta = await apiFetch<{
      file_id: string;
      upload_url: string;
      required_headers: Record<string, string>;
    }>("/api/v1/files/request-upload-url", {
      method: "POST",
      body: JSON.stringify({
        file_name: file.name,
        size_bytes: file.size,
        mime_type: file.type || null,
        folder_id: folderId ?? null,
      }),
    });

    const putHeaders = new Headers(meta.required_headers);
    const put = await fetch(meta.upload_url, {
      method: "PUT",
      headers: putHeaders,
      body: file,
    });
    if (!put.ok) {
      throw new ApiError(put.status, "Upload to storage failed");
    }

    return apiFetch<FileItem>(`/api/v1/files/${meta.file_id}/complete-upload`, {
      method: "POST",
    });
  },

  async downloadFile(fileId: string) {
    const data = await apiFetch<{
      download_url: string;
      file_name: string;
    }>(`/api/v1/files/${fileId}/request-download-url`);
    window.open(data.download_url, "_blank", "noopener,noreferrer");
  },

  moveFileToTrash(fileId: string) {
    return apiFetch<FileItem>(`/api/v1/trash/files/${fileId}/move-file-to-trash`, {
      method: "POST",
    });
  },

  searchDrive(q: string) {
    return apiFetch<SearchDriveResponse>(
      `/api/v1/search/search-drive?q=${encodeURIComponent(q)}`,
    );
  },
};
