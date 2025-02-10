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
from PyQt5.QtGui import QIcon
import subprocess

# Na začiatku súboru pridáme konštantu pre verziu
APP_VERSION = "1.22.12.0"  # Tu meníme verziu pre celú aplikáciu

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
        
        # Nastavíme ikonu aplikácie čo najskôr
        self.setup_application_icon()
        
        self.license_manager = LicenseManager()
        
        # Nastavíme ikonu aplikácie
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            # Nastavíme ikonu aj pre celú aplikáciu
            QApplication.setWindowIcon(QIcon(icon_path))
            self.logger.info(f"Ikona aplikácie nastavená z: {icon_path}")
        else:
            self.logger.warning(f"Súbor s ikonou nebol nájdený na: {icon_path}")
        
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
        
        # Odstránime všetky referencie na video_widget
        self.current_video = None
        self.video1_path = ""
        self.video2_path = ""
        self.scheduled_times = []
        self.video1_position = 0
        self.video2_scheduled = False
        self.video2_timer = QTimer()
        self.video2_timer.timeout.connect(self.check_schedule)
        self.video2_timer.start(1000)  # kontrola každú sekundu
        self.last_schedule_check = None  # pridáme sledovanie poslednej kontroly
        
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
        
        self.setWindowIcon(QIcon('icon.ico'))  # Pridajte ikonu do rovnakého priečinka ako .py súbor
        
        # Pridáme sledovanie celkovej dĺžky videa
        self.video1_duration = 0
        
        # Pridáme timer pre kontrolu konca videa
        self.video1_check_timer = QTimer()
        self.video1_check_timer.timeout.connect(self.check_video1_end)
        
        # Pridáme handler pre zatvorenie aplikácie
        self.app = QApplication.instance()
        self.app.aboutToQuit.connect(self.on_close)
        
    def setup_application_icon(self):
        """Nastaví ikonu aplikácie"""
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
            if os.path.exists(icon_path):
                app_icon = QIcon(icon_path)
                self.setWindowIcon(app_icon)
                QApplication.setWindowIcon(app_icon)
                self.logger.info(f"Ikona aplikácie nastavená z: {icon_path}")
            else:
                self.logger.error(f"Súbor s ikonou nebol nájdený: {icon_path}")
        except Exception as e:
            self.logger.error(f"Chyba pri nastavovaní ikony: {str(e)}")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Odstránime video widget z layoutu
        # Video 1 sekcia
        video1_group = QVBoxLayout()
        video1_header = QHBoxLayout()
        
        self.video1_label = QLabel('Video 1: Nevybrané (slučka)')
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
        
    def calculate_end_times(self):
        try:
            if not self.video2_path:
                return ""
                
            # Vytvoríme dočasné VLC media pre získanie informácií
            media = self.instance.media_new(self.video2_path)
            media.parse()
            duration_ms = media.get_duration()
            duration_sec = duration_ms / 1000
            
            # Vytvoríme text s časmi ukončenia pre každé plánované spustenie
            end_times_text = "Video 2 - Dĺžka: "
            end_times_text += f"{int(duration_sec/60)}:{int(duration_sec%60):02d}\n\n"
            end_times_text += "Plánované ukončenia:\n"
            
            for scheduled_time in sorted(self.scheduled_times):
                # Prevedieme čas na datetime
                today = datetime.now().date()
                start_time = datetime.strptime(f"{today} {scheduled_time}", "%Y-%m-%d %H:%M")
                end_time = start_time + timedelta(seconds=duration_sec)
                
                end_times_text += f"Spustenie {scheduled_time} -> Koniec {end_time.strftime('%H:%M:%S')}\n"
            
            return end_times_text
            
        except Exception as e:
            self.logger.error(f"Chyba pri výpočte časov ukončenia: {str(e)}")
            return "Nepodarilo sa vypočítať časy ukončenia"

    def select_video(self, video_num):
        filename, _ = QFileDialog.getOpenFileName(
            self, f'Select Video {video_num}',
            '', 'Video Files (*.mp4 *.avi *.mkv);;All Files (*.*)'
        )
        if filename:
            if video_num == 1:
                self.video1_path = filename
                self.video1_label.setText(f'Video 1: {filename} (slučka)')  # Pridáme (slučka) do textu
            else:
                self.video2_path = filename
                self.video2_label.setText(f'Video 2: {filename}')
                # Aktualizujeme informácie o Video 2
                self.video2_info_label.setText(self.calculate_end_times())
    
    def add_scheduled_time(self):
        time = self.time_edit.time().toString("HH:mm")
        if time not in [self.time_list.item(i).text() for i in range(self.time_list.count())]:
            self.time_list.addItem(time)
            self.scheduled_times.append(time)
            self.scheduled_times.sort()
            # Aktualizujeme informácie o časoch ukončenia
            if self.video2_path:
                self.video2_info_label.setText(self.calculate_end_times())
    
    def remove_scheduled_time(self):
        current_item = self.time_list.currentItem()
        if current_item:
            time = current_item.text()
            self.scheduled_times.remove(time)
            self.time_list.takeItem(self.time_list.row(current_item))
            # Aktualizujeme informácie o časoch ukončenia
            if self.video2_path:
                self.video2_info_label.setText(self.calculate_end_times())
    
    def start_playback(self):
        if self.video1_path:
            self.logger.info("Používateľ stlačil tlačidlo ŠTART")
            self.play_video1()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
    
    def stop_playback(self):
        self.logger.info("Používateľ stlačil tlačidlo STOP")
        self.player.stop()
        self.video1_check_timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def on_close(self):
        self.logger.info("Aplikácia sa vypína")
        self.player.stop()
        self.video1_check_timer.stop()
    
    def play_video1(self, resume=True):
        try:
            self.logger.info("="*50)
            self.logger.info("Začiatok sekvencie play_video1")
            self.logger.info(f"Parametre: resume={resume}, video1_position={self.video1_position}")
            self.logger.info(f"Cesta k videu: {self.video1_path}")
            
            if not os.path.exists(self.video1_path):
                self.logger.error(f"Video súbor neexistuje: {self.video1_path}")
                raise FileNotFoundError(f"Video súbor neexistuje: {self.video1_path}")
            
            media = self.instance.media_new(self.video1_path)
            media.parse()
            self.player.set_media(media)
            
            # Uložíme si dĺžku videa
            self.video1_duration = media.get_duration()
            duration_sec = self.video1_duration / 1000
            self.logger.info(f"Dĺžka Video 1: {duration_sec} sekúnd")
            
            # Ak máme pokračovať z uloženej pozície
            if resume and self.video1_position > 0:
                saved_position = self.video1_position
                self.logger.info(f"Nastavujem Video 1 na pozíciu: {saved_position} ({saved_position*100:.2f}%)")
                self.player.set_position(saved_position)
                self.video1_position = 0
            
            # VLC samo vytvorí svoje okno
            self.player.play()
            self.current_video = 1
            
            # Spustíme kontrolný timer
            self.video1_check_timer.start(50)  # kontrola každých 50ms
            
            # Odstránime starý event handler
            # event_manager = self.player.event_manager()
            # event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, replay)
            self.logger.info("Event handler pre koniec videa pripojený")
            self.logger.info("="*50)
            
        except Exception as e:
            self.logger.error("!!!"*20)
            self.logger.error(f"Kritická chyba v play_video1: {str(e)}", exc_info=True)
            self.logger.error("!!!"*20)
            QMessageBox.critical(self, 'Chyba',
                               f'Nepodarilo sa prehrať Video 1:\n{str(e)}')

    def check_video1_end(self):
        """Kontroluje či video1 dosiahlo koniec a reštartuje ho"""
        try:
            if self.current_video != 1 or not self.player.is_playing():
                return
                
            current_time = self.player.get_time()
            if current_time < 0:  # VLC môže vrátiť -1 pri chybe
                return
                
            # Pridáme debug log
            self.logger.debug(f"Video1 pozícia: {current_time}/{self.video1_duration} ms")
            
            # Kontrola či sme blízko konca (posledných 500ms)
            if self.video1_duration - current_time <= 500:
                self.logger.info(f"Video 1 sa blíži ku koncu (time={current_time}ms, duration={self.video1_duration}ms)")
                
                # Vytvoríme nové media pre čisté prehratie
                media = self.instance.media_new(self.video1_path)
                media.parse()
                self.player.set_media(media)
                self.player.set_position(0.0)
                self.player.play()
                
                self.logger.info("Video 1 reštartované od začiatku")
                
                # Kontrola či sa video skutočne spustilo
                QTimer.singleShot(100, self._verify_video1_playing)
                
        except Exception as e:
            self.logger.error(f"Chyba pri kontrole konca videa: {str(e)}", exc_info=True)

    def _verify_video1_playing(self):
        """Overí či sa Video 1 skutočne prehráva"""
        try:
            if not self.player.is_playing():
                self.logger.warning("Video 1 sa nezačalo prehrávať po reštarte!")
                self.player.play()
            else:
                current_pos = self.player.get_position()
                current_time = self.player.get_time()
                self.logger.info(f"Video 1 sa prehráva: pos={current_pos:.4f}, time={current_time}ms")
        except Exception as e:
            self.logger.error(f"Chyba pri verifikácii prehrávania: {str(e)}")

    def _restart_video1_internal(self):
        """Interná metóda pre reštart Video 1"""
        try:
            self.logger.info("-"*30)
            self.logger.info("Začiatok reštartu Video 1")
            
            # Zaznamenáme stav pred reštartom
            was_playing = self.player.is_playing()
            current_pos = self.player.get_position()
            self.logger.info(f"Stav pred reštartom: playing={was_playing}, position={current_pos}")
            
            self.player.stop()
            self.player.set_position(0.0)
            self.player.play()
            
            # Overíme stav po reštarte
            QTimer.singleShot(100, lambda: self._verify_video1_restart())
            
        except Exception as e:
            self.logger.error(f"Chyba pri reštarte Video 1: {str(e)}", exc_info=True)

    def _verify_video1_restart(self):
        """Kontrola správneho reštartu Video 1"""
        try:
            is_playing = self.player.is_playing()
            current_pos = self.player.get_position()
            self.logger.info(f"Kontrola po reštarte: playing={is_playing}, position={current_pos}")
            
            if not is_playing:
                self.logger.warning("Video 1 sa nezačalo prehrávať po reštarte!")
                self.player.play()
            elif current_pos > 0.01:
                self.logger.warning(f"Video 1 nezačalo od začiatku! Pozícia: {current_pos}")
                self.player.set_position(0.0)
                
            self.logger.info("Reštart Video 1 dokončený")
            self.logger.info("-"*30)
            
        except Exception as e:
            self.logger.error(f"Chyba pri verifikácii reštartu: {str(e)}", exc_info=True)

    def restart_video1(self):
        """Metóda pre reštart Video 1 od začiatku"""
        try:
            self.logger.info("Reštartujem Video 1 od začiatku")
            self.player.stop()
            self.player.set_position(0.0)
            self.player.play()
        except Exception as e:
            self.logger.error(f"Chyba pri reštarte Video 1: {str(e)}")

    def play_video2(self):
        try:
            # Uložíme pozíciu Video 1 pred prepnutím
            self.video1_position = self.player.get_position()
            self.logger.info(f"Ukladám pozíciu Video 1: {self.video1_position}")
            
            # Vytvoríme a analyzujeme Video 2
            media = self.instance.media_new(self.video2_path)
            media.parse()
            
            # Explicitne zastavíme Video 1
            self.player.stop()
            
            # Nastavíme a spustíme Video 2
            self.player.set_media(media)
            self.player.set_position(0.0)  # Explicitne nastavíme na začiatok
            self.player.play()
            self.current_video = 2
            
            # Vypneme kontrolný timer počas Video 2
            self.video1_check_timer.stop()
            
            # Vypočítame presné časy pre logovanie a informačný panel
            start_time = datetime.now()
            duration_ms = media.get_duration()
            duration_sec = duration_ms / 1000
            end_time = start_time + timedelta(seconds=duration_sec)
            
            self.logger.info(f"Video 2 začiatok: {start_time.strftime('%H:%M:%S')}")
            self.logger.info(f"Video 2 koniec (plánovaný): {end_time.strftime('%H:%M:%S')}")
            
            # Aktualizujeme informačný panel
            self.video2_info_label.setText(self.calculate_end_times())
            
            # Nastavíme časovač pre návrat na Video 1
            QTimer.singleShot(int(duration_sec * 1000), self.resume_video1)
            
        except Exception as e:
            self.logger.error(f"Chyba pri spúšťaní Video 2: {str(e)}")

    def resume_video1(self):
        try:
            self.logger.info(f"Plánovaný návrat na Video 1 v čase: {datetime.now().strftime('%H:%M:%S')}")
            
            # Explicitne zastavíme Video 2
            self.player.stop()
            
            # Pripravíme Video 1
            media = self.instance.media_new(self.video1_path)
            self.player.set_media(media)
            media.parse()
            
            # Nastavíme uloženú pozíciu
            self.logger.info(f"Nastavujem Video 1 na pozíciu: {self.video1_position}")
            self.player.set_position(self.video1_position)
            
            # Spustíme prehrávanie
            self.player.play()
            self.current_video = 1
            
            # Spustíme kontrolný timer
            self.video1_check_timer.start(100)
            
            # Zachováme informačný panel
            self.video2_info_label.setText(self.calculate_end_times())
            
        except Exception as e:
            self.logger.error(f"Chyba pri návrate na Video 1: {str(e)}")
    
    def check_schedule(self):
        try:
            current_time = datetime.now().strftime("%H:%M")
            
            if self.last_schedule_check == current_time:
                return
                
            self.last_schedule_check = current_time
            self.logger.debug(f"Kontrola časov: current={current_time}, scheduled={self.scheduled_times}")
            
            if self.player.is_playing():
                is_playing = True
                current_pos = self.player.get_position()
                current_time_ms = self.player.get_time()
                self.logger.info(f"Stav prehrávania: position={current_pos:.4f}, time={current_time_ms}ms")
            else:
                is_playing = False
                self.logger.warning("Video nie je momentálne prehrávané!")
            
            if is_playing and current_time in self.scheduled_times:
                self.video1_position = self.player.get_position()
                self.logger.info("="*40)
                self.logger.info(f"Našiel sa naplánovaný čas: {current_time}")
                self.logger.info(f"Aktuálna pozícia Video 1: {self.video1_position:.4f}")
                
                if self.video2_path and self.current_video == 1:
                    self.start_video2_sequence()
                    
        except Exception as e:
            self.logger.error(f"Chyba v check_schedule: {str(e)}", exc_info=True)
    
    def start_video2_sequence(self):
        """Spustí sekvenciu Video 2"""
        try:
            # Uložíme pozíciu Video 1 pred prepnutím
            self.video1_position = self.player.get_position()
            self.logger.info(f"Ukladám pozíciu Video 1: {self.video1_position}")
            
            # Pripravíme a analyzujeme Video 2
            media = self.instance.media_new(self.video2_path)
            media.parse()
            duration_ms = media.get_duration()
            duration_sec = duration_ms / 1000
            
            # Vypočítame presné časy
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=duration_sec)
            
            self.logger.info(f"Spúšťam Video 2: {self.video2_path}")
            self.logger.info(f"Video 2 začiatok: {start_time.strftime('%H:%M:%S')}")
            self.logger.info(f"Video 2 koniec (plánovaný): {end_time.strftime('%H:%M:%S')}")
            self.logger.info(f"Video 1 bude pokračovať od pozície: {self.video1_position}")
            
            # Zastavíme aktuálne prehrávanie
            self.player.stop()
            
            # Spustíme Video 2
            self.player.set_media(media)
            self.player.play()
            self.current_video = 2
            
            # Vypneme kontrolný timer počas Video 2
            self.video1_check_timer.stop()
            
            # Naplánujeme návrat na Video 1
            resume_time = int(duration_sec * 1000)
            self.logger.info(f"Plánovanie návratu na Video 1 za {resume_time}ms")
            QTimer.singleShot(resume_time, self.start_video1_sequence)
            
        except Exception as e:
            self.logger.error(f"Chyba pri spúšťaní Video 2: {str(e)}")
    
    def start_video1_sequence(self):
        """Spustí sekvenciu návratu na Video 1"""
        try:
            self.logger.info(f"Plánovaný návrat na Video 1 v čase: {datetime.now().strftime('%H:%M:%S')}")
            self.logger.info(f"Nastavujem Video 1 na pozíciu: {self.video1_position}")
            
            # Zastavíme aktuálne prehrávanie
            self.player.stop()
            
            # Pripravíme Video 1
            media = self.instance.media_new(self.video1_path)
            self.player.set_media(media)
            media.parse()
            
            # Nastavíme pozíciu
            saved_position = self.video1_position
            self.player.set_position(saved_position)
            
            # Spustíme prehrávanie
            self.player.play()
            self.current_video = 1
            
            self.logger.info("Video 1 úspešne obnovené a spustené")
            
            # Spustíme kontrolný timer
            self.video1_check_timer.start(100)
            
            # Kontrola pozície po spustení
            def verify_position():
                current_pos = self.player.get_position()
                self.logger.info(f"Kontrola pozície Video 1: aktuálna={current_pos}, očakávaná={saved_position}")
                if abs(current_pos - saved_position) > 0.01:
                    self.logger.info(f"Opravujem pozíciu Video 1 na: {saved_position}")
                    self.player.set_position(saved_position)
            
            QTimer.singleShot(200, verify_position)
            
        except Exception as e:
            self.logger.error(f"Chyba pri návrate na Video 1: {str(e)}")
    
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
            if platform.system() == 'Windows':
                documents_path = Path(os.path.expanduser("~/Documents"))
                log_dir = documents_path / 'VideoScheduler' / 'logs'
            else:
                log_dir = Path('/var/log/videoschedule')
            
            # Vytvoríme priečinok pre logy
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Vytvoríme log súbor s aktuálnym časom
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = log_dir / f"videoschedule_{timestamp}.log"
            
            # Vytvoríme handler pre súbor
            file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # Vytvoríme handler pre konzolu
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Vytvoríme formátovač
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # Vytvoríme logger
            self.logger = logging.getLogger('VideoScheduler')
            self.logger.setLevel(logging.INFO)
            
            # Odstránime existujúce handlery ak existujú
            self.logger.handlers.clear()
            
            # Pridáme handlery do loggera
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            
            # Vypneme propagáciu do root loggera
            self.logger.propagate = False
            
            # Test logovania
            self.logger.info("="*50)
            self.logger.info("Logovanie inicializované")
            self.logger.info(f"Logy sa ukladajú do: {log_file}")
            
        except Exception as e:
            print(f"Kritická chyba pri nastavovaní logovania: {str(e)}")
            # Fallback na základné konsolové logovanie
            self.logger = logging.getLogger('VideoScheduler')
            self.logger.addHandler(logging.StreamHandler())
            self.logger.setLevel(logging.INFO)

    def setup_menu(self):
        menubar = self.menuBar()
        help_menu = menubar.addMenu('Pomoc')
        
        # Aktivačná akcia
        activate_action = QAction('Aktivovať produkt', self)
        activate_action.triggered.connect(self.show_activation_dialog)
        help_menu.addAction(activate_action)
        
        # Pridáme položku Logy
        logs_action = QAction('Logy', self)
        logs_action.triggered.connect(self.open_logs_folder)
        help_menu.addAction(logs_action)
        
        # O programe
        about_action = QAction('O programe', self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def open_logs_folder(self):
        """Otvorí priečinok s logmi"""
        try:
            if platform.system() == 'Windows':
                log_path = Path(os.path.expanduser("~/Documents/VideoScheduler/logs"))
                if not log_path.exists():
                    log_path = Path(os.getenv('APPDATA')) / 'VideoScheduler' / 'logs'
                
                if log_path.exists():
                    subprocess.run(['explorer', str(log_path)])
                else:
                    QMessageBox.warning(self, 'Upozornenie', 
                                      'Priečinok s logmi zatiaľ neexistuje.')
            else:
                # Pre Linux/Mac
                log_path = Path('/var/log/videoschedule')
                if log_path.exists():  # Oprava: exists() -> exists
                    subprocess.run(['xdg-open', str(log_path)])  # Linux
                else:
                    QMessageBox.warning(self, 'Upozornenie', 
                                      'Priečinok s logmi zatiaľ neexistuje.')
        except Exception as e:
            self.logger.error(f"Chyba pri otváraní priečinka s logmi: {str(e)}")
            QMessageBox.critical(self, 'Chyba',
                               'Nepodarilo sa otvoriť priečinok s logmi.')

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
    
    # Nastavíme ikonu pre celú aplikáciu
    try:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception as e:
        print(f"Chyba pri nastavovaní ikony aplikácie: {str(e)}")
    
    window = VideoScheduler()
    window.show()
    sys.exit(app.exec_())
