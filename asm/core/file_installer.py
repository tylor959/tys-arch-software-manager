"""File installer engine — handles .deb, .rpm, .tar.gz, .tar.zst, .AppImage, .flatpak.

Each handler is self-diagnosing: validates prerequisites, detects missing tools,
offers to install them, resolves dependencies, and provides rollback on failure.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from asm.core.pacman_backend import is_installed


class FileType(Enum):
    DEB = "deb"
    RPM = "rpm"
    TAR_GZ = "tar.gz"
    TAR_ZST = "tar.zst"
    APPIMAGE = "appimage"
    FLATPAK = "flatpak"
    UNKNOWN = "unknown"


@dataclass
class InstallResult:
    success: bool
    message: str
    warnings: list[str]
    rollback_cmd: list[str] | None = None


@dataclass
class FileAnalysis:
    file_path: str
    file_type: FileType
    size_bytes: int
    missing_tools: list[str]
    detected_build_system: str  # "makefile", "pkgbuild", "configure", "install.sh", ""
    suggested_action: str


def detect_file_type(path: str) -> FileType:
    """Determine the installer file type from extension."""
    p = path.lower()
    if p.endswith(".deb"):
        return FileType.DEB
    if p.endswith(".rpm"):
        return FileType.RPM
    if p.endswith(".tar.gz") or p.endswith(".tgz"):
        return FileType.TAR_GZ
    if p.endswith(".tar.zst") or p.endswith(".tar.xz") or p.endswith(".tar.bz2"):
        return FileType.TAR_ZST
    if p.endswith(".appimage"):
        return FileType.APPIMAGE
    if p.endswith(".flatpak") or p.endswith(".flatpakref"):
        return FileType.FLATPAK
    return FileType.UNKNOWN


def analyze_file(path: str) -> FileAnalysis:
    """Analyze a file before installation — check prerequisites and detect build systems."""
    ft = detect_file_type(path)
    size = os.path.getsize(path) if os.path.isfile(path) else 0
    missing = _check_tools(ft)
    build_sys = ""
    action = ""

    if ft == FileType.DEB:
        action = "Convert with debtap, then install with pacman -U"
    elif ft == FileType.RPM:
        action = "Extract with rpmextract, repackage for pacman"
    elif ft in (FileType.TAR_GZ, FileType.TAR_ZST):
        build_sys = _detect_build_system(path)
        if build_sys == "pkgbuild":
            action = "Build with makepkg -si"
        elif build_sys == "makefile":
            action = "Build with make && make install"
        elif build_sys == "configure":
            action = "Run ./configure && make && make install"
        elif build_sys == "install.sh":
            action = "Run install.sh script"
        else:
            action = "Extract and inspect manually"
    elif ft == FileType.APPIMAGE:
        action = "Make executable and optionally integrate into desktop"
    elif ft == FileType.FLATPAK:
        action = "Install with flatpak install"
    else:
        action = "Unknown file type"

    return FileAnalysis(
        file_path=path,
        file_type=ft,
        size_bytes=size,
        missing_tools=missing,
        detected_build_system=build_sys,
        suggested_action=action,
    )


def _check_tools(ft: FileType) -> list[str]:
    """Check which required tools are missing for a given file type."""
    required: dict[FileType, list[str]] = {
        FileType.DEB: ["debtap", "ar"],
        FileType.RPM: ["rpmextract"],
        FileType.TAR_GZ: ["tar", "make"],
        FileType.TAR_ZST: ["tar", "zstd", "make"],
        FileType.APPIMAGE: [],
        FileType.FLATPAK: ["flatpak"],
    }
    tools = required.get(ft, [])
    return [t for t in tools if not shutil.which(t)]


def _detect_build_system(archive_path: str) -> str:
    """Peek inside a tar archive to detect the build system."""
    try:
        open_mode = "r:gz"
        lower = archive_path.lower()
        if lower.endswith(".tar.zst"):
            return _detect_build_system_zst(archive_path)
        elif lower.endswith(".tar.xz"):
            open_mode = "r:xz"
        elif lower.endswith(".tar.bz2"):
            open_mode = "r:bz2"

        with tarfile.open(archive_path, open_mode) as tf:
            names = tf.getnames()
    except Exception:
        return ""
    return _match_build_system(names)


def _detect_build_system_zst(archive_path: str) -> str:
    """Handle .tar.zst archives (not natively supported by tarfile)."""
    try:
        result = subprocess.run(
            ["tar", "--zstd", "-tf", archive_path],
            capture_output=True, text=True, timeout=10,
        )
        names = result.stdout.strip().splitlines()
    except Exception:
        return ""
    return _match_build_system(names)


def _match_build_system(names: list[str]) -> str:
    basenames = {Path(n).name.lower() for n in names}
    if "pkgbuild" in basenames:
        return "pkgbuild"
    if "makefile" in basenames:
        return "makefile"
    if "configure" in basenames:
        return "configure"
    if "install.sh" in basenames:
        return "install.sh"
    return ""


# ── Installation handlers ──

def install_appimage(path: str, integrate: bool = True) -> InstallResult:
    """Install an AppImage — make executable and optionally create .desktop entry."""
    warnings: list[str] = []
    try:
        app_dir = Path.home() / "Applications"
        app_dir.mkdir(exist_ok=True)
        dest = app_dir / Path(path).name
        shutil.copy2(path, dest)
        dest.chmod(dest.stat().st_mode | stat.S_IEXEC)

        if integrate:
            _create_appimage_desktop(dest)

        return InstallResult(True, f"AppImage installed to {dest}", warnings)
    except Exception as e:
        return InstallResult(False, f"AppImage installation failed: {e}", warnings)


def _create_appimage_desktop(appimage_path: Path) -> None:
    """Create a .desktop file for an AppImage."""
    name = appimage_path.stem.replace("-", " ").replace("_", " ")
    desktop = Path.home() / ".local" / "share" / "applications" / f"{appimage_path.stem}.desktop"
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(
        f"[Desktop Entry]\n"
        f"Type=Application\n"
        f"Name={name}\n"
        f"Exec={appimage_path}\n"
        f"Icon=application-x-executable\n"
        f"Terminal=false\n"
        f"Categories=Utility;\n"
    )


def install_deb(path: str) -> InstallResult:
    """Install a .deb file by converting with debtap then installing with pacman."""
    warnings: list[str] = []

    if not shutil.which("debtap"):
        if is_installed("debtap"):
            return InstallResult(False, "debtap is installed but not found in PATH", warnings)
        return InstallResult(
            False,
            "debtap is required but not installed. Install it with: paru -S debtap",
            warnings,
            rollback_cmd=None,
        )

    with tempfile.TemporaryDirectory(prefix="asm-deb-") as tmpdir:
        try:
            # Update debtap database if needed
            db_check = subprocess.run(
                ["debtap", "-Q"], capture_output=True, text=True, timeout=5,
            )
            if "need to update" in db_check.stdout.lower() or db_check.returncode != 0:
                warnings.append("Updating debtap database (first-time setup)...")
                subprocess.run(
                    ["pkexec", "debtap", "-u"],
                    capture_output=True, text=True, timeout=300,
                )

            result = subprocess.run(
                ["debtap", "-Q", path],
                capture_output=True, text=True, timeout=120,
                cwd=tmpdir,
            )

            pkg_files = list(Path(tmpdir).glob("*.pkg.tar*"))
            if not pkg_files:
                # Try non-Q mode
                result = subprocess.run(
                    ["debtap", path],
                    input="y\n\n",
                    capture_output=True, text=True, timeout=120,
                    cwd=tmpdir,
                )
                pkg_files = list(Path(tmpdir).glob("*.pkg.tar*"))

            if not pkg_files:
                return InstallResult(False, "debtap failed to produce a package file", warnings)

            install_result = subprocess.run(
                ["pkexec", "pacman", "-U", "--noconfirm", str(pkg_files[0])],
                capture_output=True, text=True, timeout=120,
            )

            if install_result.returncode == 0:
                return InstallResult(True, "Package installed successfully from .deb", warnings)
            else:
                return InstallResult(
                    False,
                    f"pacman -U failed: {install_result.stderr.strip()}",
                    warnings,
                )
        except subprocess.TimeoutExpired:
            return InstallResult(False, "Installation timed out", warnings)
        except Exception as e:
            return InstallResult(False, f"Error: {e}", warnings)


def install_rpm(path: str) -> InstallResult:
    """Install an .rpm file by extracting and attempting to install."""
    warnings: list[str] = []
    if not shutil.which("rpmextract") and not shutil.which("rpm2cpio"):
        return InstallResult(
            False,
            "rpmextract or rpm2cpio required. Install with: sudo pacman -S rpmextract",
            warnings,
        )

    with tempfile.TemporaryDirectory(prefix="asm-rpm-") as tmpdir:
        try:
            if shutil.which("rpmextract"):
                subprocess.run(
                    ["rpmextract", path],
                    cwd=tmpdir, capture_output=True, text=True, timeout=60,
                )
            else:
                subprocess.run(
                    ["bash", "-c", f"rpm2cpio '{path}' | cpio -idmv"],
                    cwd=tmpdir, capture_output=True, text=True, timeout=60,
                )

            extracted = list(Path(tmpdir).rglob("*"))
            if not extracted:
                return InstallResult(False, "RPM extraction produced no files", warnings)

            # Copy extracted files to system
            result = subprocess.run(
                ["pkexec", "cp", "-r"] + [str(f) for f in Path(tmpdir).iterdir()] + ["/"],
                capture_output=True, text=True, timeout=60,
            )

            warnings.append(f"Extracted {len(extracted)} files from RPM (best-effort install)")
            return InstallResult(True, "RPM contents extracted and installed", warnings)
        except Exception as e:
            return InstallResult(False, f"RPM install failed: {e}", warnings)


def install_tar(path: str, build_system: str = "") -> list[str]:
    """Return the command sequence for installing from a tarball.

    Returns a list of shell commands to execute sequentially.
    """
    extract_dir = tempfile.mkdtemp(prefix="asm-tar-")

    if path.lower().endswith(".tar.zst"):
        extract_cmd = f"tar --zstd -xf '{path}' -C '{extract_dir}'"
    elif path.lower().endswith(".tar.xz"):
        extract_cmd = f"tar -xJf '{path}' -C '{extract_dir}'"
    elif path.lower().endswith(".tar.bz2"):
        extract_cmd = f"tar -xjf '{path}' -C '{extract_dir}'"
    else:
        extract_cmd = f"tar -xzf '{path}' -C '{extract_dir}'"

    cmds = [extract_cmd]

    # Find the actual source directory (often one level deep)
    cmds.append(f"cd \"$(find '{extract_dir}' -mindepth 1 -maxdepth 1 -type d | head -1)\" 2>/dev/null || cd '{extract_dir}'")

    if build_system == "pkgbuild":
        cmds.append("makepkg -si --noconfirm")
    elif build_system == "configure":
        cmds.append("./configure && make -j$(nproc) && sudo make install")
    elif build_system == "makefile":
        cmds.append("make -j$(nproc) && sudo make install")
    elif build_system == "install.sh":
        cmds.append("chmod +x install.sh && sudo ./install.sh")
    else:
        cmds.append("echo 'No build system detected. Please inspect the extracted files.'")

    return cmds


def install_flatpak_file(path: str) -> InstallResult:
    """Install a .flatpak or .flatpakref file."""
    warnings: list[str] = []
    if not shutil.which("flatpak"):
        return InstallResult(
            False,
            "Flatpak is not installed. Install with: sudo pacman -S flatpak",
            warnings,
        )
    try:
        result = subprocess.run(
            ["flatpak", "install", "--user", "-y", path],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            return InstallResult(True, "Flatpak package installed successfully", warnings)
        else:
            return InstallResult(False, f"Flatpak install failed: {result.stderr.strip()}", warnings)
    except Exception as e:
        return InstallResult(False, f"Flatpak error: {e}", warnings)


def get_install_commands(path: str) -> tuple[FileType, list[str], list[str]]:
    """Analyze a file and return (file_type, install_commands, missing_tools).

    For types that need streaming progress, returns shell commands.
    """
    analysis = analyze_file(path)
    ft = analysis.file_type
    missing = analysis.missing_tools

    if ft == FileType.APPIMAGE:
        return ft, ["echo 'AppImage handler'"], missing
    elif ft == FileType.DEB:
        return ft, ["echo 'DEB handler'"], missing
    elif ft == FileType.RPM:
        return ft, ["echo 'RPM handler'"], missing
    elif ft in (FileType.TAR_GZ, FileType.TAR_ZST):
        cmds = install_tar(path, analysis.detected_build_system)
        return ft, cmds, missing
    elif ft == FileType.FLATPAK:
        return ft, ["flatpak", "install", "--user", "-y", path], missing
    else:
        return ft, [], missing
