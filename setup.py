from setuptools import setup, find_packages

setup(
    name="tys-asm",
    version="1.0.0",
    description="Ty's ASM - Arch Software Manager",
    author="Ty",
    license="GPLv3",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "PyQt6>=6.7.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "tys-asm=asm.main:main",
        ],
    },
    package_data={
        "asm": [
            "themes/*.qss",
            "assets/icons/*",
            "assets/*.svg",
        ],
    },
)
