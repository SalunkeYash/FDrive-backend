import { useState } from "react";
import { HiOutlineArrowsExpand } from "react-icons/hi";
import {
  MdDriveFileRenameOutline,
  MdOutlineDriveFileMove,
  MdOutlineRestore,
  MdOutlineShare,
  MdStarBorder,
  MdStarRate,
} from "react-icons/md";
import { RiDeleteBin6Line, RiFolderSettingsLine } from "react-icons/ri";
import { TbDownload } from "react-icons/tb";
import { useNavigate } from "react-router-dom";
import { useDrive } from "@/context/DriveContext";
import type { FileDropDownProps } from "@/types";
import MoveModal from "./MoveModal";
import ShareModal from "./ShareModal";

function FileDropDown({
  file,
  setOpenMenu,
  select,
  isFolderComp,
  folderId,
  setRenameToggle,
}: FileDropDownProps) {
  const navigate = useNavigate();
  const {
    starEntry,
    trashEntry,
    deleteEntry,
    openOrDownloadFile,
    downloadFolder,
  } = useDrive();
  const [showOrganize, setShowOrganize] = useState(false);
  const [showMove, setShowMove] = useState(false);
  const [showShare, setShowShare] = useState(false);

  const closeMenu = () => setOpenMenu("");
  const role = file.accessRole ?? "owner";
  const isOwner = role === "owner";
  const canEdit = role === "owner" || role === "editor";

  return (
    <>
      {!showMove && !showShare && (
      <section
        onClick={(event) => event.stopPropagation()}
        className="absolute top-9 z-10 max-h-80 w-56 overflow-y-auto rounded-md border bg-white py-1 shadow-sm shadow-[#777]"
      >
        {select !== "trashed" ? (
          <>
            <button
              type="button"
              onClick={() => {
                closeMenu();
                if (isFolderComp) navigate(`/drive/folders/${folderId}`);
                else void openOrDownloadFile(file.id, "open");
              }}
              className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
            >
              <HiOutlineArrowsExpand className="h-5 w-5" />
              <span className="text-sm">Open</span>
            </button>

            {isOwner && (
              <button
                type="button"
                onClick={() => setShowShare(true)}
                className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
              >
                <MdOutlineShare className="h-5 w-5" />
                <span className="text-sm">Share</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                if (isFolderComp) {
                  closeMenu();
                  void downloadFolder(folderId);
                } else {
                  closeMenu();
                  void openOrDownloadFile(file.id, "download");
                }
              }}
              className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
            >
              <TbDownload className="h-5 w-5" />
              <span className="text-sm">Download</span>
            </button>

            {canEdit && (
              <button
                type="button"
                onClick={() => {
                  closeMenu();
                  setRenameToggle(file.id);
                }}
                className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
              >
                <MdDriveFileRenameOutline className="h-5 w-5" />
                <span className="text-sm">Rename</span>
              </button>
            )}

            {canEdit && (
              <div className="border-t border-[#e0e3e7]">
                <button
                  type="button"
                  onClick={() => setShowOrganize((prev) => !prev)}
                  className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
                >
                  <RiFolderSettingsLine className="h-5 w-5" />
                  <span className="text-sm">Organize</span>
                </button>
                {showOrganize && (
                  <button
                    type="button"
                    onClick={() => setShowMove(true)}
                    className="flex w-full items-center space-x-3 bg-[#f8fafc] py-1.5 pl-10 pr-3 hover:bg-[#ddd]"
                  >
                    <MdOutlineDriveFileMove className="h-5 w-5" />
                    <span className="text-sm">Move</span>
                  </button>
                )}
              </div>
            )}

            <button
              type="button"
              onClick={() => {
                closeMenu();
                starEntry(file.id, !file.isStarred);
              }}
              className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
            >
              {file.isStarred ? (
                <MdStarRate className="h-5 w-5 text-yellow-500" />
              ) : (
                <MdStarBorder className="h-5 w-5" />
              )}
              <span className="text-sm">
                {file.isStarred ? "Remove star" : "Add to starred"}
              </span>
            </button>

            {isOwner && (
              <button
                type="button"
                onClick={() => {
                  closeMenu();
                  void trashEntry(file.id, true);
                }}
                className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
              >
                <RiDeleteBin6Line className="h-5 w-5" />
                <span className="text-sm">Move to bin</span>
              </button>
            )}
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => {
                closeMenu();
                void trashEntry(file.id, false);
              }}
              className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
            >
              <MdOutlineRestore className="h-5 w-5" />
              <span className="text-sm">Restore</span>
            </button>
            <button
              type="button"
              onClick={() => {
                closeMenu();
                void deleteEntry(file.id);
              }}
              className="flex w-full items-center space-x-3 px-3 py-1.5 hover:bg-[#ddd]"
            >
              <RiDeleteBin6Line className="h-5 w-5" />
              <span className="text-sm">Delete forever</span>
            </button>
          </>
        )}
      </section>
      )}

      {showMove && (
        <MoveModal
          entry={file}
          onClose={() => {
            setShowMove(false);
            closeMenu();
          }}
        />
      )}
      {showShare && (
        <ShareModal
          entry={file}
          onClose={() => {
            setShowShare(false);
            closeMenu();
          }}
        />
      )}
    </>
  );
}

export default FileDropDown;
