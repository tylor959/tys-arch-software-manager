# Maintainer: Ty <ty@tys-asm.dev>
pkgname=tys-asm
pkgver=1.0.0
pkgrel=1
pkgdesc="Ty's ASM - A friendly software center for Arch Linux"
arch=('any')
url="https://github.com/tys-asm/arch-software-manager"
license=('GPL3')
depends=(
    'python>=3.11'
    'python-pyqt6'
    'python-requests'
    'polkit'
)
optdepends=(
    'paru: AUR package installation'
    'flatpak: Flatpak/Flathub support'
    'debtap: .deb file installation'
    'rpmextract: .rpm file installation'
    'papirus-icon-theme: better icon resolution'
    'paccache: package cache cleaning'
    'reflector: mirror list management'
)
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
    cd "$srcdir/$pkgname-$pkgver"

    # Install Python package
    install -d "$pkgdir/usr/lib/python3.14/site-packages"
    cp -r asm "$pkgdir/usr/lib/python3.14/site-packages/"

    # Install launcher script
    install -Dm755 /dev/stdin "$pkgdir/usr/bin/tys-asm" <<'LAUNCHER'
#!/bin/bash
exec python3 -m asm.main "$@"
LAUNCHER

    # Install desktop file
    install -Dm644 /dev/stdin "$pkgdir/usr/share/applications/tys-asm.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Ty's ASM
GenericName=Software Manager
Comment=A friendly software center for Arch Linux
Exec=tys-asm
Icon=system-software-install
Terminal=false
Categories=System;PackageManager;
Keywords=software;packages;install;remove;update;
DESKTOP

    # Install polkit policy
    install -Dm644 polkit/org.tys-asm.policy "$pkgdir/usr/share/polkit-1/actions/org.tys-asm.policy"
}
