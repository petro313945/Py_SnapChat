import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import os
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time

class ChromeSession:
    def __init__(self, session_id, user_data_dir, friends_list, status_callback):
        self.session_id = session_id
        self.user_data_dir = user_data_dir
        self.friends_list = friends_list
        self.status_callback = status_callback
        self.playwright = None
        self.browser = None
        self.page = None
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
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
            self.browser = None
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass
            self.playwright = None
        self.page = None
            
    def _run_automation(self):
        try:
            # Launch Playwright with persistent context
            try:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                    ],
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                # Get or create page
                if self.browser.pages:
                    self.page = self.browser.pages[0]
                else:
                    self.page = self.browser.new_page()
                    
            except Exception as e:
                self.status_callback(self.session_id, f"Session {self.session_id}: Playwright error - {str(e)}")
                self.status_callback(self.session_id, f"Session {self.session_id}: Make sure Playwright is installed: pip install playwright && playwright install chromium")
                self.is_running = False
                return
                
            self.page.goto('https://www.snapchat.com')
            
            # Wait for login (user must login manually)
            self.status_callback(self.session_id, f"Session {self.session_id}: Waiting for login...")
            
            # Wait until logged in (check for camera button or similar)
            try:
                # Wait for camera button or main interface
                self.page.wait_for_selector('button.FBYjn.gK0xL.W5dIq, button.fE2D5', timeout=300000)  # 5 min timeout
                self.status_callback(self.session_id, f"Session {self.session_id}: Logged in, waiting 2 minutes for friends to load...")
            except PlaywrightTimeoutError:
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
                        # Status message removed - no longer displaying "Sent X photos. Total: Y"
                        # Wait 1 second before next round
                        time.sleep(1.0)
                    else:
                        time.sleep(0.3)  # Reduced error delay (optimized for 20 rounds/min)
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
            # Step 0: Check if already at photo preview
            photo_img = self._find_element_safe('img.VcjuA')
            skip_to_send = photo_img is not None
            
            if not skip_to_send:
                # Step 1: Check if already at friend selection modal
                friend_modal_check = self._find_element_safe('form.tvul8.pebzM')
                if friend_modal_check:
                    # Already at friend selection modal, skip to Step 7
                    # Step 7: Find friend list immediately (no delay - start searching right away)
                    friend_list = self._find_element_safe('ul.s7loS')
                    timing_list_found = time.time()
                    
                    if not friend_list:
                        return {'success': False, 'error': 'Friend list not found'}
                    
                    # Find and click friends one at a time - optimized for speed
                    timing_select_start = time.time()
                    timing_list_items_found = time.time()
                    
                    selected_count = 0
                    not_found_count = 0
                    already_selected_count = 0
                    
                    # Click each friend using Playwright's text-based locator (more reliable)
                    for friend_name in self.friends_list:
                        try:
                            clicked = False
                            
                            # Find by text content in the list item
                            locator = self.page.locator('ul.s7loS li').filter(has_text=friend_name).first
                            # Check if already selected (optimized - check and click in one JS call)
                            result = locator.evaluate("""
                                (el) => {
                                    // Check if already selected
                                    var checkedCheckbox = el.querySelector('input[type="checkbox"]:checked');
                                    var isSelected = el.classList.contains('selected') || 
                                                   el.getAttribute('aria-selected') === 'true' ||
                                                   checkedCheckbox !== null;
                                    if (!isSelected) {
                                        // Try to click the clickable div first
                                        var clickable = el.querySelector('div.Ewflr.cDeBk') || 
                                                       el.querySelector('div.Ewflr') || 
                                                       el;
                                        clickable.click();
                                        return true;
                                    }
                                    return false;
                                }
                            """)
                            if result:
                                clicked = True
                            else:
                                # Already selected, skip
                                already_selected_count += 1
                                continue
                            
                            if clicked:
                                selected_count += 1
                            else:
                                not_found_count += 1
                                
                        except Exception as e:
                            not_found_count += 1
                            continue
                    
                    timing_select_end = time.time()
                    timing_select = timing_select_end - timing_list_items_found
                    
                    self.status_callback(self.session_id, 
                        f"Session {self.session_id} [TIMING] Select: {timing_select:.3f}s | "
                        f"Clicked: {selected_count} (Skipped to Step 7)")
                    
                    # Step 8: Click Send button
                    send_btn = None
                    try:
                        self.page.click('button.TYX6O.eKaL7.Bnaur[type="submit"]', timeout=500)
                        send_btn = True
                    except:
                        try:
                            self.page.click('button.TYX6O.eKaL7.Bnaur', timeout=500)
                            send_btn = True
                        except:
                            try:
                                self.page.click('button.TYX6O', timeout=500)
                                send_btn = True
                            except:
                                pass
                        
                    if not send_btn:
                        return {
                            'success': False,
                            'error': 'Send button not found',
                            'selected_count': selected_count,
                            'not_found_count': not_found_count
                        }
                    
                    return {
                        'success': True,
                        'sent_count': selected_count,
                        'not_found_count': not_found_count
                    }
                
                # Step 2: Open camera if not already open
                camera_modal = self._find_element_safe('div.Nuu9e')
                if not camera_modal:
                    # Click open camera button
                    try:
                        self.page.click('button.FBYjn.gK0xL.W5dIq', timeout=1000)
                    except:
                        return {'success': False, 'error': 'Open camera button not found'}
                    time.sleep(0.005)
                    
                    # Wait for camera modal
                    camera_modal = self._find_element_with_retry('div.Nuu9e', max_retries=4)
                    if not camera_modal:
                        return {'success': False, 'error': 'Camera modal did not appear'}
                
                # Step 3: Wait for camera to load (minimal delay)
                time.sleep(0.002)
                
                # Step 4: Click shot button
                shot_button = None
                try:
                    self.page.click('div.Nuu9e button.fE2D5', timeout=500)
                    shot_button = True
                except:
                    try:
                        self.page.click('div.Nuu9e button.FBYjn.gK0xL.W5dIq', timeout=500)
                        shot_button = True
                    except:
                        try:
                            self.page.click('div.Nuu9e button.FBYjn', timeout=500)
                            shot_button = True
                        except:
                            pass
                    
                if not shot_button:
                    return {'success': False, 'error': 'Shot button not found'}
                    
                time.sleep(0.0005)
                
                # Wait for photo to appear
                photo_img = self._find_element_with_retry('img.VcjuA', max_retries=3)
                if not photo_img:
                    return {'success': False, 'error': 'Photo did not appear'}
                    
                time.sleep(0.0005)
            
            # Step 5: Click Send To button (optimized for speed)
            send_to_btn = None
            try:
                self.page.click('button.YatIx.fGS78.eKaL7.Bnaur', timeout=500)
                send_to_btn = True
            except:
                try:
                    self.page.click('button.YatIx.fGS78', timeout=500)
                    send_to_btn = True
                except:
                    try:
                        self.page.click('button.YatIx', timeout=500)
                        send_to_btn = True
                    except:
                        pass
                
            if not send_to_btn:
                return {'success': False, 'error': 'Send To button not found'}
                
            # TIMING: Start tracking from Send To click
            timing_start = time.time()
            timing_after_click = time.time()
            
            # Step 6: Wait for friend modal (optimized - start immediately with minimal retries)
            friend_modal = None
            try:
                self.page.wait_for_selector('form.tvul8.pebzM', timeout=500, state='visible')
                friend_modal = True
            except:
                try:
                    self.page.wait_for_selector('form.tvul8', timeout=500, state='visible')
                    friend_modal = True
                except:
                    try:
                        self.page.wait_for_selector('form.pebzM', timeout=500, state='visible')
                        friend_modal = True
                    except:
                        pass
            timing_modal_found = time.time()
                
            if not friend_modal:
                return {'success': False, 'error': 'Friend modal not found'}
                
            # Step 7: Find friend list immediately (no delay - start searching right away)
            friend_list = self._find_element_safe('ul.s7loS')
            timing_list_found = time.time()
                
            if not friend_list:
                return {'success': False, 'error': 'Friend list not found'}
                
            # Find and click friends one at a time - optimized for speed
            timing_select_start = time.time()
            timing_list_items_found = time.time()
            
            selected_count = 0
            not_found_count = 0
            already_selected_count = 0
            
            # Click each friend using Playwright's text-based locator (more reliable)
            for friend_name in self.friends_list:
                try:
                    clicked = False
                    
                    # Find by text content in the list item
                    locator = self.page.locator('ul.s7loS li').filter(has_text=friend_name).first
                    # Check if already selected (optimized - check and click in one JS call)
                    result = locator.evaluate("""
                        (el) => {
                            // Check if already selected
                            var checkedCheckbox = el.querySelector('input[type="checkbox"]:checked');
                            var isSelected = el.classList.contains('selected') || 
                                           el.getAttribute('aria-selected') === 'true' ||
                                           checkedCheckbox !== null;
                            if (!isSelected) {
                                // Try to click the clickable div first
                                var clickable = el.querySelector('div.Ewflr.cDeBk') || 
                                               el.querySelector('div.Ewflr') || 
                                               el;
                                clickable.click();
                                return true;
                            }
                            return false;
                        }
                    """)
                    if result:
                        clicked = True
                    else:
                        # Already selected, skip
                        already_selected_count += 1
                        continue
                    
                    if clicked:
                        selected_count += 1
                    else:
                        not_found_count += 1
                        
                except Exception as e:
                    not_found_count += 1
                    continue
            
            timing_select_end = time.time()
            timing_total = timing_select_end - timing_start
            timing_to_modal = timing_modal_found - timing_after_click
            timing_to_list = timing_list_found - timing_modal_found
            timing_select = timing_select_end - timing_list_items_found
            
            self.status_callback(self.session_id, 
                f"Session {self.session_id} [TIMING] Total: {timing_total:.3f}s | "
                f"Modal: {timing_to_modal:.3f}s | "
                f"List: {timing_to_list:.3f}s | "
                f"Select: {timing_select:.3f}s | "
                f"Clicked: {selected_count}")
            
            # Step 8: Click Send button
            send_btn = None
            try:
                self.page.click('button.TYX6O.eKaL7.Bnaur[type="submit"]', timeout=500)
                send_btn = True
            except:
                try:
                    self.page.click('button.TYX6O.eKaL7.Bnaur', timeout=500)
                    send_btn = True
                except:
                    try:
                        self.page.click('button.TYX6O', timeout=500)
                        send_btn = True
                    except:
                        pass
                
            if not send_btn:
                return {
                    'success': False,
                    'error': 'Send button not found',
                    'selected_count': selected_count,
                    'not_found_count': not_found_count
                }
            
            return {
                'success': True,
                'sent_count': selected_count,
                'not_found_count': not_found_count
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _find_element_safe(self, selector):
        try:
            element = self.page.query_selector(selector)
            if element:
                # Check if element is visible using bounding_box (faster than is_visible check)
                try:
                    box = element.bounding_box()
                    if box and box['width'] > 0 and box['height'] > 0:
                        return element
                except:
                    pass
            return None
        except:
            return None
            
    def _find_element_with_retry(self, selector, max_retries=3, delay=0.001):
        # First try immediately (no delay)
        element = self._find_element_safe(selector)
        if element:
            return element
        
        # Then retry with delays
        for i in range(max_retries - 1):
            time.sleep(delay)
            element = self._find_element_safe(selector)
            if element:
                return element
        return None
        
    def _find_element_in_container(self, container, selector):
        try:
            # In Playwright, container is a Locator, so we use locator.query_selector
            if hasattr(container, 'query_selector'):
                return container.query_selector(selector)
            else:
                # If container is a selector string, combine them
                return self.page.query_selector(f'{container} {selector}')
        except:
            return None
            
    def _is_visible(self, element):
        try:
            box = element.bounding_box()
            return box is not None and box['width'] > 0 and box['height'] > 0
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
        self.session_widgets = {}
        self.base_user_data_dir = os.path.join(os.getcwd(), 'chrome_profiles')
        self.start_time = None
        self.timer_running = False
        
        # Create profiles directory
        os.makedirs(self.base_user_data_dir, exist_ok=True)
        
        self._create_gui()
        self._load_friends()
        
    def _create_gui(self):
        # Session count slider and launch button on same row
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
        
        # Launch button on same row
        self.launch_btn = tk.Button(slider_frame, text="Launch Sessions", font=('Arial', 9),
                                   bg='#4CAF50', fg='white', padx=12, pady=6,
                                   activebackground='#45a049', activeforeground='white',
                                   command=self._launch_sessions)
        self.launch_btn.pack(side=tk.LEFT, padx=10)
        
        # View Friends button on same row
        view_friends_btn = tk.Button(slider_frame, text="View Friends", font=('Arial', 9),
                                     bg='#2196F3', fg='white', padx=12, pady=6,
                                     activebackground='#0b7dda', activeforeground='white',
                                     command=self._show_friends_modal)
        view_friends_btn.pack(side=tk.LEFT, padx=10)
        
        # Stop button on same row
        self.stop_btn = tk.Button(slider_frame, text="Stop All Sessions", font=('Arial', 9),
                                  bg='#f44336', fg='white', padx=12, pady=6,
                                  activebackground='#da190b', activeforeground='white',
                                  disabledforeground='white',
                                  command=self._stop_all_sessions, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # Working time label on the right side
        self.working_time_label = tk.Label(slider_frame, text="", font=('Arial', 10),
                                          bg='#0b0b0b', fg='#31d158', width=15)
        self.working_time_label.pack(side=tk.RIGHT, padx=10)
        
        # Session list display
        session_list_frame = tk.LabelFrame(self.root, text="Sessions", font=('Arial', 12),
                                           bg='#1a1a1a', fg='white', padx=10, pady=10)
        session_list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=False)
        
        # Container for session items with flex layout
        self.session_container = tk.Frame(session_list_frame, bg='#1a1a1a')
        self.session_container.pack(fill=tk.BOTH, expand=True)
        
        # Hidden friends listbox for internal use
        self.friends_listbox = tk.Listbox(self.root, font=('Arial', 10), bg='#2a2a2a',
                                          fg='white', selectbackground='#31d158')
        # Don't pack it - it's just for internal management
        
        # Status panel - bigger
        status_frame = tk.LabelFrame(self.root, text="Status", font=('Arial', 12),
                                     bg='#1a1a1a', fg='white', padx=10, pady=10)
        status_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, font=('Consolas', 9),
                                                     bg='#2a2a2a', fg='white', wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
    def _show_friends_modal(self):
        """Open a modal window showing the friend list"""
        modal = tk.Toplevel(self.root)
        modal.title("Friends List")
        modal.geometry("400x500")
        modal.configure(bg='#1a1a1a')
        modal.transient(self.root)
        modal.grab_set()
        
        # Title
        title_label = tk.Label(modal, text="Friends/Usernames", font=('Arial', 14, 'bold'),
                              bg='#1a1a1a', fg='white')
        title_label.pack(pady=10)
        
        # Friends input
        input_frame = tk.Frame(modal, bg='#1a1a1a')
        input_frame.pack(fill=tk.X, padx=20, pady=5)
        
        friend_entry = tk.Entry(input_frame, font=('Arial', 11), bg='#2a2a2a', fg='white',
                                insertbackground='white')
        friend_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        def add_friend():
            friend = friend_entry.get().strip()
            if friend and friend not in self.friends_list:
                self.friends_list.append(friend)
                friends_listbox.insert(tk.END, friend)
                friend_entry.delete(0, tk.END)
                self._save_friends()
        
        friend_entry.bind('<Return>', lambda e: add_friend())
        
        add_btn = tk.Button(input_frame, text="Add", bg='#31d158', fg='white',
                           command=add_friend, padx=8, pady=4, font=('Arial', 9),
                           activebackground='#45a049', activeforeground='white')
        add_btn.pack(side=tk.LEFT, padx=5)
        
        # Friends list
        friends_listbox = tk.Listbox(modal, font=('Arial', 10), bg='#2a2a2a',
                                     fg='white', selectbackground='#31d158')
        friends_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        # Load friends into modal listbox
        for friend in self.friends_list:
            friends_listbox.insert(tk.END, friend)
        
        # Friends buttons
        friends_btn_frame = tk.Frame(modal, bg='#1a1a1a')
        friends_btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        def remove_friend():
            selection = friends_listbox.curselection()
            if selection:
                index = selection[0]
                friends_listbox.delete(index)
                self.friends_list.pop(index)
                self._save_friends()
        
        def clear_friends():
            friends_listbox.delete(0, tk.END)
            self.friends_list = []
            self._save_friends()
        
        remove_btn = tk.Button(friends_btn_frame, text="Remove Selected", bg='#ff5f57', fg='white',
                              command=remove_friend, padx=8, pady=4, font=('Arial', 9),
                              activebackground='#da190b', activeforeground='white')
        remove_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(friends_btn_frame, text="Clear All", bg='#ff5f57', fg='white',
                             command=clear_friends, padx=8, pady=4, font=('Arial', 9),
                             activebackground='#da190b', activeforeground='white')
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = tk.Button(friends_btn_frame, text="Close", bg='#2a2a2a', fg='white',
                             command=modal.destroy, padx=8, pady=4, font=('Arial', 9),
                             activebackground='#3a3a3a', activeforeground='white')
        close_btn.pack(side=tk.RIGHT, padx=5)
    
    def _add_friend(self):
        # This method is kept for compatibility but may not be used directly
        pass
            
    def _remove_friend(self):
        # This method is kept for compatibility but may not be used directly
        pass
            
    def _clear_friends(self):
        # This method is kept for compatibility but may not be used directly
        pass
        
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
        
        # Clear session display
        for widget in self.session_container.winfo_children():
            widget.destroy()
        self.session_widgets.clear()
        
        # Launch new sessions
        for i in range(1, session_count + 1):
            user_data_dir = os.path.join(self.base_user_data_dir, f'session_{i}')
            session = ChromeSession(i, user_data_dir, self.friends_list.copy(), self._update_status)
            self.sessions[i] = session
            session.start()
            # Create session display widget
            self._create_session_widget(i)
            
        self.launch_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._update_status(0, f"Launched {session_count} session(s). Each will open Chrome - please login manually.")
        
        # Start working time timer
        self.start_time = time.time()
        self.timer_running = True
        self._update_working_time()
    
    def _create_session_widget(self, session_id):
        """Create a widget for displaying session info with sent photo count"""
        session_frame = tk.Frame(self.session_container, bg='#2a2a2a', relief=tk.RAISED, bd=2)
        session_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        session_label = tk.Label(session_frame, text=f"Session {session_id}", 
                                 font=('Arial', 10, 'bold'), bg='#2a2a2a', fg='white')
        session_label.pack(pady=5)
        
        count_label = tk.Label(session_frame, text="Photos: 0", 
                              font=('Arial', 9), bg='#2a2a2a', fg='#31d158')
        count_label.pack(pady=2)
        
        self.session_widgets[session_id] = {
            'frame': session_frame,
            'count_label': count_label
        }
    
    def _update_session_display(self, session_id):
        """Update the session display with current sent count"""
        if session_id in self.sessions and session_id in self.session_widgets:
            session = self.sessions[session_id]
            count = session.sent_count if hasattr(session, 'sent_count') else 0
            self.session_widgets[session_id]['count_label'].config(text=f"Photos: {count}")
        
    def _stop_all_sessions(self):
        for session in self.sessions.values():
            session.stop()
        self.sessions.clear()
        # Clear session display
        for widget in self.session_container.winfo_children():
            widget.destroy()
        self.session_widgets.clear()
        self.launch_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self._update_status(0, "All sessions stopped.")
        
        # Stop working time timer
        self.timer_running = False
        self.start_time = None
        self.working_time_label.config(text="")
        
    def _update_status(self, session_id, message):
        # Calculate working time instead of timestamp
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            if hours > 0:
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{minutes:02d}:{seconds:02d}"
        else:
            time_str = "00:00"
        # Format: [working_time] Session X [TIMING] ... or [working_time] message
        if session_id > 0 and "[TIMING]" in message:
            # Message already includes "Session X", just add working time
            status_msg = f"[{time_str}] {message}\n"
        else:
            # Regular message, add session prefix if session_id > 0
            if session_id > 0:
                status_msg = f"[{time_str}] Session {session_id} {message}\n"
            else:
                status_msg = f"[{time_str}] {message}\n"
        self.status_text.insert(tk.END, status_msg)
        self.status_text.see(tk.END)
        # Update session display when status mentions sent count or Total
        if session_id > 0 and ("Total:" in message or "Sent" in message):
            self._update_session_display(session_id)
        self.root.update_idletasks()
    
    def _refresh_all_session_displays(self):
        """Refresh all session displays"""
        for session_id in self.sessions.keys():
            self._update_session_display(session_id)
    
    def _update_working_time(self):
        """Update the working time display"""
        if not self.timer_running or self.start_time is None:
            return
        
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        if hours > 0:
            time_str = f"Working: {hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            time_str = f"Working: {minutes:02d}:{seconds:02d}"
        
        self.working_time_label.config(text=time_str)
        
        # Schedule next update in 1 second
        if self.timer_running:
            self.root.after(1000, self._update_working_time)


if __name__ == "__main__":
    root = tk.Tk()
    app = SnapchatAutomationApp(root)
    root.mainloop()
