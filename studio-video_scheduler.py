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
                            QInputDialog, QLineEdit, QDialog, QDialogButtonBox)
from PyQt5.QtCore import QTime, QTimer
from datetime import datetime, timedelta
import logging
from PyQt5.QtWidgets import QAction
import platform
import requests
import re

# Na začiatku súboru pridáme konštantu pre verziu
APP_VERSION = "1.21.3"  # Tu meníme verziu pre celú aplikáciu

class LicenseManager:
    def __init__(self):
        # Zmeníme umiestnenie konfiguračného súboru do skrytého systémového priečinka
        if platform.system() == 'Windows':
            self.config_file = Path(os.getenv('APPDATA')) / 'VideoScheduler' / '.config'
        else:  # Linux/Mac
            self.config_file = Path.home() / '.config' / 'videoschedule' / '.config'
            
        self.trial_days = 7
        self.secret_key = "0fc081be3aaaa55bec5e2098eb7cc8ec"
        
    def get_license_info(self):
        if not self.config_file.exists():
            # Vytvoríme priečinok ak neexistuje
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Prvé spustenie - začiatok trial verzie
            info = {
                'first_run': datetime.now().isoformat(),
                'license_key': '',
                'email': '',
                # Pridáme kontrolný hash
                'checksum': ''
            }
            info['checksum'] = self._calculate_checksum(info)
            self.save_license_info(info)
            return info
        
        return self._verify_and_load_config()
    
    def _calculate_checksum(self, info):
        # Vytvoríme kópiu info bez existujúceho checksumu
        info_copy = info.copy()
        info_copy.pop('checksum', None)  # Odstránime existujúci checksum ak existuje
        
        # Vytvoríme hash z dát a tajného kľúča
        data = f"{info_copy['first_run']}{info_copy['license_key']}{info_copy['email']}{self.secret_key}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _verify_and_load_config(self):
        try:
            with open(self.config_file, 'rb') as f:
                info = json.load(f)
            
            # Overíme checksum
            original_checksum = info.pop('checksum', '')
            calculated_checksum = self._calculate_checksum(info)
            
            if original_checksum != calculated_checksum:
                # Detegovaná manipulácia - zablokujeme aplikáciu
                self.logger.error("Detekovaná manipulácia s konfiguračným súborom - aplikácia zablokovaná")
                QMessageBox.critical(None, 'Kritická chyba', 
                    'Bola detegovaná neoprávnená manipulácia s licenčnými údajmi.\n'
                    'Aplikácia bude zablokovaná.\n\n'
                    'Pre odblokovanie kontaktujte podporu na support@trify.sk')
                sys.exit(1)
            
            return info
            
        except Exception as e:
            self.logger.error(f"Chyba pri načítaní konfigurácie: {str(e)}")
            QMessageBox.critical(None, 'Kritická chyba',
                'Nepodarilo sa načítať konfiguráciu.\n'
                'Pre pomoc kontaktujte podporu na support@trify.sk')
            sys.exit(1)
    
    def save_license_info(self, info):
        # Najprv vypočítame nový checksum
        info['checksum'] = self._calculate_checksum(info)
        
        # Vytvoríme priečinok ak neexistuje
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Uložíme dáta aj s checksumom
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

