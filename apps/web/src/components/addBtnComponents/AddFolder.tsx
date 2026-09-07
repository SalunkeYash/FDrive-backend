import { useState } from "react";
import type { folderToggleProps } from "@/types";

function AddFolder({
  setFolderToggle,
  setFolderName,
  uploadFolder,
}: folderToggleProps) {
  const addFolder = async () => {
    const createdId = await uploadFolder();
    if (createdId) setFolderToggle(false);
  };

  return (
    <div
      onClick={() => setFolderToggle(false)}
      className="absolute -left-5 -top-20 z-20 flex h-screen w-screen items-center justify-center bg-darkC2/40"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-96 space-y-6 rounded-xl bg-white p-5 shadow-lg shadow-[#bbb]"
      >
        <h2 className="text-2xl">New folder</h2>
        <input
          className="w-full rounded-md border border-textC py-2 indent-5 outline-textC2"
          type="text"
          placeholder="Untitled folder"
          onChange={(e) => setFolderName(e.target.value)}
        />
        <div className="flex w-full justify-end space-x-5 pr-3 font-medium text-textC2">
          <button
            type="button"
            onClick={() => setFolderToggle(false)}
            className="rounded-full px-3 py-2 hover:bg-darkC2"
          >
            Cancel
          </button>
          <button
            onClick={() => void addFolder()}
            className="rounded-full px-3 py-2 hover:bg-darkC2"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

export default AddFolder;
