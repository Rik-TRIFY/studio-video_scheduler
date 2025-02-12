import os
import subprocess
from pathlib import Path
import ctypes
import win32gui
import win32con

def clear_icon_cache():
    try:
        print("Čistím Windows icon cache...")
        
        # Zastavíme Windows Explorer
        subprocess.run(['taskkill', '/F', '/IM', 'explorer.exe'], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Cesty k icon cache súborom
        cache_paths = [
            Path(os.getenv('LOCALAPPDATA')) / 'IconCache.db',
            Path(os.getenv('LOCALAPPDATA')) / 'Microsoft/Windows/Explorer/iconcache*',
            Path(os.getenv('LOCALAPPDATA')) / 'Microsoft/Windows/Explorer/thumbcache*'
        ]
        
        # Vymažeme cache súbory
        for path in cache_paths:
            try:
                if isinstance(path, str) and '*' in path:
                    # Pre wildcard cesty
                    import glob
                    for f in glob.glob(str(path)):
                        try:
                            os.remove(f)
                            print(f"Vymazaný cache: {f}")
                        except:
                            pass
                elif path.exists():
                    os.remove(path)
                    print(f"Vymazaný cache: {path}")
            except Exception as e:
                print(f"Nemôžem vymazať {path}: {e}")
        
        # Vyčistíme systémový icon cache
        win32gui.SystemParametersInfo(win32con.SPI_SETICONS, 0, 0, 
                                    win32con.SPIF_UPDATEINIFILE | win32con.SPIF_SENDCHANGE)
        
        # Reštartujeme Explorer
        subprocess.Popen('explorer.exe')
        
        print("\nIcon cache bol vyčistený!")
        print("1. Reštartujte počítač")
        print("2. Po reštarte spustite VideoScheduler")
        
    except Exception as e:
        print(f"Chyba: {str(e)}")
        input("Stlačte Enter pre ukončenie...")

if __name__ == "__main__":
    # Kontrola admin práv
    if ctypes.windll.shell32.IsUserAnAdmin():
        clear_icon_cache()
        input("\nStlačte Enter pre ukončenie...")
    else:
        print("Tento skript vyžaduje administrátorské práva!")
        print("Prosím, spustite CMD ako administrátor a skúste znova.")
        input("Stlačte Enter pre ukončenie...")
