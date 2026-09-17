# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
root = Path(SPECPATH)
datas = [
    (str(root/'risk_rules.json'), '.'),
    (str(root/'knowledge_seed.json'), '.'),
    (str(root/'device_models.json'), '.'),
    (str(root/'production_config.json'), '.'),
]
a = Analysis(['android_cleaner.py'], pathex=[str(root)], binaries=[], datas=datas, hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='AndroidCleaner', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False, disable_windowed_traceback=False, argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None, icon=None)
