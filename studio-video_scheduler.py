import sys
import vlc
import json
import hashlib
import datetime
import os
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QWidget, 
                            QVBoxLayout, QHBoxLayout, QFileDialog, QLabel, 
                            QTimeEdit, QCheckBox, QListWidget, QMessageBox,
                            QInputDialog, QLineEdit)
from PyQt5.QtCore import QTime, QTimer
from datetime import datetime, timedelta
import logging
from PyQt5.QtWidgets import QAction

class LicenseManager:
    def __init__(self):
        self.config_file = Path.home() / '.video_scheduler_config.json'
        self.trial_days = 7
        self.secret_key = "0fc081be3aaaa55bec5e2098eb7cc8ec"
        
    def get_license_info(self):
        if not self.config_file.exists():
            # Prvé spustenie - začiatok trial verzie
            info = {
                'first_run': datetime.now().isoformat(),
                'license_key': '',
                'email': ''
            }
            self.save_license_info(info)
            return info
        
        with open(self.config_file, 'r') as f:
            return json.load(f)
    
    def save_license_info(self, info):
        with open(self.config_file, 'w') as f:
            json.dump(info, f)
    
    def is_trial_valid(self):
        info = self.get_license_info()
        first_run = datetime.fromisoformat(info['first_run'])
        return datetime.now() - first_run < timedelta(days=self.trial_days)
    
    def is_license_valid(self, license_key, email):
        # Jednoduchá implementácia - v produkcii by mala byť bezpečnejšia
        expected_key = hashlib.md5(f"{email}{self.secret_key}".encode()).hexdigest()
        return license_key == expected_key
    
    def activate_license(self, license_key, email):
        if self.is_license_valid(license_key, email):
            info = self.get_license_info()
            info['license_key'] = license_key
            info['email'] = email
            self.save_license_info(info)
            return True
        return False

