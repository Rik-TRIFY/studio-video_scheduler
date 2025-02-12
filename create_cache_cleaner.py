import PyInstaller.__main__

PyInstaller.__main__.run([
    'clear_icon_cache.py',
    '--onefile',
    '--uac-admin',  # Vyžiada admin práva
    '--name=VideoScheduler_ClearCache',
    '--icon=resources/icons/icon.ico',
    '--noconsole',
    '--add-data=resources/icons/icon.ico;resources/icons'
])
