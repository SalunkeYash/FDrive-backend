import { MdOutlineCreateNewFolder } from "react-icons/md";
import UploadFileBtn from "./UploadFileBtn";
import type { folderToggleAndUpload } from "@/types";

function DropDown({
  setFolderToggle,
  setIsDropDown,
  uploadFile,
  uploadFolderFiles,
}: folderToggleAndUpload) {
  return (
    <div
      onClick={() => setIsDropDown(false)}
      className="absolute -left-5 -top-20 flex h-screen w-screen items-center justify-center"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="absolute left-6 top-[68px] w-72 rounded-md bg-white text-textC shadow-md shadow-[#bbb]"
      >
        <div className="border-b py-2">
          <button
            onClick={() => setFolderToggle(true)}
            className="flex w-full items-center space-x-3 px-4 py-1.5 hover:bg-darkC"
          >
            <MdOutlineCreateNewFolder className="h-5 w-5" />
            <span>New folder</span>
          </button>
        </div>
        <div className="border-b py-2">
          <UploadFileBtn
            uploadFile={uploadFile}
            uploadFolderFiles={uploadFolderFiles}
          />
        </div>
      </div>
    </div>
  );
}

export default DropDown;