class VideoScheduler(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Nastavenie logovania
        self.setup_logging()
        self.logger.info("Aplikácia sa spúšťa")
        
        self.license_manager = LicenseManager()
        
        # Pridáme menu s aktiváciou
        self.setup_menu()
        
        if not self.check_license():
            sys.exit()
            
        # Najprv skontrolujeme VLC
        if not self.setup_vlc():
            sys.exit()
            
        self.setWindowTitle('Video Scheduler')
        self.setGeometry(100, 100, 800, 600)
        
        # VLC inštancia
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.current_video = None
        self.video1_path = ""
        self.video2_path = ""
        self.scheduled_times = []
        
        self.init_ui()
        
        # Timer pre kontrolu času
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_schedule)
        self.timer.start(1000)  # kontrola každú sekundu
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Video 1 sekcia
        video1_group = QVBoxLayout()
        video1_header = QHBoxLayout()
        
        self.video1_label = QLabel('Video 1 (slučka): Nevybrané')
        self.video1_btn = QPushButton('Vybrať Video 1')
        self.video1_btn.clicked.connect(lambda: self.select_video(1))
        
        video1_header.addWidget(self.video1_label)
        video1_header.addWidget(self.video1_btn)
        video1_group.addLayout(video1_header)
        
        # Video 2 sekcia
        video2_group = QVBoxLayout()
        video2_header = QHBoxLayout()
        
        self.video2_label = QLabel('Video 2: Nevybrané')
        self.video2_btn = QPushButton('Vybrať Video 2')
        self.video2_btn.clicked.connect(lambda: self.select_video(2))
        
        video2_header.addWidget(self.video2_label)
        video2_header.addWidget(self.video2_btn)
        video2_group.addLayout(video2_header)
        
        # Časový výber
        time_layout = QHBoxLayout()
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        add_time_btn = QPushButton('Pridať čas spustenia')
        add_time_btn.clicked.connect(self.add_scheduled_time)
        
        time_layout.addWidget(QLabel('Pridať čas spustenia:'))
        time_layout.addWidget(self.time_edit)
        time_layout.addWidget(add_time_btn)
        
        # Seznam naplánovaných časov
        self.time_list = QListWidget()
        remove_time_btn = QPushButton('Odstrániť vybraný čas')
        remove_time_btn.clicked.connect(self.remove_scheduled_time)
        
        # Ovládacie tlačidlá
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton('Spustiť')
        self.start_btn.clicked.connect(self.start_playback)
        self.stop_btn = QPushButton('Zastaviť')
        self.stop_btn.clicked.connect(self.stop_playback)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        
        # Pridanie všetkých komponentov do hlavného layoutu
        layout.addLayout(video1_group)
        layout.addLayout(video2_group)
        layout.addLayout(time_layout)
        layout.addWidget(QLabel('Scheduled times:'))
        layout.addWidget(self.time_list)
        layout.addWidget(remove_time_btn)
        layout.addLayout(control_layout)
        
    def select_video(self, video_num):
        filename, _ = QFileDialog.getOpenFileName(
            self, f'Select Video {video_num}',
            '', 'Video Files (*.mp4 *.avi *.mkv);;All Files (*.*)'
        )
        if filename:
            if video_num == 1:
                self.video1_path = filename
                self.video1_label.setText(f'Video 1: {filename}')
            else:
                self.video2_path = filename
                self.video2_label.setText(f'Video 2: {filename}')
    
    def add_scheduled_time(self):
        time = self.time_edit.time().toString("HH:mm")
        if time not in [self.time_list.item(i).text() for i in range(self.time_list.count())]:
            self.time_list.addItem(time)
            self.scheduled_times.append(time)
            self.scheduled_times.sort()
    
    def remove_scheduled_time(self):
        current_item = self.time_list.currentItem()
        if current_item:
            time = current_item.text()
            self.scheduled_times.remove(time)
            self.time_list.takeItem(self.time_list.row(current_item))
    
    def start_playback(self):
        if self.video1_path:
            self.play_video1()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
    
    def stop_playback(self):
        self.player.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def play_video1(self):
        try:
            self.logger.info("Spúšťam Video 1: %s", self.video1_path)
            media = self.instance.media_new(self.video1_path)
            self.player.set_media(media)
            self.player.play()
            self.current_video = 1
            
            @media.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached)
            def replay(event):
                self.logger.info("Video 1 skončilo, prehrávam znova")
                if self.current_video == 1:
                    self.player.set_position(0)
                    self.player.play()
        except Exception as e:
            self.logger.error("Chyba pri prehrávaní Video 1: %s", str(e))
            QMessageBox.critical(self, 'Chyba',
                               f'Nepodarilo sa prehrať Video 1:\n{str(e)}')
    
    def play_video2(self):
        try:
            self.logger.info("Spúšťam Video 2: %s", self.video2_path)
            self.current_video = 2
            media = self.instance.media_new(self.video2_path)
            self.player.set_media(media)
            self.player.play()
            
            @media.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached)
            def back_to_video1(event):
                self.logger.info("Video 2 skončilo, prepínam na Video 1")
                self.play_video1()
        except Exception as e:
            self.logger.error("Chyba pri prehrávaní Video 2: %s", str(e))
            QMessageBox.critical(self, 'Chyba',
                               f'Nepodarilo sa prehrať Video 2:\n{str(e)}')
    
    def check_schedule(self):
        current_time = datetime.now().strftime("%H:%M")
        if (current_time in self.scheduled_times and 
            self.video2_path and 
            self.current_video == 1):
            self.play_video2()
    
    def check_license(self):
        info = self.license_manager.get_license_info()
        
        if info['license_key']:
            if self.license_manager.is_license_valid(info['license_key'], info['email']):
                return True
        
        if self.license_manager.is_trial_valid():
            days_left = 7 - (datetime.now() - datetime.fromisoformat(info['first_run'])).days
            QMessageBox.information(self, 'Skúšobná verzia', 
                                  f'Používate skúšobnú verziu. Zostáva {days_left} dní.')
            return True
        
        return self.show_activation_dialog()
    
    def show_activation_dialog(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Skúšobná doba vypršala. Chcete aktivovať softvér?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if msg.exec_() == QMessageBox.Yes:
            email, ok = QInputDialog.getText(self, 'Aktivácia', 
                                           'Zadajte váš email:', QLineEdit.Normal)
            if ok and email:
                license_key, ok = QInputDialog.getText(self, 'Aktivácia', 
                                                     'Zadajte licenčný kľúč:', QLineEdit.Normal)
                if ok and license_key:
                    if self.license_manager.activate_license(license_key, email):
                        QMessageBox.information(self, 'Úspech', 
                                              'Softvér bol úspešne aktivovaný!')
                        return True
                    else:
                        QMessageBox.critical(self, 'Chyba', 
                                           'Neplatný licenčný kľúč!')
        
        return False

    def setup_vlc(self):
        # Štandardné cesty pre VLC
        standard_paths = [
            r"C:\Program Files\VideoLAN\VLC",
            r"C:\Program Files (x86)\VideoLAN\VLC",
            os.path.expanduser("~\\AppData\\Local\\Programs\\VideoLAN\\VLC")
        ]
        
        vlc_path = None
        
        # Skúsime nájsť VLC v štandardných cestách
        for path in standard_paths:
            if os.path.exists(os.path.join(path, "libvlc.dll")):
                vlc_path = path
                break
        
        # Ak sa nenašlo VLC, spýtame sa používateľa
        if not vlc_path:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("VLC player nebol nájdený v štandardných priečinkoch.\n"
                       "Prosím, vyberte priečinok kde je nainštalovaný VLC player.")
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            
            if msg.exec_() == QMessageBox.Ok:
                vlc_path = QFileDialog.getExistingDirectory(
                    self, 
                    "Vyberte priečinok s VLC player",
                    os.path.expanduser("~"),
                    QFileDialog.ShowDirsOnly
                )
            else:
                return False
        
        if not vlc_path:
            QMessageBox.critical(self, 'Chyba',
                               'VLC player je potrebný pre fungovanie aplikácie.\n'
                               'Prosím, nainštalujte VLC player a spustite aplikáciu znova.')
            return False
            
        # Kontrola či vybraný priečinok obsahuje potrebné súbory
        required_files = ['libvlc.dll', 'libvlccore.dll']
        missing_files = [f for f in required_files 
                        if not os.path.exists(os.path.join(vlc_path, f))]
        
        if missing_files:
            QMessageBox.critical(self, 'Chyba',
                               f'Vybraný priečinok neobsahuje potrebné VLC súbory:\n'
                               f'{", ".join(missing_files)}')
            return False
        
        # Nastavenie VLC cesty do systémovej PATH
        os.environ['PATH'] = vlc_path + os.pathsep + os.environ['PATH']
        
        # Inicializácia VLC
        try:
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            return True
        except Exception as e:
            QMessageBox.critical(self, 'Chyba',
                               f'Nepodarilo sa inicializovať VLC player:\n{str(e)}')
            return False

    def setup_logging(self):
        # Získanie cesty k priečinku STUDIO na ploche
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        log_dir = os.path.join(desktop_path, "STUDIO", "logs")
        
        # Vytvorenie priečinka pre logy ak neexistuje
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Nastavenie logovania
        log_file = os.path.join(log_dir, f"videoschedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Aplikácia spustená - inicializácia logovania")

    def setup_menu(self):
        menubar = self.menuBar()
        help_menu = menubar.addMenu('Pomoc')
        
        # Aktivačná akcia
        activate_action = QAction('Aktivovať produkt', self)
        activate_action.triggered.connect(self.show_activation_dialog)
        help_menu.addAction(activate_action)
        
        # O programe
        about_action = QAction('O programe', self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        info = self.license_manager.get_license_info()
        if info['license_key']:
            status = "Plná verzia"
        else:
            days_left = 7 - (datetime.now() - datetime.fromisoformat(info['first_run'])).days
            status = f"Skúšobná verzia (zostáva {days_left} dní)"
            
        QMessageBox.information(self, 'O programe',
                              f'Video Scheduler\n\n'
                              f'Stav: {status}\n'
                              f'Email: {info["email"] if info["email"] else "Neregistrované"}\n\n'
                              f'👨‍💻 Kódované s vášňou a kreativitou od Erika\n\n'
                              f'Version: 1.0\n'
                              f'Author: Erik Fedor - Trify s.r.o.')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoScheduler()
    window.show()
    sys.exit(app.exec_())