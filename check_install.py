import os
import sys
import platform
from pathlib import Path
import ctypes
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow
from PyQt5.QtGui import QIcon

class InstallChecker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Video Scheduler - Kontrola inštalácie')
        self.run_checks()
        
    def run_checks(self):
        issues = []
        
        # Kontrola existencie resources priečinka
        resources_path = Path("resources")
        if not resources_path.exists():
            issues.append("- Chýba priečinok resources")
            
        # Kontrola ikon
        icons_path = resources_path / "icons" / "icon.ico"
        if not icons_path.exists():
            issues.append("- Chýba súbor icon.ico")
            
        # Kontrola VLC
        vlc_paths = [
            r"C:\Program Files\VideoLAN\VLC",
            r"C:\Program Files (x86)\VideoLAN\VLC"
        ]
        vlc_found = any(Path(p).exists() for p in vlc_paths)
        if not vlc_found:
            issues.append("- Nenašiel sa VLC player")
        
        if issues:
            msg = "Našli sa nasledujúce problémy:\n\n" + "\n".join(issues) + \
                  "\n\nOdporúčania:\n" + \
                  "1. Rozbaľte celý ZIP archív\n" + \
                  "2. Nainštalujte VLC player\n" + \
                  "3. Spustite VideoScheduler.exe ako správca"
            QMessageBox.warning(self, 'Kontrola zlyhala', msg)
        else:
            QMessageBox.information(self, 'Kontrola úspešná',
                                  'Všetko je pripravené!\n\n' + 
                                  'Môžete spustiť VideoScheduler.exe')

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        checker = InstallChecker()
        checker.show()
        sys.exit(app.exec_())
    except Exception as e:
        QMessageBox.critical(None, 'Chyba',
                           f'Kritická chyba pri kontrole:\n{str(e)}')
