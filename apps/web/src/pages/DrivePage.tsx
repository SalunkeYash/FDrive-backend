import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { FileItem, FolderItem, StorageQuota } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { formatBytes } from "../lib/format";

type Crumb = { id: string | null; name: string };

export function DrivePage() {
  const { user, loading, logout } = useAuth();
  const [folderId, setFolderId] = useState<string | null>(null);
  const [crumbs, setCrumbs] = useState<Crumb[]>([{ id: null, name: "My Drive" }]);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [quota, setQuota] = useState<StorageQuota | null>(null);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async (id: string | null) => {
    setError(null);
    setSearching(false);
    const [folderList, fileList, quotaData] = await Promise.all([
      api.listFolders(id),
      api.listFolderFiles(id),
      api.getStorageQuota(),
    ]);
    setFolders(folderList);
    setFiles(fileList);
    setQuota(quotaData);
  }, []);

  useEffect(() => {
    if (!user) return;
    load(folderId).catch((err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Failed to load drive");
    });
  }, [user, folderId, load]);

  if (loading) {
    return <div className="center-screen muted">Loading…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;

  function openFolder(folder: FolderItem) {
    setFolderId(folder.id);
    setCrumbs((prev) => [...prev, { id: folder.id, name: folder.name }]);
  }

  function jumpTo(index: number) {
    const next = crumbs.slice(0, index + 1);
    setCrumbs(next);
    setFolderId(next[next.length - 1]?.id ?? null);
  }

  async function onCreateFolder() {
    const name = window.prompt("Folder name");
    if (!name?.trim()) return;
    setBusy(true);
    try {
      await api.createFolder(name.trim(), folderId);
      await load(folderId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create folder");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(selected: FileList | null) {
    if (!selected?.length) return;
    setBusy(true);
    setError(null);
    try {
      for (const file of Array.from(selected)) {
        await api.requestUpload(file, folderId);
      }
      await load(folderId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) {
      setSearching(false);
      await load(folderId);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.searchDrive(query.trim());
      setSearching(true);
      setFolders(result.folders);
      setFiles(result.files);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDownload(file: FileItem) {
    try {
      await api.downloadFile(file.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download failed");
    }
  }

  async function onTrash(file: FileItem) {
    if (!window.confirm(`Move “${file.name}” to trash?`)) return;
    setBusy(true);
    try {
      await api.moveFileToTrash(file.id);
      await load(folderId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not trash file");
    } finally {
      setBusy(false);
    }
  }

  const usage = quota?.usage_percent ?? 0;

  return (
    <div className="drive-shell">
      <aside className="drive-side">
        <p className="brand">FDrive</p>
        <p className="side-user">{user.display_name || user.email}</p>
        {quota && (
          <div className="quota">
            <div className="quota-track">
              <div className="quota-fill" style={{ width: `${Math.min(usage, 100)}%` }} />
            </div>
            <p className="muted small">
              {formatBytes(quota.bytes_used)} of {formatBytes(quota.bytes_limit)}
            </p>
          </div>
        )}
        <button type="button" className="btn-ghost" onClick={() => void logout()}>
          Sign out
        </button>
      </aside>

      <main className="drive-main">
        <header className="drive-top">
          <nav className="crumbs" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <button
                key={`${c.id ?? "root"}-${i}`}
                type="button"
                className="crumb"
                onClick={() => jumpTo(i)}
              >
                {c.name}
              </button>
            ))}
          </nav>
          <form className="search" onSubmit={(e) => void onSearch(e)}>
            <input
              type="search"
              placeholder="Search files and folders"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className="btn-secondary" disabled={busy}>
              Search
            </button>
          </form>
        </header>

        <div className="toolbar">
          <button
            type="button"
            className="btn-primary"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
          >
            Upload
          </button>
          <input
            ref={fileInput}
            type="file"
            className="sr-only"
            multiple
            onChange={(e) => void onUpload(e.target.files)}
          />
          <button
            type="button"
            className="btn-secondary"
            disabled={busy || searching}
            onClick={() => void onCreateFolder()}
          >
            New folder
          </button>
        </div>

        {error && <p className="error banner">{error}</p>}
        {searching && (
          <p className="muted banner">Search results for “{query.trim()}”</p>
        )}

        <section className="listing">
          {folders.length === 0 && files.length === 0 && (
            <p className="empty">This folder is empty. Upload a file to begin.</p>
          )}
          {folders.map((folder) => (
            <button
              key={folder.id}
              type="button"
              className="row folder-row"
              onClick={() => openFolder(folder)}
            >
              <span className="row-icon" aria-hidden>
                ▢
              </span>
              <span className="row-name">{folder.name}</span>
              <span className="row-meta muted">Folder</span>
            </button>
          ))}
          {files.map((file) => (
            <div key={file.id} className="row file-row">
              <span className="row-icon" aria-hidden>
                ▭
              </span>
              <span className="row-name">{file.name}</span>
              <span className="row-meta muted">{formatBytes(file.size_bytes)}</span>
              <div className="row-actions">
                <button type="button" className="btn-ghost" onClick={() => void onDownload(file)}>
                  Download
                </button>
                <button type="button" className="btn-ghost danger" onClick={() => void onTrash(file)}>
                  Trash
                </button>
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
