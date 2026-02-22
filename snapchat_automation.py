import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import os
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
from datetime import datetime

class ChromeSession:
    def __init__(self, session_id, user_data_dir, friends_list, status_callback, start_time=None):
        self.session_id = session_id
        self.user_data_dir = user_data_dir
        self.friends_list = friends_list
        self.status_callback = status_callback
        self.start_time = start_time
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
        # Stop the JavaScript automation loop
        if self.page:
            try:
                self.page.evaluate("""
                    if (window.__snapchatAutomation) {
                        window.__snapchatAutomation.isRunning = false;
                        if (window.__snapchatAutomation.intervalId) {
                            clearInterval(window.__snapchatAutomation.intervalId);
                        }
                    }
                    window.__snapchatAutomationRunning = false;
                """)
            except:
                pass
        # Close all pages first
        if self.browser:
            try:
                # Close all pages in the browser context
                pages_to_close = list(self.browser.pages)  # Create a copy to avoid modification during iteration
                for page in pages_to_close:
                    try:
                        if not page.is_closed():
                            page.close()
                    except:
                        pass
            except:
                pass
        # Close the browser context (this will close all browser windows)
        if self.browser:
            try:
                self.browser.close()
                # Give it a moment to close
                time.sleep(0.5)
            except:
                pass
            self.browser = None
        # Stop playwright
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
                
                # Block automatic downloads (Snapchat downloads photos automatically)
                def handle_download(download):
                    # Cancel the download to prevent files from being saved
                    try:
                        download.cancel()
                    except:
                        pass
                
                self.page.on("download", handle_download)
                
                # Capture console messages and forward to status
                def handle_console(msg):
                    text = msg.text
                    # Forward all console messages that start with [Iteration 1]
                    if '[Iteration 1]' in text:
                        self.status_callback(self.session_id, f"CONSOLE: {text}")
                
                self.page.on("console", handle_console)
                    
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
                self.status_callback(self.session_id, f"Session {self.session_id}: Logged in, waiting 3 minutes for friends to load...")
            except PlaywrightTimeoutError:
                self.status_callback(self.session_id, f"Session {self.session_id}: Login timeout")
                self.is_running = False
                return
                
            # Wait 3 minutes for friends to load
            time.sleep(180)
            self.status_callback(self.session_id, f"Session {self.session_id}: Starting automation...")
            
            # Wait for page to be ready
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass  # Continue even if networkidle times out
                
            # Expose communication bridge for status updates (must be before script injection)
            self.page.expose_function("reportStatus", lambda msg: self.status_callback(self.session_id, msg))
            self.page.expose_function("reportSentCount", lambda count: self._update_sent_count(count))
            
            # Test console handler
            try:
                self.page.evaluate("console.log('[Iteration 1] Console handler test - if you see this, handler is working!')")
                time.sleep(0.5)  # Give it time to process
            except Exception as e:
                self.status_callback(self.session_id, f"Session {self.session_id}: Console test error: {str(e)}")
            
            # Inject in-page automation script and start the loop
            try:
                automation_js = self._get_automation_script()
                
                # First inject the automation script
                self.page.evaluate(f"""
                    console.log('[Iteration 1] Script injection started');
                    {automation_js}
                """)
                
                # Then initialize and start the automation
                # Calculate start_time in milliseconds for JavaScript
                start_time_ms = int(self.start_time * 1000) if self.start_time else None
                start_time_js = start_time_ms if start_time_ms else 'Date.now()'
                
                result = self.page.evaluate(f"""
                    (function() {{
                        try {{
                            console.log('[Iteration 1] Initialization function started');
                            
                            if (window.__snapchatAutomationRunning) {{
                                console.log('[Iteration 1] Automation already running, skipping initialization');
                                return 'ALREADY_RUNNING';
                            }}
                            
                            const friendsList = {json.dumps(self.friends_list)};
                            console.log('[Iteration 1] Friends list loaded:', friendsList);
                            
                            // Initialize automation state
                            const startTimeMs = {start_time_js};
                            window.__snapchatAutomation = {{
                                friendsList: friendsList,
                                sentCount: 0,
                                isRunning: true,
                                intervalId: null,
                                startTime: startTimeMs
                            }};
                            
                            window.__snapchatAutomationRunning = true;
                            
                            // Start the main loop (it handles continuous execution internally)
                            if (window.mainLoop) {{
                                console.log('[Iteration 1] Starting main loop...');
                                window.mainLoop();
                            }} else {{
                                console.log('[Iteration 1] ERROR: mainLoop function not found!');
                                if (window.reportStatus) window.reportStatus('[Iteration 1] ERROR: mainLoop function not found!');
                            }}
                            
                            return 'SUCCESS';
                        }} catch (error) {{
                            console.error('[Iteration 1] Script injection error:', error);
                            return 'ERROR: ' + error.message;
                        }}
                    }})();
                """)
                
                # Verify script was injected (silently)
                time.sleep(1)
                is_running = self.page.evaluate("window.__snapchatAutomationRunning === true")
                has_mainloop = self.page.evaluate("typeof window.mainLoop === 'function'")
                
            except Exception as e:
                self.status_callback(self.session_id, f"Session {self.session_id}: ERROR injecting script - {str(e)}")
                import traceback
                self.status_callback(self.session_id, f"Session {self.session_id}: Traceback: {traceback.format_exc()}")
            
            # Monitor the automation (Python just maintains the session)
            while self.is_running:
                try:
                    # Check if automation is still running
                    is_automation_running = self.page.evaluate("window.__snapchatAutomationRunning === true")
                    if not is_automation_running:
                        self.status_callback(self.session_id, "Automation stopped in browser")
                        break
                    time.sleep(5)  # Check every 5 seconds
                except Exception as e:
                    self.status_callback(self.session_id, f"Session {self.session_id}: Monitor error - {str(e)}")
                    time.sleep(5)
                    
        except Exception as e:
            self.status_callback(self.session_id, f"Session {self.session_id}: Fatal error - {str(e)}")
        finally:
            self.is_running = False
            
    def _get_automation_script(self):
        """Returns the JavaScript automation script that runs in-page"""
        return """
        (function() {
            // Helper function to find element safely
            function findElement(selector) {
                try {
                    const el = document.querySelector(selector);
                    if (el) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            return el;
                        }
                    }
                } catch (e) {}
                return null;
            }
            
            // Helper function to sleep - more precise timing
            function sleep(ms) {
                return new Promise(resolve => {
                    const start = Date.now();
                    // Use setTimeout for most of the delay
                    setTimeout(() => {
                        // Busy-wait for the remaining time to get more precise timing
                        const elapsed = Date.now() - start;
                        const remaining = ms - elapsed;
                        if (remaining > 0) {
                            const busyStart = Date.now();
                            // Busy-wait for remaining time (max 50ms to avoid blocking too long)
                            while (Date.now() - busyStart < Math.min(remaining, 50)) {
                                // Busy wait
                            }
                        }
                        resolve();
                    }, Math.max(0, ms - 10)); // Reserve 10ms for busy-wait
                });
            }
            
            // Helper function to wait for element with timeout
            function waitForElement(selector, maxWait = 200, checkInterval = 50) {
                return new Promise((resolve) => {
                    const startTime = Date.now();
                    const check = () => {
                        const el = findElement(selector);
                        if (el) {
                            resolve(el);
                        } else if ((Date.now() - startTime) >= maxWait) {
                            resolve(null);
                        } else {
                            setTimeout(check, checkInterval);
                        }
                    };
                    check();
                });
            }
            
            // Retry function with timeout
            async function retryAction(action, maxRetries = 2, timeout = 200) {
                for (let i = 0; i < maxRetries; i++) {
                    const result = await action();
                    if (result !== null && result !== false) {
                        return result;
                    }
                    if (i < maxRetries - 1) {
                        await sleep(timeout);
                    }
                }
                return null;
            }
            
            // Main round function - runs Step 1 → Step 7 in one continuous flow
            async function runRound() {
                if (!window.__snapchatAutomation || !window.__snapchatAutomation.isRunning) {
                    return { success: false, error: 'Automation not running' };
                }
                
                const roundStartTime = Date.now();
                const friendsList = window.__snapchatAutomation.friendsList;
                let roundResult = { success: false, selectedCount: 0, error: null, timings: {} };
                
                // Report round start with timestamp
                if (window.reportStatus) {
                    const elapsed = window.__snapchatAutomation.startTime ? 
                        Math.floor((Date.now() - window.__snapchatAutomation.startTime) / 1000) : 0;
                    const hours = Math.floor(elapsed / 3600);
                    const minutes = Math.floor((elapsed % 3600) / 60);
                    const seconds = elapsed % 60;
                    const timeStr = hours > 0 ? 
                        `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}` :
                        `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                    window.reportStatus(`[${timeStr}] Starting new round...`);
                }
                
                try {
                    // Step 1: Check Send To Button
                    const step1Start = Date.now();
                    const photoImage = document.querySelector('img.VcjuA');
                    const sendToBtn = photoImage ? document.querySelector('button.YatIx.fGS78.eKaL7.Bnaur') : null;
                    const hasSendTo = sendToBtn !== null;
                    roundResult.timings.step1 = Date.now() - step1Start;
                    
                    // Step 2: Check Friend Modal
                    const step2Start = Date.now();
                    const friendModal = findElement('form.tvul8.pebzM');
                    const atFriendModal = friendModal !== null;
                    roundResult.timings.step2 = Date.now() - step2Start;
                    
                    // Step 3: Open Camera (only if Steps 1 & 2 didn't skip)
                    if (!hasSendTo && !atFriendModal) {
                        const step3Start = Date.now();
                        
                        // Check if camera modal already open (use findElement to check visibility)
                        const shotBtnCheck = findElement('button.fE2D5');
                        if (shotBtnCheck) {
                            roundResult.timings.step3 = Date.now() - step3Start;
                        } else {
                            // Click camera button with retry
                            const cameraResult = await retryAction(async () => {
                                const cameraBtn = findElement('button.FBYjn.gK0xL.W5dIq');
                                if (cameraBtn) {
                                    try {
                                        cameraBtn.click();
                                        return true;
                                    } catch (e) {
                                        return false;
                                    }
                                }
                                return false;
                            }, 2, 200);
                            
                            roundResult.timings.step3 = Date.now() - step3Start;
                            if (!cameraResult) {
                                roundResult.error = 'Step 3: Failed to open camera';
                                if (window.reportStatus) window.reportStatus(roundResult.error);
                                return roundResult;
                            }
                        }
                    } else {
                        roundResult.timings.step3 = 0;
                    }
                    
                    // Step 4: Click Shot Button (only if Steps 1 & 2 didn't skip)
                    if (!hasSendTo && !atFriendModal) {
                        const step4Start = Date.now();
                        
                        const shotResult = await retryAction(async () => {
                            const shotBtn = document.querySelector('button.fE2D5');
                            if (shotBtn) {
                                try {
                                    // Dispatch pointer events only (pointerdown + pointerup)
                                    shotBtn.dispatchEvent(new PointerEvent('pointerdown', {
                                        bubbles: true,
                                        cancelable: true,
                                        pointerId: 1,
                                        button: 0,
                                        buttons: 1
                                    }));
                                    shotBtn.dispatchEvent(new PointerEvent('pointerup', {
                                        bubbles: true,
                                        cancelable: true,
                                        pointerId: 1,
                                        button: 0,
                                        buttons: 0
                                    }));
                                    return true;
                                } catch (e) {
                                    return false;
                                }
                            }
                            return false;
                        }, 2, 100);
                        
                        roundResult.timings.step4 = Date.now() - step4Start;
                        if (!shotResult) {
                            roundResult.error = 'Step 4: Failed to click shot button';
                            if (window.reportStatus) window.reportStatus(roundResult.error);
                            return roundResult;
                        }
                    } else {
                        roundResult.timings.step4 = 0;
                    }
                    
                    // Step 5: Click Send To Button (only if Step 2 didn't skip)
                    if (!atFriendModal) {
                        const step5Start = Date.now();
                        
                        // Delay 300ms before starting Step 5
                        await sleep(300);
                        
                        let attemptCount = 0;
                        const sendToResult = await retryAction(async () => {
                            attemptCount++;
                            // TEMPORARILY DISABLED: Photo image check
                            // const photoImg = document.querySelector('img.VcjuA');
                            // if (!photoImg) {
                            //     return false;
                            // }
                            
                            const btn = document.querySelector('button.YatIx.fGS78.eKaL7.Bnaur');
                            if (!btn) {
                                return false;
                            }
                            
                            // Check button visibility and properties
                            const rect = btn.getBoundingClientRect();
                            const isVisible = rect.width > 0 && rect.height > 0;
                            const isDisabled = btn.disabled || btn.getAttribute('disabled') !== null;
                            
                            if (!isVisible) {
                                return false;
                            }
                            
                            if (isDisabled) {
                                return false;
                            }
                            
                            try {
                                btn.click();
                                return true;
                            } catch (e) {
                                return false;
                            }
                        }, 2, 200);
                        
                        roundResult.timings.step5 = Date.now() - step5Start;
                        if (!sendToResult) {
                            roundResult.error = 'Step 5: Failed to click Send To button';
                            if (window.reportStatus) window.reportStatus(roundResult.error);
                            return roundResult;
                        }
                    } else {
                        roundResult.timings.step5 = 0;
                    }
                    
                    // Step 6: Select Friends
                    const step6Start = Date.now();
                    
                    let selectedCount = 0;
                    const friendListItems = document.querySelectorAll('ul.s7loS li');
                    
                    for (const friendName of friendsList) {
                        for (const item of friendListItems) {
                            if (item.textContent && item.textContent.includes(friendName)) {
                                // Temporarily disabled: Check if already selected
                                // const checkbox = item.querySelector('input[type="checkbox"]');
                                // const isSelected = checkbox ? checkbox.checked : false;
                                
                                // if (!isSelected) {
                                    const clickable = item.querySelector('div.Ewflr.cDeBk') || 
                                                     item.querySelector('div.Ewflr') || 
                                                     item;
                                    if (clickable) {
                                        try {
                                            clickable.click();
                                            selectedCount++;
                                            await sleep(5); // Small delay between clicks
                                        } catch (e) {
                                            // Skip on error
                                        }
                                    }
                                // }
                                break;
                            }
                        }
                    }
                    
                    roundResult.selectedCount = selectedCount;
                    roundResult.timings.step6 = Date.now() - step6Start;
                    
                    // Step 7: Click Send Button
                    if (selectedCount > 0) {
                        const step7Start = Date.now();
                        
                        const sendResult = await retryAction(async () => {
                            const sendBtn = document.querySelector('button.TYX6O.eKaL7.Bnaur[type="submit"]');
                            if (sendBtn) {
                                try {
                                    sendBtn.click();
                                    return true;
                                } catch (e) {
                                    return false;
                                }
                            }
                            return false;
                        }, 2, 200);
                        
                        roundResult.timings.step7 = Date.now() - step7Start;
                        if (!sendResult) {
                            roundResult.error = 'Step 7: Failed to click Send button';
                            if (window.reportStatus) window.reportStatus(roundResult.error);
                            return roundResult;
                        }
                        
                        window.__snapchatAutomation.sentCount += selectedCount;
                        roundResult.success = true;
                        roundResult.timings.total = Date.now() - roundStartTime;
                        
                        if (window.reportSentCount) {
                            window.reportSentCount(window.__snapchatAutomation.sentCount);
                        }
                    } else {
                        roundResult.error = 'Step 7: No friends selected';
                        if (window.reportStatus) window.reportStatus(roundResult.error);
                    }
                    
                } catch (error) {
                    roundResult.error = 'Exception: ' + error.message;
                    roundResult.timings.total = Date.now() - roundStartTime;
                    if (window.reportStatus) {
                        window.reportStatus(roundResult.error);
                    }
                }
                
                return roundResult;
            }
            
            // Main continuous loop
            async function mainLoop() {
                let roundNumber = 0;
                while (window.__snapchatAutomation && window.__snapchatAutomation.isRunning) {
                    roundNumber++;
                    const roundStartTime = Date.now();
                    
                    // Log round start
                    const roundStartMsg = `[ROUND ${roundNumber}] Starting at ${new Date(roundStartTime).toISOString()}`;
                    if (window.reportStatus) window.reportStatus(roundStartMsg);
                    
                    const roundResult = await runRound();
                    const roundEndTime = Date.now();
                    const roundDuration = roundEndTime - roundStartTime;
                    
                    // Log round completion
                    const roundEndMsg = `[ROUND ${roundNumber}] Completed in ${roundDuration}ms | Success: ${roundResult.success} | Selected: ${roundResult.selectedCount} | Error: ${roundResult.error || 'none'}`;
                    if (window.reportStatus) window.reportStatus(roundEndMsg);
                    
                    // Calculate delay based on result
                    const delayCalcStart = Date.now();
                    let delay = 2500; // Default: 2.5 seconds on success
                    let delayReason = 'success';
                    if (roundResult.error) {
                        if (roundResult.error.includes('Exception')) {
                            delay = 5000; // 5 seconds on exception
                            delayReason = 'exception';
                        } else {
                            delay = 300; // 0.3 seconds on failure
                            delayReason = 'failure';
                        }
                    }
                    
                    // Log delay calculation
                    const delayCalcMsg = `[ROUND ${roundNumber}] Delay calculation: ${delay}ms (reason: ${delayReason}) | Calculated at ${new Date(delayCalcStart).toISOString()}`;
                    if (window.reportStatus) window.reportStatus(delayCalcMsg);
                    
                    // Wait before next round - EXACT delay from round end
                    const delayStartTime = Date.now();
                    const delayStartMsg = `[ROUND ${roundNumber}] Delay START - waiting ${delay}ms | Started at ${new Date(delayStartTime).toISOString()}`;
                    if (window.reportStatus) window.reportStatus(delayStartMsg);
                    
                    // Precise blocking delay - ensures exact pause
                    const targetEndTime = delayStartTime + delay;
                    await sleep(delay);
                    
                    // Fine-tune to exact target time
                    let currentTime = Date.now();
                    while (currentTime < targetEndTime) {
                        // Busy-wait until exact target time
                        currentTime = Date.now();
                    }
                    
                    const delayEndTime = Date.now();
                    const actualDelay = delayEndTime - delayStartTime;
                    const delayDiff = actualDelay - delay;
                    const delayEndMsg = `[ROUND ${roundNumber}] Delay END - waited ${actualDelay}ms (expected: ${delay}ms, diff: ${delayDiff}ms) | Ended at ${new Date(delayEndTime).toISOString()}`;
                    if (window.reportStatus) window.reportStatus(delayEndMsg);
                    
                    // CRITICAL: Check if automation is still running before starting next round
                    if (!window.__snapchatAutomation || !window.__snapchatAutomation.isRunning) {
                        break;
                    }
                }
            }
            
            // Start the main loop
            if (window.__snapchatAutomation && window.__snapchatAutomation.isRunning) {
                mainLoop();
            }
            
            // Make functions available globally
            window.runRound = runRound;
            window.mainLoop = mainLoop;
        })();
        """
    
    def _update_sent_count(self, count):
        """Update sent count from JavaScript"""
        self.sent_count = count


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
        
        # Start working time timer (set before creating sessions so they can use it)
        self.start_time = time.time()
        self.timer_running = True
        
        # Launch new sessions
        for i in range(1, session_count + 1):
            user_data_dir = os.path.join(self.base_user_data_dir, f'session_{i}')
            session = ChromeSession(i, user_data_dir, self.friends_list.copy(), self._update_status, self.start_time)
            self.sessions[i] = session
            session.start()
            # Create session display widget
            self._create_session_widget(i)
        
        self.launch_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._update_status(0, f"Launched {session_count} session(s). Each will open Chrome - please login manually.")
        
        # Start working time display update
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
        # Check if message already has timestamp format [HH:MM:SS] or [HH:MM]
        if message.startswith('[') and ']' in message:
            # Extract timestamp part and message part
            bracket_end = message.find(']')
            timestamp_part = message[:bracket_end + 1]
            message_part = message[bracket_end + 1:].strip()
            
            # Add session prefix if needed
            if session_id > 0:
                status_msg = f"{timestamp_part} Session {session_id} {message_part}\n"
            else:
                status_msg = f"{timestamp_part} {message_part}\n"
        else:
            # Get working time (elapsed time since start) for all messages
            if self.start_time is not None:
                elapsed = time.time() - self.start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                # Fallback to clock time if working time not available
                time_str = datetime.now().strftime("%H:%M:%S")
            
            if session_id > 0:
                status_msg = f"[{time_str}] Session {session_id} {message}\n"
            else:
                status_msg = f"[{time_str}] {message}\n"
        self.status_text.insert(tk.END, status_msg)
        
        # Limit to last 30 messages
        lines = self.status_text.get("1.0", tk.END).split('\n')
        if len(lines) > 31:  # 30 messages + 1 empty line at end
            # Keep only the last 30 lines
            self.status_text.delete("1.0", f"{len(lines) - 30}.0")
        
        self.status_text.see(tk.END)
        # Update session display for active sessions
        if session_id > 0:
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
