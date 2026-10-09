"""core/encrypt.py —— 加密文件检测与解密（从原脚本迁移）。

- 只限制编辑的 PDF 零密码可解，正常合并；
- 需要打开密码的 PDF/Office 由调用方（回调）决定：预置密码 / 询问用户 / 跳过。
"""
from __future__ import annotations

from pathlib import Path

from core.deps import ensure_module

OOXML_EXTS = {".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm"}
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def office_needs_password(path: Path) -> bool:
    """判断 Office 文件是否需要打开密码。

    docx/xlsx/pptx 正常是 zip 包，加了打开密码后会变成 OLE 复合文档；
    老格式 doc/xls/ppt 则看文件里有没有加密流。
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
            if path.suffix.lower() in OOXML_EXTS:
                return head == OLE_MAGIC
            blob = fh.read(4 * 1024 * 1024)
        return b"EncryptedPackage" in blob or b"EncryptionInfo" in blob
    except OSError:
        return False


def decrypt_office(src: Path, passwords: list[str], tmp_dir: Path,
                   index: int) -> Path | None:
    """把带打开密码的 Office 文件解密成临时副本（msoffcrypto）。"""
    if not passwords:
        return None
    if not ensure_module("msoffcrypto", "msoffcrypto-tool"):
        return None

    import msoffcrypto

    out = tmp_dir / f"{index:04d}_decrypted{src.suffix.lower()}"
    for pwd in passwords:
        try:
            with open(src, "rb") as fh, open(out, "wb") as ofh:
                office = msoffcrypto.OfficeFile(fh)
                office.load_key(password=pwd)
                office.decrypt(ofh)
            if out.exists() and out.stat().st_size > 0:
                return out
        except Exception:
            try:
                out.unlink()
            except OSError:
                pass
            continue
    return None


def office_password_ok(src: Path, password: str, tmp_dir: Path) -> bool:
    """验证 Office 打开密码是否正确（能解开就是对的）。"""
    return decrypt_office(src, [password], tmp_dir, 9999) is not None


def pdf_needs_password(path: Path) -> bool:
    """PDF 是否需要打开密码（只限制编辑/打印的 PDF 不算）。"""
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
        if not reader.is_encrypted:
            return False
        try:
            return not bool(reader.decrypt(""))
        except Exception:
            return True
    except Exception:
        return False


def pdf_password_ok(path: Path, password: str) -> bool:
    """用某个密码试着打开 PDF，判断密码是否正确。"""
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
        return (not reader.is_encrypted) or bool(reader.decrypt(password))
    except Exception:
        return False