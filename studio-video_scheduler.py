import sys
import vlc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QWidget, 
                            QVBoxLayout, QHBoxLayout, QFileDialog, QLabel, 
                            QTimeEdit, QCheckBox, QListWidget)
from PyQt5.QtCore import QTime, QTimer
from datetime import datetime

class VideoScheduler(QMainWindow):
    def __init__(self):
        super().__init__()
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
        
        self.video1_label = QLabel('Video 1 (loop): Not selected')
        self.video1_btn = QPushButton('Select Video 1')
        self.video1_btn.clicked.connect(lambda: self.select_video(1))
        
        video1_header.addWidget(self.video1_label)
        video1_header.addWidget(self.video1_btn)
        video1_group.addLayout(video1_header)
        
        # Video 2 sekcia
        video2_group = QVBoxLayout()
        video2_header = QHBoxLayout()
        
        self.video2_label = QLabel('Video 2: Not selected')
        self.video2_btn = QPushButton('Select Video 2')
        self.video2_btn.clicked.connect(lambda: self.select_video(2))
        
        video2_header.addWidget(self.video2_label)
        video2_header.addWidget(self.video2_btn)
        video2_group.addLayout(video2_header)
        
        # Časový výber
        time_layout = QHBoxLayout()
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        add_time_btn = QPushButton('Add Time')
        add_time_btn.clicked.connect(self.add_scheduled_time)
        
        time_layout.addWidget(QLabel('Add schedule time:'))
        time_layout.addWidget(self.time_edit)
        time_layout.addWidget(add_time_btn)
        
        # Seznam naplánovaných časov
        self.time_list = QListWidget()
        remove_time_btn = QPushButton('Remove Selected Time')
        remove_time_btn.clicked.connect(self.remove_scheduled_time)
        
        # Ovládacie tlačidlá
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton('Start')
        self.start_btn.clicked.connect(self.start_playback)
        self.stop_btn = QPushButton('Stop')
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
        media = self.instance.media_new(self.video1_path)
        self.player.set_media(media)
        self.player.play()
        self.current_video = 1
        
        # Nastavenie opakovania
        @media.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached)
        def replay(event):
            if self.current_video == 1:
                self.player.set_position(0)
                self.player.play()
    
    def play_video2(self):
        self.current_video = 2
        media = self.instance.media_new(self.video2_path)
        self.player.set_media(media)
        self.player.play()
        
        # Po skončení video2 sa vrátime k video1
        @media.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached)
        def back_to_video1(event):
            self.play_video1()
    
    def check_schedule(self):
        current_time = datetime.now().strftime("%H:%M")
        if (current_time in self.scheduled_times and 
            self.video2_path and 
            self.current_video == 1):
            self.play_video2()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoScheduler()
    window.show()
    sys.exit(app.exec_())