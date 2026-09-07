import { useState, type FormEvent } from "react";
import { AiOutlineClose, AiOutlineLink } from "react-icons/ai";
import { MdOutlinePersonAddAlt } from "react-icons/md";
import { api, ApiError } from "@/api/client";
import type { FileEntry } from "@/types";

type ShareModalProps = {
  entry: FileEntry;
  onClose: () => void;
};

function ShareModal({ entry, onClose }: ShareModalProps) {
  const resourceType = entry.isFolder ? "folder" : "file";
  const title = entry.isFolder ? entry.folderName : entry.fileName;

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"viewer" | "editor">("viewer");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);

  const shareWithUser = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.createUserShare({
        resourceType,
        resourceId: entry.id,
        granteeEmail: email.trim(),
        role,
      });
      setMessage(`Shared with ${email.trim()} as ${role}.`);
      setEmail("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not share");
    } finally {
      setBusy(false);
    }
  };

  const createLink = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const share = await api.createLinkShare({
        resourceType,
        resourceId: entry.id,
        role,
      });
      if (!share.token) {
        setError("Share link was not created.");
        return;
      }
      const url = `${window.location.origin}/share/${share.token}`;
      setLink(url);
      await navigator.clipboard.writeText(url);
      setMessage("Link created and copied to clipboard.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create link");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-drive-modal
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="truncate pr-3 text-lg font-medium text-[#1f1f1f]">
            Share “{title}”
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-full p-1.5 hover:bg-darkC2"
            aria-label="Close"
          >
            <AiOutlineClose className="h-5 w-5" />
          </button>
        </div>

        <label className="mb-3 block text-sm text-textC">
          Permission
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "viewer" | "editor")}
            className="mt-1 w-full rounded-lg border border-[#dadce0] px-3 py-2 outline-none focus:border-[#1a73e8]"
          >
            <option value="viewer">Viewer</option>
            <option value="editor">Editor</option>
          </select>
        </label>

        <form onSubmit={shareWithUser} className="space-y-3">
          <label className="block text-sm text-textC">
            Share with people
            <div className="mt-1 flex gap-2">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="someone@example.com"
                className="w-full rounded-lg border border-[#dadce0] px-3 py-2 outline-none focus:border-[#1a73e8]"
              />
              <button
                type="submit"
                disabled={busy}
                className="flex shrink-0 items-center gap-1 rounded-full bg-[#1a73e8] px-3 py-2 text-sm font-medium text-white hover:bg-[#1558b0] disabled:opacity-60"
              >
                <MdOutlinePersonAddAlt className="h-5 w-5" />
                Share
              </button>
            </div>
          </label>
        </form>

        <div className="my-4 border-t border-[#e0e3e7]" />

        <button
          type="button"
          disabled={busy}
          onClick={() => {
            void createLink();
          }}
          className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left hover:bg-darkC2 disabled:opacity-60"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e8f0fe]">
            <AiOutlineLink className="h-5 w-5 text-[#1a73e8]" />
          </span>
          <span>
            <span className="block text-sm font-medium text-[#1f1f1f]">
              Create shareable link
            </span>
            <span className="block text-xs text-textC">
              Anyone with the link can access
            </span>
          </span>
        </button>

        {link && (
          <p className="mt-2 break-all rounded-lg bg-darkC2 px-3 py-2 text-xs text-textC">
            {link}
          </p>
        )}
        {message && <p className="mt-2 text-sm text-[#188038]">{message}</p>}
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full px-4 py-2 text-sm font-medium text-[#1a73e8] hover:bg-[#e8f0fe]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export default ShareModal;
