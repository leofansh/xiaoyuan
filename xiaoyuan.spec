# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Xiaoyuan desktop app

import os
import sys
from pathlib import Path

block_cipher = None

# Root directory
ROOT_DIR = os.path.dirname(os.path.abspath(SPEC))

# Collect all backend files
backend_tree = Tree(os.path.join(ROOT_DIR, 'backend'), prefix='backend')

# Collect frontend files
frontend_tree = Tree(os.path.join(ROOT_DIR, 'frontend'), prefix='frontend')

# Collect data files
data_tree = Tree(os.path.join(ROOT_DIR, 'data'), prefix='data')

a = Analysis(
    [os.path.join(ROOT_DIR, 'run.py')],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=[
        (os.path.join(ROOT_DIR, 'frontend'), 'frontend'),
        (os.path.join(ROOT_DIR, 'backend'), 'backend'),
        (os.path.join(ROOT_DIR, 'data'), 'data'),
        (os.path.join(ROOT_DIR, 'assets'), 'assets'),
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'backend',
        'backend.main',
        'backend.config',
        'backend.agent',
        'backend.agent.persona',
        'backend.agent.chat',
        'backend.agent.assessment',
        'backend.services',
        'backend.services.llm',
        'backend.services.storage',
        'backend.services.ocr',
        'backend.services.repetition',
        'backend.services.teaching_journal',
        'backend.models',
        'backend.models.student',
        'backend.knowledge',
        'backend.knowledge.syllabus',
        'openai',
        'httpx',
        'pydantic',
        'rapidocr_onnxruntime',
        'pystray',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Xiaoyuan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Xiaoyuan',
)
