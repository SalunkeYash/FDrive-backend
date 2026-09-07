import { useEffect, useRef, useState } from "react";
import { AiFillFolder, AiOutlineSearch } from "react-icons/ai";
import { useNavigate } from "react-router-dom";
import { useDrive } from "@/context/DriveContext";
import fileIcons from "../fileIcons";

function Search() {
  const [searchText, setSearchText] = useState("");
  const [onFocus, setOnFocus] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { entries, openOrDownloadFile } = useDrive();
  const navigate = useNavigate();

  const searchList = entries.filter((item) => {
    if (!searchText || item.isTrashed) return false;
    const query = searchText.toLowerCase();
    return (
      item.fileName?.toLowerCase().includes(query) ||
      item.folderName?.toLowerCase().includes(query)
    );
  });

  const showResults = onFocus && searchText.trim().length > 0;

  useEffect(() => {
    const handleDocumentClick = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOnFocus(false);
      }
    };
    document.addEventListener("click", handleDocumentClick);
    return () => document.removeEventListener("click", handleDocumentClick);
  }, []);

  return (
    <div ref={containerRef} className="relative w-full max-w-[860px]">
      <div
        className={`flex items-center rounded-full bg-darkC2 px-4 transition-shadow ${
          onFocus ? "bg-white shadow-md ring-1 ring-[#dadce0]" : "hover:bg-[#e7ebf0]"
        }`}
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-textC">
          <AiOutlineSearch className="h-5 w-5" />
        </span>
        <input
          onFocus={() => setOnFocus(true)}
          onChange={(e) => setSearchText(e.target.value)}
          value={searchText}
          type="search"
          placeholder="Search in Drive"
          className="w-full bg-transparent py-3 pr-3 text-base text-textC placeholder:text-[#5f6368] outline-none"
        />
      </div>

      {showResults && (
        <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-20 max-h-60 overflow-y-auto rounded-2xl bg-white py-2 shadow-lg ring-1 ring-[#dadce0]">
          {searchList.length === 0 ? (
            <div className="px-5 py-2 text-sm text-[#5f6368]">
              No results match your search.
            </div>
          ) : (
            searchList.map((item) => {
              const icon =
                fileIcons[item.fileExtension as keyof typeof fileIcons] ??
                fileIcons["any"];
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setOnFocus(false);
                    setSearchText("");
                    if (item.isFolder) navigate(`/drive/folders/${item.id}`);
                    else void openOrDownloadFile(item.id, "open");
                  }}
                  className="flex w-full items-center space-x-3.5 px-4 py-2 text-left hover:bg-darkC2"
                >
                  <span className="h-6 w-6 shrink-0">
                    {item.isFolder ? (
                      <AiFillFolder className="h-full w-full text-textC" />
                    ) : (
                      icon
                    )}
                  </span>
                  <span className="w-full truncate text-sm">
                    {item.fileName || item.folderName}
                  </span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

export default Search;
