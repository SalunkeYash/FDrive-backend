"""Model import smoke tests (no DB required)."""

from models import File, FileObject, Folder, Share, TrashEntry, UploadSession, User


def test_model_tablenames() -> None:
    assert User.__tablename__ == "users"
    assert Folder.__tablename__ == "folders"
    assert File.__tablename__ == "files"
    assert FileObject.__tablename__ == "file_objects"
    assert Share.__tablename__ == "shares"
    assert TrashEntry.__tablename__ == "trash_entries"
    assert UploadSession.__tablename__ == "upload_sessions"
