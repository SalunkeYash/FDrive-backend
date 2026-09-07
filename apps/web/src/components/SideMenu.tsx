import { useState, type ChangeEvent } from "react";
import { HiOutlinePlusSm } from "react-icons/hi";
import DropDown from "./addBtnComponents/DropDown";
import AddFolder from "./addBtnComponents/AddFolder";
import Navbar from "./Navbar";
import ProgressIndicator from "./ProgressIndicator";
import { useDrive } from "@/context/DriveContext";
import { formatBytes } from "@/lib/utils";

function SideMenu({ currentFolderId = "" }: { currentFolderId?: string }) {
  const [isDropDown, setIsDropDown] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [folderToggle, setFolderToggle] = useState(false);
  const {
    addFolder,
    quota,
    uploads,
    setUploads,
    uploadFlatFiles,
    uploadPathFiles,
  } = useDrive();

  const bytesUsed = quota?.bytes_used ?? 0;
  const bytesLimit = quota?.bytes_limit ?? 1;

  const uploadFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    await uploadFlatFiles(files, currentFolderId);
  };

  const uploadFolder = async () => addFolder(folderName, currentFolderId);

  const uploadFolderFiles = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    await uploadPathFiles(
      files.map((file) => ({
        file,
        relativePath: file.webkitRelativePath || file.name,
      })),
      currentFolderId,
    );
  };

  return (
    <section className="relative h-[90vh] w-16 space-y-4 duration-500 tablet:w-60">
      <button
        onClick={() => setIsDropDown(true)}
        className="mt-1 flex w-fit items-center justify-center space-x-2 rounded-2xl bg-white p-3 text-textC shadow-md shadow-[#ddd] duration-300 hover:bg-darkC2 hover:shadow-[#bbb] tablet:px-5 tablet:py-4"
      >
        <HiOutlinePlusSm className="h-6 w-6" />
        <span className="hidden text-sm font-medium tablet:block">New</span>
      </button>
      {isDropDown && (
        <DropDown
          setFolderToggle={setFolderToggle}
          uploadFile={uploadFile}
          uploadFolderFiles={uploadFolderFiles}
          setIsDropDown={setIsDropDown}
        />
      )}
      <ProgressIndicator uploads={uploads} setUploads={setUploads} />
      {folderToggle && (
        <AddFolder
          setFolderToggle={setFolderToggle}
          setFolderName={setFolderName}
          uploadFolder={uploadFolder}
        />
      )}
      <Navbar />
      <div className="absolute bottom-4 left-0 w-full pr-4">
        <div className="rounded-2xl bg-white/90 px-2 py-3 text-sm text-textC shadow-sm shadow-[#ddd] tablet:px-4">
          <div className="mb-2 flex items-center justify-between font-medium">
            <span className="hidden tablet:block">Storage</span>
            <span>
              {formatBytes(bytesUsed)} / {formatBytes(bytesLimit)}
            </span>
          </div>
          <div className="hidden h-2 overflow-hidden rounded-full bg-darkC2 tablet:block">
            <div
              className={`h-full rounded-full ${
                bytesUsed >= bytesLimit / 1.25 ? "bg-red-500" : "bg-[#1a73e8]"
              }`}
              style={{
                width: `${Math.min(100, (bytesUsed / bytesLimit) * 100)}%`,
              }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

export default SideMenu;
