import { AiOutlineClose } from "react-icons/ai";

export type MediaViewerState = {
  url: string;
  name: string;
  mimeType: string | null;
} | null;

function MediaViewer({
  media,
  onClose,
}: {
  media: MediaViewerState;
  onClose: () => void;
}) {
  if (!media) return null;

  const isVideo = (media.mimeType || "").startsWith("video/");
  const isImage = (media.mimeType || "").startsWith("image/");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] max-w-[95vw] overflow-hidden rounded-xl bg-black shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 z-10 rounded-full bg-black/60 p-2 text-white hover:bg-black/80"
          aria-label="Close preview"
        >
          <AiOutlineClose className="h-5 w-5" />
        </button>
        <p className="truncate px-12 py-3 text-sm text-white/90">{media.name}</p>
        {isVideo ? (
          <video
            key={media.url}
            src={media.url}
            controls
            autoPlay
            className="max-h-[80vh] max-w-[95vw]"
          />
        ) : isImage ? (
          <img
            src={media.url}
            alt={media.name}
            className="max-h-[80vh] max-w-[95vw] object-contain [image-orientation:from-image]"
          />
        ) : (
          <div className="p-8 text-white">
            Preview is not available for this file type.
          </div>
        )}
      </div>
    </div>
  );
}

export default MediaViewer;
