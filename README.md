# Ty's ASM — Arch Software Manager

A friendly, graphical software center for Arch Linux designed for brand-new users who want a simple way to install, remove, and manage their software.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running](#running)
- [Usage Guide](#usage-guide)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

### Installed Programs

- View all installed applications with a smart filter (GUI apps by default)
- Toggle to show all packages (libraries, fonts, CLI tools)
- Search and sort (A–Z, Z–A, by size)
- **Remove** packages with one click
- **Add desktop shortcut** for any app
- **Browse install directory** — open the folder containing an app’s files
- Per-package view of installed files

### Repository Browser

- Search official Arch Linux repositories
- Browse by category/group
- Sort by name or size
- Install and remove packages from core, extra, community, multilib

### AUR Browser

- Search the Arch User Repository
- Sort by votes or popularity
- Install and remove AUR packages
- **AUR helper:** Uses paru when available, falls back to yay
- **Auto-install:** If neither paru nor yay is installed, offers to install paru from official repos
- **Password prompt:** Uses polkit (pkexec) or opens a terminal so you can enter your password when running from a GUI launcher

### Snap

- Browse and install from the Snap Store
- Same layout as Repositories and AUR (search, sort, install/remove)
- Setup panel when snapd is not installed — one-click install via paru
- Requires `snapd` and `snapd.socket` enabled

### Flatpak / Flathub

- Browse and install sandboxed apps from Flathub
- Auto-setup Flathub remote when Flatpak is first used
- **Move to disk** — move Flatpak apps between installations (e.g. root vs custom disk)
- Supports custom Flatpak installations configured in `/etc/flatpak/installations.d/`

### Install from File

Drag and drop or browse to install from local files:

| Format | Description | Requirements |
|--------|-------------|--------------|
| `.deb` | Debian packages | debtap (AUR) |
| `.rpm` | RPM packages | rpmextract, rpm2cpio, or bsdtar |
| `.tar.gz`, `.tar.zst`, `.tar.xz`, `.tar.bz2` | Source tarballs | tar, make |
| `.AppImage` | Portable apps | None |
| `.flatpak`, `.flatpakref` | Flatpak bundles | flatpak |

- **Self-diagnostics:** Detects missing tools and offers to install them
- **Progress feedback:** Step-by-step status for DEB conversion (debtap)
- **Build detection:** Auto-detects PKGBUILD, Makefile, configure, install.sh in tarballs

### Settings & Diagnostics

**General**

- Theme: dark / light
- Default sort order
- Auto-add desktop shortcut on install
- Show all packages by default
- Default install disk for AppImages

**Disk Setup**

- Select a disk for application storage
- Auto-configure: creates `Applications` folder, sets permissions, sets as default
- Useful for storing apps on a separate data partition

**Repositories**

- View enabled/disabled repos from `/etc/pacman.conf`
- Add custom repositories
- Toggle repos on/off
- Sync package databases

**Diagnostics**

- **Full diagnostics:** Disk space, keyring health, orphaned packages, package cache size, failed services, broken symlinks, pacman lock
- **One-click fixes** for common issues
- **Quick actions:** Refresh keyring, populate keyring, clean cache, remove orphans, update mirror list, force sync databases

### Log Viewer

- Press `Ctrl+Shift+L` to open the log viewer
- View application log for debugging crashes and issues
- Copy to clipboard, open in external editor
- Log file: `~/.cache/tys-asm/tys-asm.log`

---

## Requirements

### Required

- **Arch Linux** (or Arch-based: CachyOS, EndeavourOS, Manjaro, etc.)
- **Python 3.11+**
- **PyQt6**
- **polkit** — for privilege escalation (pkexec)

### Optional (for full functionality)

| Package | Purpose |
|---------|---------|
| `paru` or `yay` | AUR package installation (paru preferred; can auto-install) |
| `flatpak` | Flatpak/Flathub support |
| `snapd` | Snap Store support |
| `debtap` | `.deb` file installation (AUR) |
| `rpmextract` or `bsdtar` | `.rpm` file installation |
| `papirus-icon-theme` | Better icon resolution |
| `paccache` | Package cache cleaning (diagnostics) |
| `reflector` | Mirror list management (diagnostics) |

---

## Installation

### Step 1: From AUR (recommended)

If you have paru:

```bash
paru -S tys-asm
```

If you have yay:

```bash
yay -S tys-asm
```

### Step 2: Manual installation (from source)

```bash
# 1. Install system dependencies (Arch)
sudo pacman -S python python-pyqt6 python-requests polkit

# 2. Clone the repository
git clone https://github.com/tylor959/tys-arch-software-manager.git
cd tys-arch-software-manager

# 3. Run from source (no install)
python -m asm.main
```

To install the `tys-asm` command so you can run it from anywhere:

```bash
# After steps 1–2 above:
pip install -e .
# Then run: tys-asm
```

### Step 3: AppImage (portable)

If an AppImage build is available, download it, make it executable, and run:

```bash
chmod +x tys-asm-*.AppImage
./tys-asm-*.AppImage
```

---

## Running

```bash
tys-asm
```

Or launch **Ty's ASM** from your application menu (System → Ty's ASM or similar).

---

## Usage Guide

### First-time setup

1. **AUR:** If you install an AUR package and don’t have paru or yay, the app will offer to install paru from official repos.
2. **Flatpak:** On first use, the app will add the Flathub remote if needed.
3. **Snap:** If snapd is not installed, use the setup panel to install it via paru.

### Installing from a file

1. Go to **Install File** in the sidebar.
2. Drag and drop a file, or click **Browse Files**.
3. The app analyzes the file and shows type, size, and required tools.
4. If tools are missing (e.g. debtap for .deb), click **Install Missing Tools**.
5. Click **Install** and follow the progress dialog.

### Moving a Flatpak app to another disk

1. Go to **Flatpak** → Installed tab.
2. Find the app and click **Move**.
3. Select the target installation (disk) from the dropdown.
4. Confirm; the app is uninstalled from the current location and installed to the target.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+L` | Open log viewer |

---

## Configuration

Settings are stored in `~/.config/tys-asm/settings.json`.

| Setting | Description |
|---------|-------------|
| `theme` | `dark` or `light` |
| `default_sort` | Default sort order |
| `auto_desktop_shortcut` | Add desktop shortcut on install |
| `show_all_packages` | Show all packages (not just apps) |
| `default_install_disk` | Default disk for AppImage installs |

---

## Troubleshooting

### "Can't install AUR package as root"

AUR helpers (paru, yay) must run as a normal user. Ty's ASM runs them unprivileged; when they need sudo, a polkit dialog or terminal will appear. If no dialog appears, ensure polkit is installed and try launching from a terminal.

### DEB conversion fails

- Ensure debtap is installed: `paru -S debtap`
- Update the debtap database: `sudo debtap -u`
- Check the log (`Ctrl+Shift+L`) for debtap output

### RPM extraction fails

Install one of: `rpmextract`, or `bsdtar` (from libarchive). Ty's ASM will use whichever is available.

### Log file location

`~/.cache/tys-asm/tys-asm.log`

---

## License

GPLv3 — see [LICENSE](LICENSE)

---

## Author

**Ty** — Built with care for the Arch Linux community.
