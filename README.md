# Ty's ASM — Arch Software Manager

A friendly, graphical software center for Arch Linux designed for brand-new users who want a simple way to install, remove, and manage their software.

## Features

- **Installed Programs** — View, remove, and manage your installed apps. Smart filter shows GUI apps by default, with a toggle for all packages. Add desktop shortcuts, browse install directories, and more.
- **Repository Browser** — Search and install from official Arch Linux repositories with categories and sorting.
- **AUR Browser** — Search, sort by votes/popularity, and install community packages from the AUR (via paru or the AUR RPC API).
- **File Installer** — Drag-and-drop installation from `.deb`, `.rpm`, `.tar.gz`, `.tar.zst`, `.AppImage`, and `.flatpak` files with self-diagnostics and missing dependency detection.
- **Flatpak / Flathub** — Browse and install sandboxed applications from Flathub with auto-setup.
- **Settings & Diagnostics** — Theme toggle (dark/light), repo manager, system health checks with one-click fixes.

## Requirements

- **Arch Linux** (or Arch-based distro like CachyOS, EndeavourOS, Manjaro)
- Python 3.11+
- PyQt6
- polkit (for privilege escalation)

### Optional Dependencies

| Package | Purpose |
|---------|---------|
| `paru` | AUR package installation (recommended) |
| `flatpak` | Flatpak/Flathub support |
| `debtap` | `.deb` file installation |
| `rpmextract` | `.rpm` file installation |
| `papirus-icon-theme` | Better icon resolution |
| `paccache` | Package cache cleaning |
| `reflector` | Mirror list management |

## Installation

### From AUR (recommended)

```bash
paru -S tys-asm
```

### Manual Installation

```bash
git clone https://github.com/tys-asm/arch-software-manager.git
cd arch-software-manager
pip install -r requirements.txt
python -m asm.main
```

## Running

```bash
tys-asm
```

Or launch "Ty's ASM" from your application menu.

## Screenshots

*Coming soon*

## License

GPLv3 — see [LICENSE](LICENSE)

## Author

**Ty** — Built with care for the Arch Linux community.
