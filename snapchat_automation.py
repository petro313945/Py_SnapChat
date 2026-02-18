import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time

class ChromeSession:
    def __init__(self, session_id, user_data_dir, friends_list, status_callback):
        self.session_id = session_id
        self.user_data_dir = user_data_dir
        self.friends_list = friends_list
        self.status_callback = status_callback
        self.driver = None
        self.is_running = False
        self.thread = None
        self.sent_count = 0
        
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run_automation, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            
    def _run_automation(self):
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument(f'--user-data-dir={self.user_data_dir}')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Launch Chrome
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
            except WebDriverException as e:
                self.status_callback(self.session_id, f"Session {self.session_id}: ChromeDriver error - {str(e)}")
                self.status_callback(self.session_id, f"Session {self.session_id}: Make sure Chrome is installed and ChromeDriver is available")
                self.is_running = False
                return
                
            self.driver.get('https://www.snapchat.com')
            
            # Wait for login (user must login manually)
            self.status_callback(self.session_id, f"Session {self.session_id}: Waiting for login...")
            
            # Wait until logged in (check for camera button or similar)
            wait = WebDriverWait(self.driver, 300)  # 5 min timeout for manual login
            try:
                # Wait for camera button or main interface
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'button.FBYjn.gK0xL.W5dIq, button.fE2D5')))
                self.status_callback(self.session_id, f"Session {self.session_id}: Logged in, waiting 2 minutes for friends to load...")
            except TimeoutException:
                self.status_callback(self.session_id, f"Session {self.session_id}: Login timeout")
                self.is_running = False
                return
                
            # Wait 2 minutes for friends to load
            time.sleep(120)
            self.status_callback(self.session_id, f"Session {self.session_id}: Starting automation...")
                
            # Start photo sending loop
            while self.is_running:
                try:
                    result = self._send_photo_round()
                    if result['success']:
                        self.sent_count += result.get('sent_count', 0)
                        self.status_callback(self.session_id, f"Session {self.session_id}: Sent {result.get('sent_count', 0)} photos. Total: {self.sent_count}")
                        # Minimal delay before next round (optimized for speed)
                        time.sleep(0.1)
                    else:
                        time.sleep(0.5)  # Reduced error delay
                except Exception as e:
                    self.status_callback(self.session_id, f"Session {self.session_id}: Error - {str(e)}")
                    time.sleep(5)
                    
        except Exception as e:
            self.status_callback(self.session_id, f"Session {self.session_id}: Fatal error - {str(e)}")
        finally:
            self.is_running = False
            
    def _send_photo_round(self):
        """Port of the JavaScript auto-photo-send logic"""
        try:
            # Step 1: Check if already at photo preview
            photo_img = self._find_element_safe('img.VcjuA')
            skip_to_send = photo_img is not None
            
            if not skip_to_send:
                # Step 2: Open camera if not already open
                camera_modal = self._find_element_safe('div.Nuu9e')
                if not camera_modal or not self._is_visible(camera_modal):
                    # Click open camera button
                    open_camera_btn = self._find_element_with_retry('button.FBYjn.gK0xL.W5dIq', max_retries=4)
                    if not open_camera_btn:
                        return {'success': False, 'error': 'Open camera button not found'}
                    open_camera_btn.click()
                    time.sleep(0.01)
                    
                    # Wait for camera modal
                    camera_modal = self._find_element_with_retry('div.Nuu9e', max_retries=4)
                    if not camera_modal:
                        return {'success': False, 'error': 'Camera modal did not appear'}
                
                # Step 3: Wait for camera to load (minimal delay)
                time.sleep(0.005)
                
                # Step 4: Click shot button
                shot_button = self._find_element_in_container(camera_modal, 'button.fE2D5')
                if not shot_button:
                    shot_button = self._find_element_in_container(camera_modal, 'button.FBYjn.gK0xL.W5dIq')
                if not shot_button:
                    shot_button = self._find_element_in_container(camera_modal, 'button.FBYjn')
                    
                if not shot_button:
                    return {'success': False, 'error': 'Shot button not found'}
                    
                shot_button.click()
                time.sleep(0.001)
                
                # Wait for photo to appear
                photo_img = self._find_element_with_retry('img.VcjuA', max_retries=3)
                if not photo_img:
                    return {'success': False, 'error': 'Photo did not appear'}
                    
                time.sleep(0.001)
            
            # Step 5: Click Send To button (minimal delay)
            time.sleep(0.001)
            send_to_btn = self._find_element_with_retry('button.YatIx.fGS78.eKaL7.Bnaur', max_retries=4)
            if not send_to_btn:
                send_to_btn = self._find_element_with_retry('button.YatIx.fGS78', max_retries=2)
            if not send_to_btn:
                send_to_btn = self._find_element_with_retry('button.YatIx', max_retries=2)
                
            if not send_to_btn:
                return {'success': False, 'error': 'Send To button not found'}
                
            send_to_btn.click()
            time.sleep(0.001)
            
            # Step 6: Wait for friend modal (optimized - start immediately)
            friend_modal = self._find_element_with_retry('form.tvul8.pebzM', max_retries=2, delay=0.001)
            if not friend_modal:
                friend_modal = self._find_element_with_retry('form.tvul8', max_retries=1, delay=0.001)
            if not friend_modal:
                friend_modal = self._find_element_with_retry('form.pebzM', max_retries=1, delay=0.001)
                
            if not friend_modal:
                return {'success': False, 'error': 'Friend modal not found'}
                
            # Step 7: Find friend list immediately (no delay - start searching right away)
            friend_list = self._find_element_in_container(friend_modal, 'ul.s7loS')
            if not friend_list:
                # Try document-wide search with minimal retries
                friend_list = self._find_element_with_retry('ul.s7loS', max_retries=2, delay=0.001)
                
            if not friend_list:
                return {'success': False, 'error': 'Friend list not found'}
                
            # Build friend map for O(1) lookup (optimized - faster element finding)
            friend_map = {}
            list_items = friend_list.find_elements(By.TAG_NAME, 'li')
            for item in list_items:
                try:
                    # Try most common selector first
                    name_div = item.find_element(By.CSS_SELECTOR, 'div.RBx9s.nonIntl')
                except:
                    try:
                        # Fallback to any RBx9s div
                        name_div = item.find_element(By.CSS_SELECTOR, 'div.RBx9s')
                    except:
                        name_div = None
                            
                if name_div and name_div.text:
                    name_key = name_div.text.strip().lower()
                    try:
                        friend_item = item.find_element(By.CSS_SELECTOR, 'div.Ewflr.cDeBk')
                    except:
                        try:
                            friend_item = item.find_element(By.CSS_SELECTOR, 'div.Ewflr')
                        except:
                            try:
                                friend_item = item.find_element(By.TAG_NAME, 'div')
                            except:
                                friend_item = item
                        
                    friend_map[name_key] = {
                        'item': friend_item,
                        'list_item': item
                    }
            
            # Select friends (optimized - skip selection check for speed, just click)
            selected_count = 0
            not_found_count = 0
            already_selected_count = 0
            
            for friend_name in self.friends_list:
                friend_key = friend_name.lower()
                friend_data = friend_map.get(friend_key)
                
                if friend_data:
                    friend_item = friend_data['item']
                    # Quick check - only verify if checkbox exists and is checked
                    try:
                        checked = friend_item.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]:checked')
                        if len(checked) > 0:
                            already_selected_count += 1
                            continue
                    except:
                        pass
                    
                    # Click immediately (Snapchat handles duplicate selection)
                    try:
                        friend_item.click()
                        selected_count += 1
                    except:
                        pass
                else:
                    not_found_count += 1
            
            # Step 8: Click Send button
            send_btn = self._find_element_in_container(friend_modal, 'button.TYX6O.eKaL7.Bnaur[type="submit"]')
            if not send_btn:
                send_btn = self._find_element_in_container(friend_modal, 'button.TYX6O.eKaL7.Bnaur')
            if not send_btn:
                send_btn = self._find_element_in_container(friend_modal, 'button.TYX6O')
                
            if not send_btn:
                return {
                    'success': False,
                    'error': 'Send button not found',
                    'selected_count': selected_count,
                    'not_found_count': not_found_count
                }
                
            send_btn.click()
            
            # Wait for modal to close
            start_time = time.time()
            modal_closed = False
            max_wait = 2.0  # 2 seconds
            
            while time.time() - start_time < max_wait:
                try:
                    if not self._is_visible(friend_modal):
                        modal_closed = True
                        break
                except:
                    modal_closed = True
                    break
                time.sleep(0.01)  # Faster polling
                
            return {
                'success': True,
                'sent_count': selected_count,
                'not_found_count': not_found_count,
                'already_selected_count': already_selected_count
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _find_element_safe(self, selector):
        try:
            return self.driver.find_element(By.CSS_SELECTOR, selector)
        except:
            return None
            
    def _find_element_with_retry(self, selector, max_retries=3, delay=0.001):
        # First try immediately (no delay)
        element = self._find_element_safe(selector)
        if element and self._is_visible(element):
            return element
        
        # Then retry with delays
        for i in range(max_retries - 1):
            time.sleep(delay)
            element = self._find_element_safe(selector)
            if element and self._is_visible(element):
                return element
        return None
        
    def _find_element_in_container(self, container, selector):
        try:
            return container.find_element(By.CSS_SELECTOR, selector)
        except:
            return None
            
    def _is_visible(self, element):
        try:
            return element.is_displayed() and element.size['width'] > 0 and element.size['height'] > 0
        except:
            return False


class SnapchatAutomationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Snapchat Automation")
        self.root.geometry("800x700")
        self.root.configure(bg='#0b0b0b')
        
        self.sessions = {}
        self.friends_list = []
        self.base_user_data_dir = os.path.join(os.getcwd(), 'chrome_profiles')
        
        # Create profiles directory
        os.makedirs(self.base_user_data_dir, exist_ok=True)
        
        self._create_gui()
        self._load_friends()
        
    def _create_gui(self):
        # Title
        title = tk.Label(self.root, text="Snapchat Automation", font=('Arial', 20, 'bold'), 
                        bg='#0b0b0b', fg='white')
        title.pack(pady=20)
        
        # Session count slider
        slider_frame = tk.Frame(self.root, bg='#0b0b0b')
        slider_frame.pack(pady=10)
        
        tk.Label(slider_frame, text="Sessions (1-10):", font=('Arial', 12), 
                bg='#0b0b0b', fg='white').pack(side=tk.LEFT, padx=10)
        
        self.session_var = tk.IntVar(value=1)
        self.session_slider = tk.Scale(slider_frame, from_=1, to=10, orient=tk.HORIZONTAL,
                                       variable=self.session_var, bg='#1a1a1a', fg='white',
                                       highlightbackground='#0b0b0b', length=200)
        self.session_slider.pack(side=tk.LEFT, padx=10)
        
        self.session_label = tk.Label(slider_frame, text="1", font=('Arial', 12),
                                      bg='#0b0b0b', fg='white', width=3)
        self.session_label.pack(side=tk.LEFT)
        self.session_slider.configure(command=lambda v: self.session_label.config(text=str(int(float(v)))))
        
        # Launch button
        self.launch_btn = tk.Button(self.root, text="Launch Sessions", font=('Arial', 14, 'bold'),
                                   bg='#31d158', fg='white', padx=20, pady=10,
                                   command=self._launch_sessions)
        self.launch_btn.pack(pady=20)
        
        # Friends panel
        friends_frame = tk.LabelFrame(self.root, text="Friends/Usernames", font=('Arial', 12),
                                     bg='#1a1a1a', fg='white', padx=10, pady=10)
        friends_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Friends input
        input_frame = tk.Frame(friends_frame, bg='#1a1a1a')
        input_frame.pack(fill=tk.X, pady=5)
        
        self.friend_entry = tk.Entry(input_frame, font=('Arial', 11), bg='#2a2a2a', fg='white',
                                    insertbackground='white')
        self.friend_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.friend_entry.bind('<Return>', lambda e: self._add_friend())
        
        add_btn = tk.Button(input_frame, text="Add", bg='#31d158', fg='white',
                           command=self._add_friend, padx=10)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        # Friends list
        self.friends_listbox = tk.Listbox(friends_frame, font=('Arial', 10), bg='#2a2a2a',
                                          fg='white', selectbackground='#31d158')
        self.friends_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Friends buttons
        friends_btn_frame = tk.Frame(friends_frame, bg='#1a1a1a')
        friends_btn_frame.pack(fill=tk.X)
        
        remove_btn = tk.Button(friends_btn_frame, text="Remove Selected", bg='#ff5f57', fg='white',
                              command=self._remove_friend)
        remove_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(friends_btn_frame, text="Clear All", bg='#ff5f57', fg='white',
                             command=self._clear_friends)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Status panel
        status_frame = tk.LabelFrame(self.root, text="Status", font=('Arial', 12),
                                     bg='#1a1a1a', fg='white', padx=10, pady=10)
        status_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=8, font=('Consolas', 9),
                                                     bg='#2a2a2a', fg='white', wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Stop button
        self.stop_btn = tk.Button(self.root, text="Stop All Sessions", font=('Arial', 12),
                                  bg='#ff5f57', fg='white', padx=15, pady=8,
                                  command=self._stop_all_sessions, state=tk.DISABLED)
        self.stop_btn.pack(pady=10)
        
    def _add_friend(self):
        friend = self.friend_entry.get().strip()
        if friend and friend not in self.friends_list:
            self.friends_list.append(friend)
            self.friends_listbox.insert(tk.END, friend)
            self.friend_entry.delete(0, tk.END)
            self._save_friends()
            
    def _remove_friend(self):
        selection = self.friends_listbox.curselection()
        if selection:
            index = selection[0]
            self.friends_listbox.delete(index)
            self.friends_list.pop(index)
            self._save_friends()
            
    def _clear_friends(self):
        self.friends_listbox.delete(0, tk.END)
        self.friends_list = []
        self._save_friends()
        
    def _save_friends(self):
        try:
            # Save to friends.txt (one friend per line)
            with open('friends.txt', 'w', encoding='utf-8') as f:
                for friend in self.friends_list:
                    f.write(friend + '\n')
            # Also save to friends.json for backward compatibility
            with open('friends.json', 'w') as f:
                json.dump(self.friends_list, f)
        except:
            pass
            
    def _load_friends(self):
        try:
            # Try loading from friends.txt first (one friend per line)
            if os.path.exists('friends.txt'):
                with open('friends.txt', 'r', encoding='utf-8') as f:
                    self.friends_list = []
                    for line in f:
                        friend = line.strip()
                        if friend:  # Skip empty lines
                            self.friends_list.append(friend)
                            self.friends_listbox.insert(tk.END, friend)
            # Fallback to friends.json if txt doesn't exist
            elif os.path.exists('friends.json'):
                with open('friends.json', 'r') as f:
                    self.friends_list = json.load(f)
                    for friend in self.friends_list:
                        self.friends_listbox.insert(tk.END, friend)
        except:
            pass
            
    def _launch_sessions(self):
        if not self.friends_list:
            messagebox.showwarning("Warning", "Please add at least one friend/username first!")
            return
            
        session_count = self.session_var.get()
        
        # Stop existing sessions
        self._stop_all_sessions()
        
        # Launch new sessions
        for i in range(1, session_count + 1):
            user_data_dir = os.path.join(self.base_user_data_dir, f'session_{i}')
            session = ChromeSession(i, user_data_dir, self.friends_list.copy(), self._update_status)
            self.sessions[i] = session
            session.start()
            
        self.launch_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._update_status(0, f"Launched {session_count} session(s). Each will open Chrome - please login manually.")
        
    def _stop_all_sessions(self):
        for session in self.sessions.values():
            session.stop()
        self.sessions.clear()
        self.launch_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self._update_status(0, "All sessions stopped.")
        
    def _update_status(self, session_id, message):
        timestamp = time.strftime("%H:%M:%S")
        status_msg = f"[{timestamp}] {message}\n"
        self.status_text.insert(tk.END, status_msg)
        self.status_text.see(tk.END)
        self.root.update_idletasks()


if __name__ == "__main__":
    root = tk.Tk()
    app = SnapchatAutomationApp(root)
    root.mainloop()