class PhoneHome:
    def __init__(self, license_manager, logger):
        self.endpoint = "https://trify.sk/api/plugin-stats"
        self.api_key = "0fc081be3aaaa55bec5e2098eb7cc8ec"
        self.license_manager = license_manager
        self.logger = logger
        self.version = APP_VERSION
            
    def get_status(self):
        info = self.license_manager.get_license_info()
        if info.get('license_key'):
            # Overíme či je licencia platná
            if self.license_manager.is_license_valid(info['license_key'], info['email']):
                return 'Aktivovaný'
        elif self.license_manager.is_trial_valid():
            return 'Skúšobná verzia'
        return 'Vypršaný'
        
    def send_report(self):
        try:
            data = {
                'domain': platform.node(),
                'plugin': 'video-scheduler',
                'version': self.version,
                'status': self.get_status(),  # Endpoint zobrazí presne tento text
                'license_email': self.license_manager.get_license_info().get('email', ''),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            headers = {
                'X-TRIFY-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            
            self.logger.info("Sending phone home report")
            
            response = requests.post(
                self.endpoint,
                json=data,
                headers=headers,
                timeout=5
            )
            
            self.logger.info(f"Phone home response: {response.status_code}")
            
            if response.status_code == 200:
                self.logger.info("Phone home report úspešne odoslaný")
                return True
            else:
                self.logger.error(f"Phone home error: Status code {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Phone home error: {str(e)}")
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
        self.video1_position = 0  # Pridáme premennú pre pozíciu Video 1
        
        self.phone_home = PhoneHome(self.license_manager, self.logger)
        # Odošleme report pri štarte aplikácie
        self.phone_home.send_report()
        
        # Nastavíme pravidelné odosielanie reportu (každých 24 hodín)
        self.phone_home_timer = QTimer()
        self.phone_home_timer.timeout.connect(self.phone_home.send_report)
        self.phone_home_timer.start(24 * 60 * 60 * 1000)  # 24 hodín v milisekundách
        
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
        
        # Upravíme layout pre zoznam časov a informácie o Video 2
        times_layout = QHBoxLayout()
        
        # Ľavá strana - zoznam časov
        times_left = QVBoxLayout()
        times_left.addWidget(QLabel('Naplánované časy:'))
        times_left.addWidget(self.time_list)
        times_layout.addLayout(times_left)
        
        # Pravá strana - informácie o Video 2
        times_right = QVBoxLayout()
        times_right.addWidget(QLabel('Informácie o Video 2:'))
        self.video2_info_label = QLabel('Čaká sa na spustenie Video 2...')
        times_right.addWidget(self.video2_info_label)
        times_layout.addLayout(times_right)
        
        # Pridanie všetkých komponentov do hlavného layoutu
        layout.addLayout(video1_group)
        layout.addLayout(video2_group)
        layout.addLayout(time_layout)
        layout.addLayout(times_layout)
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
                
                # Zistíme informácie o Video 2 hneď po jeho výbere
                try:
                    # Vytvoríme dočasné VLC media pre získanie informácií
                    media = self.instance.media_new(filename)
                    media.parse()
                    duration_ms = media.get_duration()
                    duration_sec = duration_ms / 1000
                    
                    # Vypočítame čas ukončenia pre aktuálny čas
                    end_time = (datetime.now() + timedelta(seconds=duration_sec)).strftime("%H:%M:%S")
                    
                    # Aktualizujeme informácie v UI
                    self.video2_info_label.setText(
                        f'Video 2 - Dĺžka: {int(duration_sec/60)}:{int(duration_sec%60):02d}\n'
                        f'Predpokladaný čas ukončenia: {end_time}\n'
                        f'(pri okamžitom spustení)'
                    )
                    
                    self.logger.info(f"Video 2 informácie - Dĺžka: {duration_sec} sekúnd")
                except Exception as e:
                    self.logger.error(f"Chyba pri získavaní informácií o Video 2: {str(e)}")
                    self.video2_info_label.setText('Nepodarilo sa získať informácie o Video 2')
    
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
    
    def play_video1(self, resume=True):
        try:
            self.logger.info("Spúšťam Video 1: %s", self.video1_path)
            media = self.instance.media_new(self.video1_path)
            self.player.set_media(media)
            
            # Ak máme pokračovať z uloženej pozície
            if resume and self.video1_position > 0:
                saved_position = self.video1_position
                self.logger.info(f"Plánujem nastaviť Video 1 na pozíciu: {saved_position}")
                
                def set_position():
                    self.logger.info(f"Nastavujem Video 1 na pozíciu: {saved_position}")
                    self.player.set_position(saved_position)
                    # Resetujeme pozíciu až po úspešnom nastavení
                    self.video1_position = 0
                
                # Počkáme dlhšie, aby sa video určite načítalo
                QTimer.singleShot(200, set_position)
            
            self.player.play()
            self.current_video = 1
            
            # Definujeme callback funkciu pre koniec videa
            def replay(event):
                self.logger.info("Video 1 skončilo, prehrávam znova")
                if self.current_video == 1:
                    self.player.set_position(0)
                    self.player.play()
            
            # Správne pripojenie event handlera
            event_manager = media.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, replay)
            
        except Exception as e:
            self.logger.error("Chyba pri prehrávaní Video 1: %s", str(e))
            QMessageBox.critical(self, 'Chyba',
                               f'Nepodarilo sa prehrať Video 1:\n{str(e)}')
    
    def play_video2(self):
        try:
            self.logger.info("Spúšťam Video 2: %s", self.video2_path)
            media = self.instance.media_new(self.video2_path)
            self.player.set_media(media)
            
            # Získame dĺžku videa v milisekundách
            media.parse()
            duration_ms = media.get_duration()
            duration_sec = duration_ms / 1000
            self.logger.info(f"Dĺžka Video 2: {duration_sec} sekúnd")
            
            # Aktualizujeme informácie v UI hneď po načítaní
            self.video2_info_label.setText(
                f'Video 2 - Dĺžka: {int(duration_sec/60)}:{int(duration_sec%60):02d}\n'
                f'Končí v: {(datetime.now() + timedelta(seconds=duration_sec)).strftime("%H:%M:%S")}'
            )
            
            self.player.play()
            self.current_video = 2
            
            # Nastavíme časovač na prepnutie späť na Video 1
            QTimer.singleShot(int(duration_ms), lambda: self.play_video1(resume=True))
            
        except Exception as e:
            self.logger.error("Chyba pri prehrávaní Video 2: %s", str(e))
            QMessageBox.critical(self, 'Chyba',
                               f'Nepodarilo sa prehrať Video 2:\n{str(e)}')
    
    def check_schedule(self):
        current_time = datetime.now().strftime("%H:%M")
        if (current_time in self.scheduled_times and 
            self.video2_path and 
            self.current_video == 1):
            # Uložíme si pozíciu Video 1 pred prepnutím
            self.video1_position = self.player.get_position()
            self.logger.info(f"Ukladám pozíciu Video 1: {self.video1_position}")
            self.play_video2()
    
    def check_license(self):
        info = self.license_manager.get_license_info()
        
        # Ak už máme platnú licenciu, vrátime True bez zobrazenia dialógu
        if info['license_key']:
            if self.license_manager.is_license_valid(info['license_key'], info['email']):
                return True
        
        # Ak je trial stále platný, zobrazíme len informáciu
        if self.license_manager.is_trial_valid():
            days_left = 7 - (datetime.now() - datetime.fromisoformat(info['first_run'])).days
            QMessageBox.information(self, 'Skúšobná verzia', 
                                  f'Používate skúšobnú verziu. Zostáva {days_left} dní.')
            return True
        
        # Ak nemáme licenciu ani platný trial, zobrazíme aktivačný dialóg
        return self.show_activation_dialog()
    
    def show_activation_dialog(self):
        # Najprv skontrolujeme, či už nie je aktivovaný
        info = self.license_manager.get_license_info()
        if info['license_key'] and self.license_manager.is_license_valid(info['license_key'], info['email']):
            QMessageBox.information(self, 'Informácia', 
                                  'Produkt je už aktivovaný.')
            return True

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Skúšobná doba vypršala. Chcete aktivovať softvér?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if msg.exec_() == QMessageBox.Yes:
            while True:
                email, ok = QInputDialog.getText(self, 'Aktivácia', 
                                               'Zadajte sériové číslo:', QLineEdit.Normal)
                if not ok:
                    return False
                    
                if not email:
                    QMessageBox.warning(self, 'Upozornenie', 
                                      'Sériové číslo nemôže byť prázdne!')
                    continue
                    
                license_key, ok = QInputDialog.getText(self, 'Aktivácia', 
                                                     'Zadajte licenčný kľúč:', QLineEdit.Normal)
                if not ok:
                    return False
                    
                if not license_key:
                    QMessageBox.warning(self, 'Upozornenie', 
                                      'Licenčný kľúč nemôže byť prázdny!')
                    continue
                    
                if self.license_manager.activate_license(license_key, email):
                    QMessageBox.information(self, 'Úspech', 
                                          'Softvér bol úspešne aktivovaný!')
                    return True  # Vrátime True, ale neukončíme program
                else:
                    QMessageBox.critical(self, 'Chyba', 
                                       'Neplatný licenčný kľúč!')
                    continue  # Dáme možnosť skúsiť znova
        
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
        try:
            # Nastavenie cesty k logom pre Windows
            if platform.system() == 'Windows':
                # Použijeme priečinok Dokumenty
                documents_path = Path(os.path.expanduser("~/Documents"))
                log_dir = documents_path / 'VideoScheduler' / 'logs'
            else:  # Linux/Mac
                log_dir = Path('/var/log/videoschedule')
            
            # Pokus o vytvorenie priečinkov
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                print(f"Priečinok pre logy vytvorený: {log_dir}")  # Dočasný print pre debug
            except Exception as e:
                print(f"Chyba pri vytváraní priečinka: {str(e)}")  # Dočasný print pre debug
                # Fallback na AppData ak Documents zlyhá
                log_dir = Path(os.getenv('APPDATA')) / 'VideoScheduler' / 'logs'
                log_dir.mkdir(parents=True, exist_ok=True)
                
            # Vytvorenie log súboru
            log_file = log_dir / f"videoschedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            
            # Nastavenie logovania
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
            self.logger.info(f"Logy sa ukladajú do: {log_dir}")
            
        except Exception as e:
            print(f"Kritická chyba pri nastavovaní logovania: {str(e)}")
            # Fallback na základné logovanie do konzoly
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[logging.StreamHandler()]
            )
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"Nepodarilo sa nastaviť logovanie do súboru: {str(e)}")

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
                              f'Seriové číslo: {info["email"] if info["email"] else "Neregistrované"}\n\n'
                              f'👨‍💻 Kódované s vášňou a kreativitou od Erika\n\n'
                              f'Verzia: {APP_VERSION}\n'
                              f'Author: Erik Fedor - TRIFY s.r.o.\n'
                              f'Copyright: © 2025 TRIFY s.r.o.\n'  
                              f'Všetky práva vyhradené.')

    def show_license_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Aktivácia licencie')
        layout = QVBoxLayout()

        # Informácie o trial verzii
        trial_info = QLabel('Používate skúšobnú verziu programu.')
        layout.addWidget(trial_info)

        # Input pre sériové číslo
        email_label = QLabel('Sériové číslo:')
        email_input = QLineEdit()
        layout.addWidget(email_label)
        layout.addWidget(email_input)

        # Input pre licenčný kľúč
        key_label = QLabel('Licenčný kľúč:')
        key_input = QLineEdit()
        layout.addWidget(key_label)
        layout.addWidget(key_input)

        # Tlačidlá
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoScheduler()
    window.show()
    sys.exit(app.exec_())
    