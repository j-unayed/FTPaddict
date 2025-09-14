global current_page
global current_url
global current_page_type
global folders
global history
global donation_window
global progress_window
import sys
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import subprocess
import webbrowser
import re
import tkinter.font as tkfont
import threading
import pyperclip
import json
import urllib.parse
import time

progress_window = None
donation_window = None
history = []
current_page_type = None
current_url = None
root = None
folders = []
current_page = 0
chunk_size = 200
edit_window = None
# GLOBAL STATE FOR DOWNLOAD QUEUE
# ================================
download_queue = []  # List of (url, name, progress_var, label)
download_worker_running = False

def get_app_directory():
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return app_dir

def get_download_directory():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    download_folder = os.path.join(base_dir, 'Downloads')
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    return download_folder

def create_cache_folder():
    app_dir = get_app_directory()
    cache_dir = os.path.join(app_dir, 'FTPaddict_cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return cache_dir

def get_file_paths():
    cache_dir = create_cache_folder()
    SETTINGS_FILE = os.path.join(cache_dir, 'settings.txt')
    SHORTCUT_SETTINGS = os.path.join(cache_dir, 'SCsettings.txt')
    playlist_file = os.path.join(cache_dir, 'new_playlist.m3u')
    return (SETTINGS_FILE, SHORTCUT_SETTINGS, playlist_file)

SETTINGS_FILE, SHORTCUT_SETTINGS, playlist_file = get_file_paths()

def save_player_selection(selection):
    with open(SETTINGS_FILE, 'w') as f:
        f.write(selection)

def load_player_selection():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return f.read().strip()
    return 'PotPlayer'

def extract_links(base_url):
    """Extracts all folder and video links from the webpage."""
    try:
        response = requests.get(base_url)
        response.raise_for_status()
    except requests.RequestException:
        messagebox.showerror('Error', 'Failed to access the URL.')
        return ([], [])
    soup = BeautifulSoup(response.text, 'html.parser')
    folder_links = []
    video_links = []
    video_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.wmv', 'zip', 'rar', 'iso', 'apk', '7z', 'tar', 'gz', 'bz2', 'dmg', 'vmdk', 'img', 'exe', 'bin', 'pdf', 'jar', 'cab', 'msi', 'deb', 'rpm', 'xz', 'z', 'cso', 'nrg', 'udf', 'qcow2', 'vdi', 'ova', 'tgz', 'tbz', 'wim', 'vhd', 'vhdx', 'pkg', 'appx', 'xpi', 'crx', 'whl', 'egg', 'dmp', 'sfx', 'dmg', 'pup', 'esd', 'squashfs']
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        full_url = urljoin(base_url, href)
        name = a_tag.get_text(strip=True) or href.split('/')[-1]
        if not full_url.startswith(base_url):
            continue
        if any(href.lower().endswith(fmt) for fmt in video_formats):
            video_links.append((full_url, name))
        else:
            if href.endswith('/'):
                folder_links.append((full_url, name))
    return (folder_links, video_links)

def load_history_from_file():
    """Load the browsing history from a file."""
    global cache_history
    cache_dir = create_cache_folder()
    history_file = os.path.join(cache_dir, 'cache_history.json')
    if os.path.exists(history_file):
        with open(history_file, 'r') as file:
            cache_history = json.load(file)
    else:
        cache_history = []

def save_history_to_file():
    """Save the browsing history to a file."""
    cache_dir = create_cache_folder()
    history_file = os.path.join(cache_dir, 'cache_history.json')
    with open(history_file, 'w') as file:
        json.dump(cache_history, file)

def update_history(url):
    """Update the browsing history with the provided URL."""
    global cache_history
    name = extract_name_from_url(url)
    cache_history = [entry for entry in cache_history if entry['url'] != url]
    if len(cache_history) >= 100:
        cache_history.pop(0)
    cache_history.append({'name': name, 'url': url})
    save_history_to_file()

def extract_name_from_url(url):
    """Extract a meaningful name from the given URL."""
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path.strip('/')
    path_parts = path.split('/')
    if path_parts:
        name = urllib.parse.unquote(path_parts[-1])
        return name
    return ''

def validate_and_open_url(url):
    """Validate the URL and navigate to the appropriate page, trying both https and http."""
    global current_page, current_page_type, current_url, folders

    # Show temporary loading message
    message_window = tk.Toplevel(root, bg='#002F1A')
    message_window.overrideredirect(True)
    message_window.geometry('250x50')
    message_window.attributes('-topmost', True)
    window_x = root.winfo_x() + root.winfo_width() // 2 - 125
    window_y = root.winfo_y() + root.winfo_height() // 2 - 25
    message_window.geometry(f'250x50+{window_x}+{window_y}')
    message_label = tk.Label(message_window, text='Loading... trying HTTPS', font=('Arial', 12), fg='white', bg='#002F1A')
    message_label.pack(expand=True)
    message_window.attributes('-alpha', 0.85)
    root.update()

    def try_request(prefix):
        # If url already has http/https, don't re-add prefix
        if url.startswith("http://") or url.startswith("https://"):
            full_url = url
        else:
            full_url = f"{prefix}://{url}"

        try:
            message_label.config(text=f'Loading.. trying {prefix.lower()}..')
            root.update()
            response = requests.get(full_url, timeout=2)
            if response.status_code == 200:
                return full_url, response
        except requests.exceptions.RequestException:
            return None, None
        return None, None

    # Try HTTPS first, then HTTP
    tested_url, response = try_request("https")
    if not tested_url:
        tested_url, response = try_request("http")

    # Close loading window
    message_window.destroy()

    if tested_url and response:
        update_history(tested_url)
        folder_links, video_links = extract_links(tested_url)

        if len(video_links) > len(folder_links):
            if not history or history[-1].get('url') != tested_url or history[-1].get('type') != 'video':
                history.append({'type': 'video', 'url': tested_url, 'video_links': video_links})
            current_page_type = 'video'
            show_video_list(video_links)
        else:
            if folder_links:
                if not history or history[-1].get('url') != tested_url or history[-1].get('type') != 'folder':
                    history.append({'type': 'folder', 'url': tested_url, 'page': 0, 'folders': folder_links})
                current_page_type = 'folder'
                folders = folder_links
                current_page = 0
                show_folder_list()
            else:
                messagebox.showerror('Error', '0 Files')
        current_url = tested_url
    else:
        messagebox.showerror('Error', 'Server not responding!')


def show_folder_list():
    """Displays a paginated list of folders with a search bar."""
    clear_window()
    heading_label = tk.Label(root, text='Click on any folder to open', font=('Arial', 13, 'bold'), bg='#003546', fg='white', pady=8)
    heading_label.pack(fill='x', pady=(0, 10))

    import difflib
    import re

    def normalize(text):
        """Lowercase, remove non-alphanumerics, and strip spaces."""
        return re.sub(r'\W+', '', text.lower())

    def search_folders():
        def show_cap_message(msg, duration=2000):
            message_window = tk.Toplevel(root, bg='#002F1A')
            message_window.overrideredirect(True)
            message_window.geometry('250x50')
            message_window.attributes('-topmost', True)

            # Ensure root window geometry is updated
            root.update_idletasks()

            # Center message on root window
            window_x = root.winfo_x() + root.winfo_width() // 2 - 125
            window_y = root.winfo_y() + root.winfo_height() // 2 - 25
            message_window.geometry(f'250x50+{window_x}+{window_y}')

            message_label = tk.Label(
                message_window,
                text=msg,
                font=('Arial', 12),
                fg='white',
                bg='#002F1A'
            )
            message_label.pack(expand=True)
            message_window.attributes('-alpha', 0.85)

            # Auto-close after given duration (ms)
            root.after(duration, message_window.destroy)

        # Get user input
        raw_input = search_entry.get()

        # Input validation
        if len(raw_input) < 2:
            messagebox.showwarning("Input Error", "Please enter at least 2 characters.")
            return
        if raw_input[0] == ' ':
            messagebox.showwarning("Input Error", "Search term cannot start with a space.")
            return

        search_term = raw_input.lower()
        normalized_search = normalize(search_term)

        scored_folders = []

        for folder in folders:
            original_name = folder[1]
            name_lower = original_name.lower()
            normalized_name = normalize(name_lower)

            score = 0

            # Match priority
            if normalized_search == normalized_name:
                score = 100
            elif normalized_name.startswith(normalized_search):
                score = 90
            elif normalized_search in normalized_name:
                score = 75
            else:
                fuzzy_ratio = difflib.SequenceMatcher(None, normalized_search, normalized_name).ratio()
                if fuzzy_ratio > 0.5:
                    score = int(fuzzy_ratio * 100)

            if score > 0:
                scored_folders.append((score, folder))

        # Sort by score and name
        scored_folders.sort(key=lambda x: (-x[0], x[1][1].lower()))

        # Extract folder list
        filtered_folders = [f[1] for f in scored_folders]

        # Cap results to 900 and show message if needed
        if len(filtered_folders) > 900:
            filtered_folders = filtered_folders[:900]
            show_cap_message("Capped to 900 results")

        # Display results
        show_search_results(search_term, filtered_folders)

    def on_entry_click(event):
        """Clear the placeholder text when the entry gains focus."""
        if search_entry.get() == 'Find a folder...':
            search_entry.delete(0, tk.END)
            search_entry.config(fg='#002F1A')

    def on_focusout(event):
        """Restore the placeholder text if the entry is empty when it loses focus."""
        if search_entry.get() == '':
            search_entry.insert(0, 'Find a folder...')
            search_entry.config(fg='light gray')

    def show_context_menu(event):
        """Show the default context menu for the entry."""
        context_menu = tk.Menu(root, tearoff=0)
        context_menu.add_command(label='Cut', command=lambda: search_entry.event_generate('<<Cut>>'))
        context_menu.add_command(label='Copy', command=lambda: search_entry.event_generate('<<Copy>>'))
        context_menu.add_command(label='Paste', command=lambda: search_entry.event_generate('<<Paste>>'))
        context_menu.add_command(label='Delete', command=lambda: search_entry.delete(tk.ACTIVE, tk.END))
        context_menu.post(event.x_root, event.y_root)

    search_frame = tk.Frame(root, bg='#36454F')
    search_frame.pack(anchor='ne', pady=(5, 0), padx=20, fill='x')
    search_entry = tk.Entry(search_frame, fg='gray', width=30)
    search_entry.insert(0, 'Find a folder...')
    search_entry.pack(side='left', padx=(5, 10), pady=5)
    search_entry.bind('<FocusIn>', on_entry_click)
    search_entry.bind('<FocusOut>', on_focusout)
    search_entry.bind('<Button-3>', show_context_menu)
    search_button = tk.Button(search_frame, text='Search', font=('Arial', 10, 'bold'), bg='#002F1A', fg='white', command=search_folders, cursor='hand2', borderwidth=1)
    search_button.pack(side='left', padx=(0, 10), pady=5)
    search_entry.bind('<Return>', lambda event: search_button.invoke())
    display_folder_list()
    nav_frame = tk.Frame(root, bg='#36454F')
    nav_frame.pack(pady=10, fill='x')
    back_frame = tk.Frame(nav_frame, bg='#36454F')
    back_frame.pack(pady=0, padx=(25, 10), side='left')
    back_button = tk.Button(back_frame, text='Back', font=('Arial', 11, 'bold'), bg='#002F1A', fg='white', command=navigate_back, cursor='hand2', borderwidth=1)
    back_button.pack(side='left', padx=(0, 5), expand=True)
    go_home_button = tk.Button(nav_frame, text='Homepage', font=('Arial', 11, 'bold'), fg='white', bg='#002F1A', command=show_homepage, cursor='hand2')
    go_home_button.pack(side='left', padx=(0, 5), pady=5)
    copy_frame = tk.Frame(nav_frame, bg='#36454F')
    copy_frame.pack(pady=0, padx=20, side='right')
    open_url_button = tk.Button(copy_frame, text='Copy URL', font=('Arial', 11, 'bold'), bg='#002F1A', fg='white', command=find_open_url, cursor='hand2')
    open_url_button.pack(side='right', padx='10')
    footer_frame = tk.Frame(root, bg='#003546')
    footer_frame.pack(side='bottom', fill='x', pady=0)
    footer_label_left = tk.Label(footer_frame, text='Developed by', font=('Arial', 10, 'bold'), bg='#008080', fg='white')
    footer_label_left.pack(side='left', anchor='w', padx=0)
    credit_link = tk.Label(footer_frame, text='Md. Junayed', font=('Arial', 10, 'bold'), fg='white', cursor='hand2', bg='#008080')
    credit_link.pack(side='left', anchor='w')
    credit_link.bind('<Button-1>', lambda e: webbrowser.open('https://facebook.com/junayed733'))
    buy_me_coffee = tk.Label(footer_frame, text='Buy me a coffee', font=('Arial', 10, 'underline', 'bold'), fg='light gray', cursor='hand2', bg='#003546')
    buy_me_coffee.pack(side='left', padx=5, anchor='center')
    buy_me_coffee.bind('<Button-1>', lambda e: open_donation_window())
    version_label_right = tk.Label(footer_frame, text='FTPaddict v11.0', font=('Arial', 10, 'bold'), anchor='e', fg='white', bg='#008080')
    version_label_right.pack(side='right', padx=0)
    update_version_label = tk.Label(footer_frame, text='Check for Update', font=('Arial', 10, 'underline', 'bold'), fg='light gray', cursor='hand2', bg='#003546')
    update_version_label.pack(side='right', padx=(0, 5))
    update_version_label.bind('<Button-1>', lambda e: webbrowser.open('https://github.com/j-unayed/FTPaddict/releases/tag/ftpaddict'))

def show_search_results(search_term, filtered_folders):
    """Displays the search results on the same page without pagination."""
    if not filtered_folders:
        messagebox.showerror('Search Results', '0 Folders Found')
        return

    clear_window()

    if not history or history[-1].get('type') != 'search_results':
        history.append({
            'type': 'search_results',
            'search_term': search_term,
            'filtered_folders': filtered_folders
        })

    heading_label = tk.Label(root, text=f"Results for '{search_term}'", font=('Arial', 13, 'bold'), bg='#003546', fg='white', pady=10)
    heading_label.pack(fill='x', pady=(0, 10))

    frame = tk.Frame(root, bg='#36454F')
    frame.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(frame, bg='#36454F', highlightthickness=0)
    scrollbar = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)

    scrollable_frame = tk.Frame(canvas, bg='#36454F')
    scrollable_frame.config(padx=15, pady=15)
    scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    # 🌀 Mousewheel scroll only when hovering inside canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(-1 * int(event.delta / 120), 'units')

    def _bind_mousewheel(event):
        canvas.bind_all('<MouseWheel>', _on_mousewheel)

    def _unbind_mousewheel(event):
        canvas.unbind_all('<MouseWheel>')

    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)

    # Populate buttons
    for i, (url, name) in enumerate(filtered_folders):
        button = tk.Button(scrollable_frame, text=f'{i+1}. {name}', font=('Arial', 11, 'bold'),
                           fg='white', bg='#008080', anchor='w', cursor='hand2', padx=10,
                           command=lambda url=url: validate_and_open_url(url if url.startswith("http") else f"http://{url}"))
        button.pack(fill='x', pady=(0, 3), padx=10, anchor='w')

    # Footer & Back
    root.unbind('<Return>')

    nav_frame = tk.Frame(root, bg='#36454F')
    nav_frame.pack(pady=10, fill='x')
    back_frame = tk.Frame(nav_frame, bg='#36454F')
    back_frame.pack(pady=0, padx=(25, 10), side='left')
    back_button = tk.Button(back_frame, text='Back', font=('Arial', 11, 'bold'), bg='#002F1A', fg='white',
                            command=navigate_back, cursor='hand2', borderwidth=1)
    back_button.pack(side='left', padx=(0, 5), expand=True)

    footer_frame = tk.Frame(root, bg='#003546')
    footer_frame.pack(side='bottom', fill='x', pady=0)

    footer_label_left = tk.Label(footer_frame, text='Developed by', font=('Arial', 10, 'bold'),
                                 bg='#008080', fg='white')
    footer_label_left.pack(side='left', anchor='w', padx=0)

    credit_link = tk.Label(footer_frame, text='Md. Junayed', font=('Arial', 10, 'bold'),
                           fg='white', cursor='hand2', bg='#008080')
    credit_link.pack(side='left', anchor='w')
    credit_link.bind('<Button-1>', lambda e: webbrowser.open('https://facebook.com/junayed733'))

    buy_me_coffee = tk.Label(footer_frame, text='Buy me a coffee', font=('Arial', 10, 'underline', 'bold'),
                             fg='light gray', cursor='hand2', bg='#003546')
    buy_me_coffee.pack(side='left', padx=5, anchor='center')
    buy_me_coffee.bind('<Button-1>', lambda e: open_donation_window())

    version_label_right = tk.Label(footer_frame, text='FTPaddict v11.0', font=('Arial', 10, 'bold'),
                                   anchor='e', fg='white', bg='#008080')
    version_label_right.pack(side='right', padx=0)

    update_version_label = tk.Label(footer_frame, text='Check for Update',
                                    font=('Arial', 10, 'underline', 'bold'), fg='light gray',
                                    cursor='hand2', bg='#003546')
    update_version_label.pack(side='right', padx=(0, 5))
    update_version_label.bind('<Button-1>', lambda e: webbrowser.open('https://github.com/j-unayed/FTPaddict/releases/tag/ftpaddict'))


def display_folder_list():
    """Displays folders with pagination, scrollbar, media player selection, and a 'Open URL in browser' button."""
    frame = tk.Frame(root, bg='#36454F')
    frame.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(frame, bg='#36454F', highlightthickness=0)
    scrollbar = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)

    scrollable_frame = tk.Frame(canvas, bg='#36454F')
    scrollable_frame.config(padx=15, pady=10)

    scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    # 🌀 Scroll on mousewheel only when cursor is over the canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(-1 * int(event.delta / 120), 'units')

    def _bind_mousewheel(event):
        canvas.bind_all('<MouseWheel>', _on_mousewheel)

    def _unbind_mousewheel(event):
        canvas.unbind_all('<MouseWheel>')

    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)


    def open_url_in_browser():
        """Copy the last URL from history to the clipboard."""
        url = get_last_url_from_history()
        if url:
            pyperclip.copy(url)
            show_temp_message()
        else:
            messagebox.showerror('Error', 'No URL found in history.')

    start = current_page * chunk_size
    end = start + chunk_size  # Fixed: Simplified pagination
    paginated_folders = folders[start:end]
    for i, (url, name) in enumerate(paginated_folders):
        button = tk.Button(scrollable_frame, text=f'{i + 1}. {name}', font=('Arial', 11, 'bold'), fg='white', bg='#008080', anchor='w', cursor='hand2', command=lambda url=url: validate_and_open_url(url), padx=10)
        button.grid(row=i, column=0, padx=10, pady=(3, 0), sticky='ew')
    canvas.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    frame.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(-1 * (e.delta // 120), 'units'))  # Fixed: Simplified scroll logic
    frame.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
    frame.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))
    pagination_frame = tk.Frame(root, pady=10, bg='#36454F')
    pagination_frame.pack()
    total_folders_info = tk.Label(pagination_frame, text=f'Total folders: {len(folders)}', font=('Arial', 10, 'bold'), fg='white', bg='#36454F')
    total_folders_info.pack(side='left', padx=10)
    prev_button = tk.Button(pagination_frame, text='Previous', command=go_to_previous_page, state='normal' if current_page > 0 else 'disabled', font=('Arial', 10, 'bold'), bg='#003546', fg='white', relief='raised', bd=2, cursor='hand2')
    prev_button.pack(side='left', padx=5)
    next_button = tk.Button(pagination_frame, text='Next', command=go_to_next_page, state='normal' if end < len(folders) else 'disabled', font=('Arial', 10, 'bold'), bg='#003546', fg='white', relief='raised', bd=2, cursor='hand2')
    next_button.pack(side='left', padx=5)
    num_pages = (len(folders) + chunk_size - 1) // chunk_size  # Fixed: Corrected pagination calculation
    page_info = tk.Label(pagination_frame, text='Go to page:', font=('Arial', 10, 'bold'), bg='#36454F', fg='white')
    page_info.pack(side='left', padx=5)
    page_options = list(range(1, num_pages + 1))
    page_dropdown = ttk.Combobox(pagination_frame, values=page_options, width=4, state='readonly', cursor='hand2')
    page_dropdown.set(current_page + 1)  # Fixed: Set to current page
    page_dropdown.pack(side='left', padx=5)
    total_pages_info = tk.Label(pagination_frame, text=f'of {num_pages}', font=('Arial', 10, 'bold'), bg='#36454F', fg='white')
    total_pages_info.pack(side='left', padx=5)
    page_dropdown.bind('<<ComboboxSelected>>', lambda event: go_to_page(int(page_dropdown.get()) - 1))

def go_to_page(page_num):
    """Navigate to a specific page of the folder list."""
    global current_page
    current_page = page_num
    if history and history[-1]['type'] == 'folder':
        history[-1]['page'] = current_page
    else:
        history.append({'type': 'folder', 'page': current_page, 'folders': folders.copy()})
    show_folder_list()

def go_to_previous_page():
    """Navigate to the previous page of the folder list."""
    global current_page
    if current_page > 0:
        current_page -= 1  # Fixed: Corrected decrement
        if history and history[-1]['type'] == 'folder':
            history[-1]['page'] = current_page
        else:
            history.append({'type': 'folder', 'page': current_page, 'folders': folders.copy()})
        show_folder_list()

def go_to_next_page():
    """Navigate to the next page of the folder list."""
    global current_page
    if current_page * chunk_size < len(folders):  # Fixed: Corrected condition
        current_page += 1  # Fixed: Corrected increment
        if history and history[-1]['type'] == 'folder':
            history[-1]['page'] = current_page
        else:
            history.append({'type': 'folder', 'page': current_page, 'folders': folders.copy()})
        show_folder_list()

def show_video_list(video_links):
    """Displays a list of videos with a header."""
    clear_window()
    header_label = tk.Label(root, text='Click on any tab to Stream or Download', font=('Arial', 13, 'bold'), bg='#003546', fg='white', pady=10)
    header_label.pack(fill='x', pady=(0, 10))
    display_video_list(video_links)
    nav_frame = tk.Frame(root, bg='#36454F')
    nav_frame.pack(pady=10, fill='x')
    back_frame = tk.Frame(nav_frame, bg='#36454F')
    back_frame.pack(pady=0, padx=(25, 10), side='left')
    back_button = tk.Button(back_frame, text='Back', font=('Arial', 11, 'bold'), bg='#002F1A', fg='white', command=navigate_back, cursor='hand2', borderwidth=1)
    back_button.pack(side='left', padx=(0, 5), expand=True)
    go_home_button = tk.Button(nav_frame, text='Homepage', font=('Arial', 11, 'bold'), fg='white', bg='#002F1A', command=show_homepage, cursor='hand2')
    go_home_button.pack(side='left', padx=(0, 5), pady=5)
    copy_frame = tk.Frame(nav_frame, bg='#36454F')
    copy_frame.pack(pady=0, padx=20, side='right')
    open_url_button = tk.Button(copy_frame, text='Copy URL',font=('Arial', 11, 'bold'), bg='#002F1A', fg='white', command=find_open_url, cursor='hand2')
    open_url_button.pack(side='right', padx='10')
    footer_frame = tk.Frame(root, bg='#003546')
    footer_frame.pack(side='bottom', fill='x', pady=0)
    footer_label_left = tk.Label(footer_frame, text='Developed by', font=('Arial', 10, 'bold'), bg='#008080', fg='white')
    footer_label_left.pack(side='left', anchor='w', padx=0)
    credit_link = tk.Label(footer_frame, text='Md. Junayed', font=('Arial', 10, 'bold'), fg='white', cursor='hand2', bg='#008080')
    credit_link.pack(side='left', anchor='w')
    credit_link.bind('<Button-1>', lambda e: webbrowser.open('https://facebook.com/junayed733'))
    buy_me_coffee = tk.Label(footer_frame, text='Buy me a coffee', font=('Arial', 10, 'underline', 'bold'), fg='light gray', cursor='hand2', bg='#003546')
    buy_me_coffee.pack(side='left', padx=5, anchor='center')
    buy_me_coffee.bind('<Button-1>', lambda e: open_donation_window())
    version_label_right = tk.Label(footer_frame, text='FTPaddict v11.0', font=('Arial', 10, 'bold'), anchor='e', fg='white', bg='#008080')
    version_label_right.pack(side='right', padx=0)
    update_version_label = tk.Label(footer_frame, text='Check for Update', font=('Arial', 10, 'underline', 'bold'), fg='light gray', cursor='hand2', bg='#003546')
    update_version_label.pack(side='right', padx=(0, 5))
    update_version_label.bind('<Button-1>', lambda e: webbrowser.open('https://github.com/j-unayed/FTPaddict/releases/tag/ftpaddict'))

def get_last_url_from_history():
    if history:
        last_entry = history[-1]
        if 'url' in last_entry:
            return last_entry['url']
    return None

def find_open_url():
    url = get_last_url_from_history()
    if url:
        pyperclip.copy(url)
        show_temp_message()
    else:
        messagebox.showerror('Error', 'No URL found in history.')

def show_temp_message():
    """Shows a temporary message window without a title bar."""
    message_window = tk.Toplevel(root, bg='#36454F')
    message_window.overrideredirect(True)
    message_window.geometry('200x50')
    message_window.configure(bg='#002F1A')
    window_x = root.winfo_x() + root.winfo_width() // 2 - 100  # Fixed: Corrected arithmetic
    window_y = root.winfo_y() + root.winfo_height() // 2 - 25  # Fixed: Corrected arithmetic
    message_window.geometry(f'200x50+{window_x}+{window_y}')
    message_label = tk.Label(message_window, text='URL copied to clipboard!', font=('Arial', 12), fg='white', bg='#002F1A')
    message_label.pack(expand=True)
    message_window.attributes('-alpha', 0.8)
    message_window.after(1500, message_window.destroy)

def is_connected():
    """Check if the internet is available by pinging a lightweight server."""
    try:
        requests.get('https://1.1.1.1', timeout=2)
        return True
    except requests.ConnectionError:
        return False
    except requests.Timeout:
        return False

def has_streamable_formats(video_links):
    streamable_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.wmv']
    return any(link[0].lower().endswith(fmt) for link in video_links for fmt in streamable_formats)

def display_video_list(video_links):
    """Displays videos with tabs for streaming and downloading."""
    # Removed: video_links = {}  # Fixed: Keep video_links as passed list

    def create_stream_tab():
        """Create the Stream tab with existing functionality."""
        stream_tab = ttk.Frame(notebook)
        notebook.add(stream_tab, text='Stream')

        frame = tk.Frame(stream_tab, bg='#36454F')
        frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(frame, bg='#36454F', highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)

        scrollable_frame = tk.Frame(canvas, bg='#36454F')
        scrollable_frame.config(padx=10, pady=10)

        scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvases[scrollable_frame] = canvas
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        # 🌀 Scroll on mousewheel only when cursor is inside
        def _on_mousewheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), 'units')

        def _bind_mousewheel(event):
            canvas.bind_all('<MouseWheel>', _on_mousewheel)
            canvas.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))
            canvas.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))

        def _unbind_mousewheel(event):
            canvas.unbind_all('<MouseWheel>')
            canvas.unbind_all('<Button-4>')
            canvas.unbind_all('<Button-5>')

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        selected_player = load_player_selection()
        player_var = tk.StringVar(value=selected_player)

        def on_player_change():
            save_player_selection(player_var.get())
            selected_player = player_var.get()
            for button in radio_buttons:
                if button.cget('text') == selected_player:
                    button.config(relief=tk.SUNKEN, fg='black')
                else:
                    button.config(relief=tk.RAISED, fg='white')
        bold_font = tkfont.Font(weight='bold')
        label_frame = tk.Frame(frame, bg='#36454F')
        label_frame.pack(pady=0, padx=10, anchor='nw')
        label1 = tk.Label(label_frame, text='Please select your preferred video player', fg='white', bg='#36454F', font=('Arial', 11, 'bold'))
        label1.pack(side='left', padx=(0, 10), pady=10)
        label2 = tk.Label(label_frame, text='(It must be installed in default installation path)', fg='white', bg='#36454F')
        label2.pack(side='left', pady=10)
        button_frame = tk.Frame(frame, bg='#36454F')
        button_frame.pack(pady=0, anchor='center')
        radio_buttons = [
            tk.Radiobutton(button_frame, text='VLC', variable=player_var, value='VLC', command=on_player_change, font=bold_font, width=10, height=1, cursor='hand2', fg='white', bg='#36454F', indicatoron=False),
            tk.Radiobutton(button_frame, text='PotPlayer', variable=player_var, value='PotPlayer', command=on_player_change, font=bold_font, width=10, height=1, cursor='hand2', fg='white', bg='#36454F', indicatoron=False),
            tk.Radiobutton(button_frame, text='KMPlayer', variable=player_var, value='KMPlayer', command=on_player_change, font=bold_font, width=10, height=1, cursor='hand2', fg='white', bg='#36454F', indicatoron=False)
        ]
        for button in radio_buttons:
            button.pack(side='left', padx=30)
        on_player_change()
        instruction_frame = tk.Frame(frame, bg='#36454F')
        instruction_frame.pack(padx=10, pady=5, anchor='nw')
        label3 = tk.Label(instruction_frame, text='Click on any video below to start streaming!', fg='white', bg='#36454F', font=('Arial', 12, 'bold'))
        label3.pack(side='left', padx=(0, 10))
        for i, (url, name) in enumerate(video_links):
            button = tk.Button(scrollable_frame, text=f'{i+1}. {name}', font=('Arial', 11, 'bold'), fg='white', bg='#008080', anchor='w', cursor='hand2', padx=10, command=lambda i=i: add_to_playlist_and_open(i, video_links, player_var.get()))
            button.pack(fill='x', pady=(0, 3), padx=10, anchor='w')
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def create_download_tab():
        """Create the Download tab with input boxes for range and download button."""
        import tkinter as tk
        from tkinter import ttk, messagebox
        import tkinter.font as tkfont
        import os, threading, time, requests

        global download_queue, download_worker_running
        download_tab = ttk.Frame(notebook)
        notebook.add(download_tab, text='Download')

        list_frame = tk.Frame(download_tab, bg='#36454F')
        list_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(list_frame, highlightthickness=0, bg='#36454F')
        scrollbar = tk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        video_list_frame = tk.Frame(canvas, bg='#36454F')
        video_list_frame.config(padx=10, pady=10)

        video_list_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvases[video_list_frame] = canvas
        canvas.create_window((0, 0), window=video_list_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), 'units')

        def _bind_mousewheel(event):
            canvas.bind_all('<MouseWheel>', _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all('<MouseWheel>')

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        class DownloadTask:
            def __init__(self, url, name, label, progress_var, progress_bar, button_frame):
                self.url = url
                self.name = name
                self.label = label
                self.progress_var = progress_var
                self.progress_bar = progress_bar
                self.button_frame = button_frame
                self.paused = False
                self.canceled = False
                self.finished = False
                self.create_buttons()

            def create_buttons(self):
                small_font = ("Arial", 11, "bold")
                self.pause_btn = tk.Button(self.button_frame, text=" ⏸ ", width=2,  cursor="hand2",bg="#008080", fg="white",
                                           command=self.pause, state="normal", font=small_font)
                self.resume_btn = tk.Button(self.button_frame, text=" ▷ ", width=2,  cursor="hand2",bg="#008080", fg="white",
                                            command=self.resume, state="disabled",font=small_font)
                self.cancel_btn = tk.Button(self.button_frame, text=" ✖ ", width=2,  cursor="hand2",bg="#008080", fg="white",
                                            command=self.cancel, state="normal",font=small_font)
                self.pause_btn.pack(side="left", padx=2)
                self.resume_btn.pack(side="left", padx=2)
                self.cancel_btn.pack(side="left", padx=2)

            def pause(self):
                self.paused = True
                self.pause_btn.config(state="disabled")
                self.resume_btn.config(state="normal")

            def resume(self):
                self.paused = False
                self.pause_btn.config(state="normal")
                self.resume_btn.config(state="disabled")

            def cancel(self):
                self.canceled = True
                self.pause_btn.config(state="disabled")
                self.resume_btn.config(state="disabled")
                self.cancel_btn.config(state="disabled")

        def create_progress_window():
            global progress_window, progress_frame
            if progress_window is not None and progress_window.winfo_exists():
                return progress_window, progress_frame

            progress_window = tk.Toplevel()
            progress_window.title('Download Progress')
            progress_window.geometry('600x450')
            progress_window.resizable(False, False)
            icon_path = os.path.join(os.path.dirname(__file__), 'ftpaddict.ico')
            progress_window.iconbitmap(default=icon_path)


            progress_canvas = tk.Canvas(progress_window, height=400, width=550, bg='#36454F')
            progress_scrollbar = ttk.Scrollbar(progress_window, orient='vertical', command=progress_canvas.yview)
            progress_canvas.configure(yscrollcommand=progress_scrollbar.set)

            progress_frame = tk.Frame(progress_canvas, bg='#36454F')
            progress_frame.bind('<Configure>',
                                lambda e: progress_canvas.configure(scrollregion=progress_canvas.bbox('all')))
            canvases[progress_frame] = progress_canvas
            progress_canvas.create_window((0, 0), window=progress_frame, anchor='nw')
            progress_canvas.pack(side='left', fill='both', expand=True)
            progress_scrollbar.pack(side='right', fill='y')

            def _on_mousewheel(event):
                progress_canvas.yview_scroll(-1 * int(event.delta / 120), 'units')

            def _bind_mousewheel(event):
                progress_canvas.bind_all('<MouseWheel>', _on_mousewheel)

            def _unbind_mousewheel(event):
                progress_canvas.unbind_all('<MouseWheel>')

            progress_canvas.bind("<Enter>", _bind_mousewheel)
            progress_canvas.bind("<Leave>", _unbind_mousewheel)

            return progress_window, progress_frame

        def create_progress_label(progress_frame, name, url):
            # --- Label ---
            label = tk.Label(progress_frame,
                             text=f'Downloading: {name}\n[0%] (0.00 MB / ? MB)',
                             fg='white',
                             bg='#36454F',
                             anchor='w',
                             justify='left',
                             wraplength=540,)
            label.pack(fill='x', pady=5, padx=10)

            # --- Progress bar ---
            style = ttk.Style()
            style.theme_use('default')  # make sure we can customize
            style.configure("Classic.Horizontal.TProgressbar",
                            troughcolor='#d9d9d9',  # background
                            background='#003546',  # fill color
                            thickness=22,  # thin block-like bar
                            relief='flat')

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame,
                                           variable=progress_var,
                                           maximum=100,
                                           length=480,
                                           style="Classic.Horizontal.TProgressbar",
                                           mode='determinate')
            progress_bar.pack(pady=7, padx=10, anchor='w')

            # --- Button frame ---
            button_frame = tk.Frame(progress_frame, bg='#36454F')
            button_frame.pack(pady=(10, 10), padx=10, anchor="w")

            # --- Task object ---
            task = DownloadTask(url, name, label, progress_var, progress_bar, button_frame)
            return task

        def start_download_worker():
            global download_queue, download_worker_running

            def worker():
                global download_worker_running
                while download_queue:
                    task = download_queue.pop(0)
                    download_process(task)
                download_worker_running = False

            if not download_worker_running:
                download_worker_running = True
                threading.Thread(target=worker, daemon=True).start()

        def enqueue_download(url, name):
            progress_window, progress_frame = create_progress_window()
            task = create_progress_label(progress_frame, name, url)
            download_queue.append(task)
            start_download_worker()

        def download_process(task, max_retries=10):
            retries = 0
            url, name = task.url, task.name
            label, progress_var = task.label, task.progress_var
            if label.winfo_exists():
                label.config(text=f'Downloading: {name}\n[0%] (0.00 MB / ? MB)')
                progress_var.set(0)

            while retries <= max_retries and not task.canceled:
                try:
                    if not label.winfo_exists():
                        return False

                    while task.paused and not task.canceled:
                        time.sleep(0.2)

                    if task.canceled:
                        label.config(text=f"Download cancelled: {name}.")
                        return False

                    download_dir = get_download_directory()
                    filename = os.path.join(download_dir, name)
                    file_exists = os.path.exists(filename)
                    file_size = os.path.getsize(filename) if file_exists else 0
                    response_head = requests.head(url)
                    total_size = int(response_head.headers.get('content-length', 0))

                    if file_exists and file_size >= total_size:
                        label.config(
                            text=f'Already downloaded:{name}.\n[100%] ({file_size / 1048576:.2f} MB / {total_size / 1048576:.2f} MB)')
                        progress_var.set(100)
                        task.finished = True
                        task.pause_btn.config(state="disabled")
                        task.resume_btn.config(state="disabled")
                        task.cancel_btn.config(state="disabled")
                        return True

                    headers = {'Range': f'bytes={file_size}-'} if file_exists else {}
                    response = requests.get(url, headers=headers, stream=True)

                    if response.status_code == 416:
                        label.config(
                            text=f'Already downloaded: {name}.\n[100%] ({file_size / 1048576:.2f} MB / {total_size / 1048576:.2f} MB)')
                        progress_var.set(100)
                        task.finished = True
                        task.pause_btn.config(state="disabled")
                        task.resume_btn.config(state="disabled")
                        task.cancel_btn.config(state="disabled")
                        return True

                    if response.status_code in (200, 206):
                        with open(filename, 'ab') as file:
                            downloaded = file_size
                            last_percentage = (downloaded / total_size) * 100 if total_size > 0 else 0
                            for chunk in response.iter_content(chunk_size=1024):
                                if task.canceled:
                                    label.config(text=f"Download cancelled: {name}.")
                                    return False
                                while task.paused and not task.canceled:
                                    time.sleep(0.2)
                                if chunk:
                                    file.write(chunk)
                                    downloaded += len(chunk)
                                    percentage = (downloaded / total_size) * 100 if total_size > 0 else 0
                                    if percentage - last_percentage >= 0.5:
                                        last_percentage = percentage
                                        progress_var.set(min(percentage, 100))
                                        if label.winfo_exists():
                                            label.config(
                                                text=f'Downloading: {name}.\n[{percentage:.1f}%] ({downloaded / 1048576:.2f} MB / {total_size / 1048576:.2f} MB)')
                                        else:
                                            return False
                            if label.winfo_exists():
                                label.config(
                                    text=f'Download completed: {name}.\n[100%] ({downloaded / 1048576:.2f} MB / {total_size / 1048576:.2f} MB)')
                            task.finished = True
                            task.pause_btn.config(state="disabled")
                            task.resume_btn.config(state="disabled")
                            task.cancel_btn.config(state="disabled")
                            return True
                    else:
                        if label.winfo_exists():
                            label.config(text=f'Download failed: {name}.')
                        return False
                except Exception as e:
                    retries += 1
                    if retries <= max_retries:
                        if label.winfo_exists():
                            label.config(text=f'Downloading: {name} - Retrying... ({retries}/{max_retries})')
                        time.sleep(3)
                    else:
                        if label.winfo_exists():
                            label.config(text=f'Download failed: {name} - Maximum retries reached.')
                        return False

        def download_videos(video_links, start, end):
            """Queue multiple videos for download."""
            if not is_connected():
                messagebox.showerror('Connection Error', 'No internet connection available.')
                return

            for i in range(start - 1, end):
                url, name = video_links[i]
                enqueue_download(url, name)

        def on_download_button_click(video_links, from_entry, to_entry):
            """Handle the Download Now button click event."""
            try:
                start = int(from_entry.get())
                end = int(to_entry.get())
                if start <= 0 or end <= 0 or start > end or end > len(video_links):
                    raise ValueError('Invalid range')
                download_videos(video_links, start, end)
            except ValueError:
                messagebox.showerror('Input Error', 'Invalid range')

        def on_download_all_button_click(video_links):
            """Handle the Download All button click event."""
            try:
                download_videos(video_links, 1, len(video_links))
            except Exception as e:
                messagebox.showerror('Download Error', str(e))

        def download_single_video(url, name):
            """Queue a single video for download."""
            enqueue_download(url, name)

        def on_video_button_click(url, name):
            """Handle the single video download button click event."""
            if not is_connected():
                messagebox.showerror('Connection Error', 'No internet connection available.')
            else:
                download_single_video(url, name)

        # --- existing UI creation (unchanged below except enqueue calls) ---
        download_frame = tk.Frame(list_frame, bg='#36454F')
        download_frame.pack(padx=10, pady=5, anchor='nw', fill='x')
        if has_streamable_formats(video_links):
            from_label = tk.Label(download_frame, text='Download videos from', fg='white', bg='#36454F',
                                  font=('Arial', 11, 'bold'))
        else:
            from_label = tk.Label(download_frame, text='Download files from', fg='white', bg='#36454F',
                                  font=('Arial', 11, 'bold'))
        from_label.pack(side='left')
        from_entry = tk.Entry(download_frame, width=5)
        to_label = tk.Label(download_frame, text='to', fg='white', bg='#36454F', font=('Arial', 11, 'bold'))
        from_entry.pack(side='left', padx=5)
        to_label.pack(side='left')
        to_entry = tk.Entry(download_frame, width=5)
        download_button = tk.Button(download_frame, text='Download', bg='#003546', fg='white', bd=1, relief='solid',
                                    highlightthickness=1,
                                    command=lambda: on_download_button_click(video_links, from_entry, to_entry),
                                    cursor='hand2')
        download_all_button = tk.Button(download_frame, text='Download All', bg='#002F1A', fg='white', bd=1,
                                        relief='solid', highlightthickness=1,
                                        command=lambda: on_download_all_button_click(video_links), cursor='hand2')
        to_entry.pack(side='left', padx=5)
        download_button.pack(side='left', padx=5)
        download_all_button.pack(side='left', padx=50)
        location_frame = tk.Frame(list_frame, bg='#36454F')
        location_frame.pack(padx=10, pady=5, anchor='w')
        if has_streamable_formats(video_links):
            location_label = tk.Label(location_frame,
                                      text='The videos will be downloaded to the same folder where FTPaddict_v11_0.exe is located!',
                                      fg='white', bg='#36454F')
        else:
            location_label = tk.Label(location_frame,
                                      text='The files will be downloaded to the same folder where FTPaddict_v11_0.exe is located!',
                                      fg='white', bg='#36454F')
        location_label.pack(side='left')
        ins_frame = tk.Frame(list_frame, bg='#36454F')
        ins_frame.pack(padx=10, pady=5, anchor='w')
        if has_streamable_formats(video_links):
            ins_label = tk.Label(ins_frame, text='Click on any video below to start downloading!',
                                 font=('Arial', 12, 'bold'), fg='white', bg='#36454F')
        else:
            ins_label = tk.Label(ins_frame, text='\nClick on any file below to start downloading!',
                                 font=('Arial', 12, 'bold'), fg='white', bg='#36454F')
        ins_label.pack(side='left')
        for i, (url, name) in enumerate(video_links):
            video_button = tk.Button(video_list_frame, text=f'{i + 1}. {name}', font=('Arial', 11, 'bold'), fg='white',
                                     bg='#008080', anchor='w', cursor='hand2', padx=10,
                                     command=lambda url=url, name=name: on_video_button_click(url, name))
            video_button.pack(fill='x', pady=(0, 3), padx=10, anchor='w')
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        to_entry.bind('<Return>', lambda event: download_button.invoke())

    def scroll_canvas(e):
        for frame, canvas in list(canvases.items()):
            try:
                if frame.winfo_ismapped():
                    canvas.yview_scroll(-1 * (e.delta // 120), 'units')  # Fixed: Simplified scroll logic
            except tk.TclError:
                del canvases[frame]

    canvases = {}  # Initialize canvases dictionary
    root.bind_all('<MouseWheel>', scroll_canvas)  # Fixed: Bind to function, not notebook
    root.bind_all('<Button-4>', lambda e: scroll_canvas(e))
    root.bind_all('<Button-5>', lambda e: scroll_canvas(e))
    style = ttk.Style()
    bold_font = ('TkDefaultFont', 12, 'bold')
    style.configure('Custom.TNotebook.Tab', foreground='black', padding=[0, 0], font=bold_font, highlightthickness=0)
    style.map('Custom.TNotebook.Tab', foreground=[('selected', 'blue')])
    notebook = ttk.Notebook(root, style='Custom.TNotebook')
    notebook.pack(fill=tk.BOTH, expand=True)
    if has_streamable_formats(video_links):
        create_stream_tab()
    create_download_tab()

def add_to_playlist_and_open(index, video_links, selected_player):
    """Adds videos to playlist and opens with selected player priority."""
    playlist_videos = video_links[index:] + video_links[:index]  # Fixed: Corrected concatenation
    with open(playlist_file, 'w') as f:
        f.write('#EXTM3U\n')
        for url, title in playlist_videos:
            f.write(f'#EXTINF:-1,{title}\n{url}\n')
    if selected_player == 'VLC':
        if open_with_vlc(playlist_file):
            return
        if open_with_potplayer(playlist_file):
            return
        if open_with_kmplayer(playlist_file):
            return
    else:
        if selected_player == 'PotPlayer':
            if open_with_potplayer(playlist_file):
                return
            if open_with_vlc(playlist_file):
                return
            if open_with_kmplayer(playlist_file):
                return
        else:
            if selected_player == 'KMPlayer':
                if open_with_kmplayer(playlist_file):
                    return
                if open_with_vlc(playlist_file):
                    return
                if open_with_potplayer(playlist_file):
                    return
    open_with_default_app(playlist_file)
    return

def find_vlc_path():
    """Finds the path to VLC in common installation directories."""
    username = os.getlogin()
    paths = [
        'C:\\Program Files\\VideoLAN\\VLC\\vlc.exe',
        'C:\\Program Files (x86)\\VideoLAN\\VLC\\vlc.exe',
        'C:\\Program Files\\VLC\\vlc.exe',
        'C:\\Program Files (x86)\\VLC\\vlc.exe',
        'C:\\VLC\\vlc.exe',
        'C:\\VideoLAN\\VLC\\vlc.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\VideoLAN\\VLC', 'vlc.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\VideoLAN\\VLC', 'vlc.exe')
    ]
    if sys.platform == 'darwin':
        paths.extend(['/Applications/VLC.app/Contents/MacOS/VLC', '/usr/local/bin/vlc', '/opt/local/bin/vlc'])
    for path in paths:
        if os.path.isfile(path):
            return path
    return None

def find_potplayer_path():
    """Finds the path to PotPlayer in common installation directories."""
    username = os.getlogin()
    paths = [
        'C:\\Program Files\\DAUM\\PotPlayer\\PotPlayer.exe',
        'C:\\Program Files\\DAUM\\PotPlayer\\PotPlayerMini.exe',
        'C:\\Program Files\\DAUM\\PotPlayer\\PotPlayerMini64.exe',
        'C:\\Program Files\\PotPlayer\\PotPlayer.exe',
        'C:\\Program Files\\PotPlayer\\PotPlayerMini.exe',
        'C:\\Program Files\\PotPlayer\\PotPlayerMini64.exe',
        'C:\\Program Files (x86)\\PotPlayer\\PotPlayer.exe',
        'C:\\Program Files (x86)\\PotPlayer\\PotPlayerMini.exe',
        'C:\\Program Files (x86)\\PotPlayer\\PotPlayerMini64.exe',
        'C:\\PotPlayer\\PotPlayer.exe',
        'C:\\PotPlayer\\PotPlayerMini.exe',
        'C:\\PotPlayer\\PotPlayerMini64.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\PotPlayer', 'PotPlayer.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\PotPlayer', 'PotPlayer.exe')
    ]
    if sys.platform == 'darwin':
        paths.extend(['/Applications/PotPlayer.app/Contents/MacOS/PotPlayer', '/usr/local/bin/potplayer', '/opt/local/bin/potplayer'])
    for path in paths:
        if os.path.isfile(path):
            return path
    return None

def find_kmplayer_path():
    """Finds the path to KMPlayer in common installation directories."""
    username = os.getlogin()
    paths = [
        'C:\\Program Files\\KMPlayer 64X\\KMPlayer64.exe',
        'C:\\Program Files\\KMPlayer 64X\\KMPlayer.exe',
        'C:\\Program Files\\KMPlayer\\KMPlayer.exe',
        'C:\\Program Files (x86)\\KMPlayer\\KMPlayer.exe',
        'C:\\KMPlayer\\KMPlayer.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\KMPlayer', 'KMPlayer.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\KMPlayer', 'KMPlayer.exe'),
        'C:\\Program Files\\KMPlayer\\KMPlayer64.exe',
        'C:\\Program Files (x86)\\KMPlayer\\KMPlayer64.exe',
        'C:\\KMPlayer\\KMPlayer64.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\KMPlayer', 'KMPlayer64.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\KMPlayer', 'KMPlayer64.exe')
    ]
    if sys.platform == 'darwin':
        paths.extend(['/Applications/KMPlayer.app/Contents/MacOS/KMPlayer', '/usr/local/bin/kmplayer', '/opt/local/bin/kmplayer'])
    for path in paths:
        if os.path.isfile(path):
            return path
    return None

def open_with_vlc(filename):
    """Attempts to open the M3U playlist with VLC."""
    vlc_path = find_vlc_path()
    if vlc_path:
        try:
            if sys.platform == 'darwin':
                subprocess.call(('open', '-a', 'VLC', filename))
            else:
                subprocess.Popen([vlc_path, filename], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            messagebox.showerror('Error', f'Error opening with VLC: {e}')
            return False
    return False

def open_with_potplayer(filename):
    """Attempts to open the M3U playlist with PotPlayer."""
    potplayer_path = find_potplayer_path()
    if potplayer_path:
        try:
            if sys.platform == 'darwin':
                subprocess.call(('open', '-a', 'PotPlayer', filename))
            else:
                subprocess.Popen([potplayer_path, filename], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            messagebox.showerror('Error', f'Error opening with PotPlayer: {e}')
            return False
    return False

def open_with_kmplayer(filename):
    """Attempts to open the M3U playlist with KMPlayer."""
    kmplayer_path = find_kmplayer_path()
    if kmplayer_path:
        try:
            if sys.platform == 'darwin':
                subprocess.call(('open', '-a', 'KMPlayer', filename))
            else:
                subprocess.Popen([kmplayer_path, filename], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            messagebox.showerror('Error', f'Error opening with KMPlayer: {e}')
            return False
    return False

def open_with_default_app(filename):
    """Opens the M3U playlist with the default application."""
    try:
        if sys.platform == 'darwin':
            subprocess.call(('open', filename))
        else:
            os.startfile(filename)
    except Exception as e:
        messagebox.showerror('Error', f'Failed to open playlist with the default app: {e}')

def navigate_back():
    """Navigates back to the previous page or homepage."""
    global folders
    global current_page
    if history:
        last_state = history.pop()
        if history:
            prev_state = history[-1]
            if prev_state['type'] == 'video':
                show_video_list(prev_state['video_links'])
            else:
                if prev_state['type'] == 'folder':
                    current_page = prev_state['page']
                    folders = prev_state['folders']
                    show_folder_list()
                else:
                    if prev_state['type'] == 'search_results':
                        show_search_results(prev_state['search_term'], prev_state['filtered_folders'])
                    elif prev_state['type'] == 'history_page':
                        show_history_page()
                    else:
                        show_homepage()
        else:
            show_homepage()
    else:
        show_homepage()

def clear_window():
    """Clears all widgets from the main window except the progress window and the donation window."""
    for widget in root.winfo_children():
        if progress_window is not None and widget == progress_window or (donation_window is not None and widget == donation_window):
            continue
        widget.destroy()
    root.unbind_all('<MouseWheel>')
    root.unbind_all('<Button-4>')
    root.unbind_all('<Button-5>')

def open_url_from_entry(event=None):
    """Opens the URL entered by the user if the entry is focused."""
    if url_entry.focus_get() == url_entry:
        url = url_entry.get()
        validate_and_open_url(url)

def open_ftpbd_shortcut(index):
    """Handles the FTPBD shortcut button clicks."""
    url = ftpbd_shortcuts[index][1]
    validate_and_open_url(url)

def unbind_enter_key():
    """Unbinds the Enter key from the URL entry."""
    root.unbind('<Return>')

def bind_enter_key():
    """Binds the Enter key to the URL entry."""
    root.bind('<Return>', open_url_from_entry)

def load_shortcuts_from_file():
    """Loads the shortcuts from the settings file."""
    global ftpbd_shortcuts
    ftpbd_shortcuts = {}
    try:
        with open(SHORTCUT_SETTINGS, 'r') as f:
            for line in f:
                if line.strip():
                    name, url = line.strip().split('|', 1)
                    index = len(ftpbd_shortcuts) + 1
                    ftpbd_shortcuts[index] = (name, url)
            if not ftpbd_shortcuts:
                reset_to_default()
    except (FileNotFoundError, ValueError):
        reset_to_default()

def load_dont_settings():
    cache_dir = create_cache_folder()
    dont_settings_file = os.path.join(cache_dir, 'dont_settings.json')
    if os.path.exists(dont_settings_file):
        with open(dont_settings_file, 'r') as file:
            settings_data = json.load(file)
            return settings_data
    else:
        return {'session_count': 1, 'never_show_donation': False}

def save_dont_settings(dont_settings):
    cache_dir = create_cache_folder()
    dont_settings_file = os.path.join(cache_dir, 'dont_settings.json')
    with open(dont_settings_file, 'w') as file:
        json.dump(dont_settings, file)

def set_never_show_again(never_show_var):
    """Updates the setting for 'Never show again' based on the checkbox state."""
    dont_settings['never_show_donation'] = never_show_var.get()
    save_dont_settings(dont_settings)

def open_donation_window(show_never_show_checkbox=False):
    global donation_window
    if donation_window is None or not donation_window.winfo_exists():
        donation_window = tk.Toplevel(root, bg='#36454F')
        donation_window.withdraw()
        donation_window.title('$ Buy me a coffee $')
        donation_window.geometry('350x270')
        root.update_idletasks()
        donation_window.resizable(False, False)
        donation_window.configure(bg='light gray')
        root_x = root.winfo_x()
        root_y = root.winfo_y()
        root_width = root.winfo_width()
        root_height = root.winfo_height()
        window_width = 380
        window_height = 270
        center_x = root_x + (root_width // 2) - (window_width // 2)  # Fixed: Corrected arithmetic
        center_y = root_y + (root_height // 2) - (window_height // 2)  # Fixed: Corrected arithmetic
        donation_window.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        icon_path = os.path.join(os.path.dirname(__file__), 'ftpaddict.ico')
        donation_window.iconbitmap(default=icon_path)

        donation_frame = tk.Frame(donation_window, bg='light gray', relief=tk.RAISED)
        donation_frame.pack(fill=tk.BOTH, expand=True, anchor='center')
        message2 = tk.Label(donation_frame, text='Enjoying FTPaddict?\nDonate me if you want!', font=('Arial', 12, 'bold'), fg='white', bg='#003546')
        message2.pack(fill='x', pady=25)
        message3 = tk.Label(donation_frame, text='bKash/Rocket: 01728078733', font=('Arial', 12, 'bold'), bg='#002F1A', fg='yellow')
        message3.pack(pady=5)
        copy_button = tk.Button(donation_frame, text='Copy Number', font=('Arial', 13, 'bold'), cursor='hand2', command=copy_to_clipboard, bg='#008080', fg='white', relief=tk.FLAT)
        copy_button.pack(pady=10)
        appreciation = tk.Label(donation_frame, text='Appreciate it <3', font=('Arial', 12, 'bold'), fg='white', bg='#003546')
        appreciation.pack(fill='x', pady=10)
        if show_never_show_checkbox and not dont_settings['never_show_donation']:
            never_show_var = tk.BooleanVar(value=dont_settings['never_show_donation'])
            never_show_checkbox = tk.Checkbutton(donation_frame, text='Never show again', font=('Arial', 12, 'bold'), variable=never_show_var, fg='#002F1A', bg='light gray', command=lambda: set_never_show_again(never_show_var), cursor='hand2')
            never_show_checkbox.pack(pady=5)
        donation_window.deiconify()

def copy_to_clipboard():
    """Copies the donation number to clipboard and shows a temporary message."""
    pyperclip.copy('01728078733')
    show_temp_message0()

def show_temp_message0():
    """Shows a temporary message window without a title bar."""
    message_window = tk.Toplevel(root, bg='#36454F')
    message_window.overrideredirect(True)
    message_window.geometry('200x50')
    message_window.configure(bg='#002F1A')
    window_x = root.winfo_x() + root.winfo_width() // 2 - 100  # Fixed: Corrected arithmetic
    window_y = root.winfo_y() + root.winfo_height() // 2 - 40  # Fixed: Corrected arithmetic
    message_window.geometry(f'200x50+{window_x}+{window_y}')
    message_label = tk.Label(message_window, text='Number copied to clipboard!', font=('Arial', 12), fg='white', bg='#002F1A')
    message_label.pack(expand=True)
    message_window.attributes('-alpha', 0.8)
    message_window.after(1500, message_window.destroy)

def clear_history():
    """Clear the browsing history."""
    global cache_history
    cache_history = []
    save_history_to_file()
    show_history_page()

def show_history_page():
    """Display the browsing history."""
    global history

    for widget in root.winfo_children():
        if progress_window is not None and widget == progress_window:
            continue
        widget.destroy()

    # 🔹 Push history page state if not already on top
    if not history or history[-1].get('type') != 'history_page':
        history.append({'type': 'history_page'})

    history_frame = tk.Frame(root, bg='#36454F')
    history_frame.pack(fill='both', expand=True)

    title = tk.Label(history_frame, text='Browsing History', font=('Arial', 14, 'bold'),
                     pady=8, fg='white', bg='#003546')
    title.pack(fill='x', pady=(0, 15))

    scrollable_frame = tk.Frame(history_frame, bg='#36454F')
    scrollable_frame.pack(fill='both', expand=True)

    canvas = tk.Canvas(scrollable_frame, bg='#36454F', highlightthickness=0)
    scrollbar = tk.Scrollbar(scrollable_frame, orient='vertical', command=canvas.yview)

    scrollable_content = tk.Frame(canvas, bg='#36454F')
    scrollable_content.pack(fill='both', expand=True, pady=20)
    canvas.create_window((0, 0), window=scrollable_content, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollable_content.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

    # 🌀 Scroll only when hovered
    def _on_mousewheel(event):
        canvas.yview_scroll(-1 * int(event.delta / 120), 'units')

    def _bind_mousewheel(event):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, 'units'))  # Linux scroll up
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, 'units'))   # Linux scroll down

    def _unbind_mousewheel(event):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)

    if not cache_history:
        no_history_label = tk.Label(scrollable_content, text='No history found!', font=('Arial', 11), fg='red')
        no_history_label.pack(pady=20)
    else:
        for entry in reversed(cache_history):
            button = tk.Button(
                scrollable_content, text=entry['name'], font=('Arial', 11, 'bold'), fg='white', bg='#008080',
                cursor='hand2', command=lambda url=entry['url']: validate_and_open_url(url), anchor='w', padx=10
            )
            button.pack(fill='x', padx=25, pady=(3, 0))

    canvas.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')


    back_button = tk.Button(history_frame, text='Back', font=('Arial', 11, 'bold'), bg='#002F1A',
                            fg='white', command=navigate_back, cursor='hand2', borderwidth=1)
    back_button.pack(side='left', padx=(25, 0), pady=10)

    clear_button = tk.Button(history_frame, text='Clear All History', font=('Arial', 11, 'bold'), bg='red',
                             fg='white', command=clear_history, cursor='hand2', borderwidth=1)
    clear_button.pack(side='right', padx=25, pady=10)

    footer_frame = tk.Frame(root, bg='#003546')
    footer_frame.pack(side='bottom', fill='x', pady=0)

    footer_label_left = tk.Label(footer_frame, text='Developed by', font=('Arial', 10, 'bold'),
                                 bg='#008080', fg='white')
    footer_label_left.pack(side='left', anchor='w', padx=0)

    credit_link = tk.Label(footer_frame, text='Md. Junayed', font=('Arial', 10, 'bold'), fg='white',
                           cursor='hand2', bg='#008080')
    credit_link.pack(side='left', anchor='w')
    credit_link.bind('<Button-1>', lambda e: webbrowser.open('https://facebook.com/junayed733'))

    buy_me_coffee = tk.Label(footer_frame, text='Buy me a coffee', font=('Arial', 10, 'underline', 'bold'),
                             fg='light gray', cursor='hand2', bg='#003546')
    buy_me_coffee.pack(side='left', padx=5, anchor='center')
    buy_me_coffee.bind('<Button-1>', lambda e: open_donation_window())

    version_label_right = tk.Label(footer_frame, text='FTPaddict v11.0', font=('Arial', 10, 'bold'),
                                   anchor='e', fg='white', bg='#008080')
    version_label_right.pack(side='right', padx=0)

    update_version_label = tk.Label(footer_frame, text='Check for Update',
                                    font=('Arial', 10, 'underline', 'bold'), fg='light gray',
                                    cursor='hand2', bg='#003546')
    update_version_label.pack(side='right', padx=(0, 5))
    update_version_label.bind('<Button-1>', lambda e: webbrowser.open('https://github.com/j-unayed/FTPaddict/releases/tag/ftpaddict'))


def show_homepage():
    global url_entry
    global folders
    global current_page_type
    global current_url
    global current_page

    load_shortcuts_from_file()
    history.clear()
    current_page = 0
    current_page_type = None
    folders = []
    current_url = None
    clear_window()

    heading_frame = tk.Frame(root, bg='#008080')
    heading_frame.pack(fill='x', pady=0)

    heading_label = tk.Label(heading_frame, text='FTPaddict v11.0 – Streamer and Downloader',
                             font=('Arial', 16, 'bold'), fg='white', bg='#008080')
    heading_label.pack(pady=10)

    shortcuts_container = tk.Frame(root, bg='light blue', bd=0)
    shortcuts_container.pack(pady=(30, 20), padx=0)

    instruction_label = tk.Label(shortcuts_container, text='↓↓↓Click on any FTP shortcut below↓↓↓',
                                 font=('Arial', 12, 'bold'), fg='white', bg='#003546')
    instruction_label.pack(fill='x', pady=0, anchor='center')

    canvas = tk.Canvas(shortcuts_container, bg='#36454F', highlightthickness=0)
    canvas.pack(pady=2, padx=(2, 3), side='left', anchor='n')

    scrollbar = tk.Scrollbar(shortcuts_container, orient='vertical', command=canvas.yview)
    scrollbar.pack(side='right', fill='y')

    shortcut_frame = tk.Frame(canvas, bg='#36454F')
    shortcut_frame.pack(anchor='n')

    canvas.create_window((0, 0), window=shortcut_frame, anchor='n')

    def update_scroll_region(event):
        canvas.config(scrollregion=canvas.bbox('all'))

    # 🌀 Mousewheel scroll only when hovering inside canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(-1 * int(event.delta / 120), 'units')

    def _bind_mousewheel(event):
        canvas.bind_all('<MouseWheel>', _on_mousewheel)

    def _unbind_mousewheel(event):
        canvas.unbind_all('<MouseWheel>')

    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)

    shortcut_frame.grid_columnconfigure(0, weight=1)

    j = 0
    for i, (name, url) in ftpbd_shortcuts.items():
        button = tk.Button(shortcut_frame, text=name, command=lambda i=i: open_ftpbd_shortcut(i),
                           font=('Arial', 12, 'bold'), bg='#008080', fg='white', cursor='hand2', anchor='center')
        if j == 0:
            button.pack(fill='x', padx=(13, 0), pady=(12, 3))
            j += 1
        else:
            button.pack(fill='x', padx=(13, 0), pady=(0, 3))

    shortcut_frame.bind('<Configure>', update_scroll_region)

    canvas.config(scrollregion=canvas.bbox('all'))
    canvas.config(yscrollcommand=scrollbar.set)
    new_frame = tk.Frame(root, bg='#36454F')
    new_frame.pack(pady=0, anchor='n')
    edit_shortcuts_button = tk.Button(new_frame, text='Edit Shortcuts', command=open_edit_shortcuts_window, font=('Arial', 11, 'bold'), bg='#002F1A', fg='white', cursor='hand2')
    edit_shortcuts_button.grid(row=0, column=0, padx=10, pady=5)
    reset_button = tk.Button(new_frame, text='Reset Shortcuts', command=reset_to_default, font=('Arial', 11, 'bold'), bg='#002F1A', fg='white', cursor='hand2')
    reset_button.grid(row=0, column=1, padx=10, pady=5)
    history_button = tk.Button(new_frame, text='Browsing History', font=('Arial', 11, 'bold'), fg='white', bg='#002F1A', command=show_history_page, cursor='hand2', borderwidth=1)
    history_button.grid(row=0, column=2, padx=10, pady=5)
    search_label = tk.Label(root, text='Or, enter a FTP website URL:', font=('Arial', 12, 'bold'), fg='white', bg='#36454F')
    search_label.pack(pady=(10, 5))

    def on_entry_click(event):
        if url_entry.get() == 'http://www.example.com/path/to/folder/or/files/list/':
            url_entry.delete(0, tk.END)
            url_entry.config(fg='black', bg='light gray')

    def on_focusout(event):
        if url_entry.get() == '':
            url_entry.insert(0, 'http://www.example.com/path/to/folder/or/files/list/')
            url_entry.config(fg='gray', bg='light gray')

    def show_context_menu(event):
        context_menu = tk.Menu(root, tearoff=0)
        context_menu.add_command(label='Cut', command=lambda: url_entry.event_generate('<<Cut>>'))
        context_menu.add_command(label='Copy', command=lambda: url_entry.event_generate('<<Copy>>'))
        context_menu.add_command(label='Paste', command=lambda: url_entry.event_generate('<<Paste>>'))
        context_menu.add_command(label='Delete', command=lambda: url_entry.delete(tk.ACTIVE, tk.END))
        context_menu.post(event.x_root, event.y_root)
    url_entry = tk.Entry(root, fg='gray', bg='light gray', width=41)
    url_entry.insert(0, 'http://www.example.com/path/to/folder/or/files/list/')
    url_entry.pack(pady=5)
    url_entry.bind('<FocusIn>', on_entry_click)
    url_entry.bind('<FocusOut>', on_focusout)
    url_entry.bind('<Button-3>', show_context_menu)
    go_button = tk.Button(root, text='Go', command=open_url_from_entry, font=('Arial', 10, 'bold'), bg='#002F1A', fg='white', relief='raised', bd=3, width=10, cursor='hand2', borderwidth=1)
    go_button.pack(pady=5)
    bind_enter_key()
    footer_frame = tk.Frame(root, bg='#003546')
    footer_frame.pack(side='bottom', fill='x', pady=0)
    footer_label_left = tk.Label(footer_frame, text='Developed by', font=('Arial', 10, 'bold'), bg='#008080',
                                 fg='white')
    footer_label_left.pack(side='left', anchor='w', padx=0)
    credit_link = tk.Label(footer_frame, text='Md. Junayed', font=('Arial', 10, 'bold'), fg='white', cursor='hand2',
                           bg='#008080')
    credit_link.pack(side='left', anchor='w')
    credit_link.bind('<Button-1>', lambda e: webbrowser.open('https://facebook.com/junayed733'))
    buy_me_coffee = tk.Label(footer_frame, text='Buy me a coffee', font=('Arial', 10, 'underline', 'bold'),
                             fg='light gray', cursor='hand2', bg='#003546')
    buy_me_coffee.pack(side='left', padx=5, anchor='center')
    buy_me_coffee.bind('<Button-1>', lambda e: open_donation_window())
    version_label_right = tk.Label(footer_frame, text='FTPaddict v11.0', font=('Arial', 10, 'bold'), anchor='e',
                                   fg='white', bg='#008080')
    version_label_right.pack(side='right', padx=0)
    update_version_label = tk.Label(footer_frame, text='Check for Update', font=('Arial', 10, 'underline', 'bold'),
                                    fg='light gray', cursor='hand2', bg='#003546')
    update_version_label.pack(side='right', padx=(0, 5))
    update_version_label.bind('<Button-1>',
                              lambda e: webbrowser.open('https://github.com/j-unayed/FTPaddict/releases/tag/ftpaddict'))


def reset_to_default():
    """Resets the shortcuts to default values."""
    global ftpbd_shortcuts
    ftpbd_shortcuts = {
        1: ("English/Foreign TV Series", "https://server4.ftpbd.net/FTP-4/English-Foreign-TV-Series/"),
        2: ("All English Movies", "https://server2.ftpbd.net/FTP-2/"),
        3: ("Animation/Anime/Cartoon/Documentary", "https://server5.ftpbd.net/FTP-5/"),
        4: ("Hindi Series", "https://server3.ftpbd.net/FTP-3/Hindi%20TV%20Series/"),
        5: ("Hindi Movies", "https://server3.ftpbd.net/FTP-3/Hindi%20Movies/"),
        6: ("Bangla/Kolkatan", "https://server3.ftpbd.net/FTP-3/Bangla%20Collection/BANGLA/"),
        7: ("South Indian Movies", "https://server3.ftpbd.net/FTP-3/South%20Indian%20Movies/"),
        8: ("Skill Development Tutorials", "https://server4.ftpbd.net/FTP-4/Tutorial/"),
        9: ("Cracked Software", "https://server3.ftpbd.net/FTP-3/SOFTWARE-COLLECTION/"),
        10: ("Server 3", "https://server3.ftpbd.net/FTP-3/")
    }
    with open(SHORTCUT_SETTINGS, 'w') as f:
        for name, url in ftpbd_shortcuts.values():
            f.write(f'{name}|{url}\n')
    show_homepage()


def open_edit_shortcuts_window():
    """Opens a window to edit FTP shortcuts."""
    global edit_window
    if edit_window is not None and edit_window.winfo_exists():
        return

    # Create the window first
    edit_window = tk.Toplevel(root, bg='#607482')
    edit_window.title('Edit Shortcuts')
    edit_window.resizable(False, False)

    # --- Center the window on screen ---
    window_width = 750
    window_height = 470
    screen_width = edit_window.winfo_screenwidth()
    screen_height = edit_window.winfo_screenheight()
    center_x = int((screen_width / 2) - (window_width / 2))
    center_y = int((screen_height / 2) - (window_height / 2))
    edit_window.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
    frame = tk.Frame(edit_window, bg='#607482')
    frame.pack(fill='both', expand=True, padx=10, pady=10)

    canvas = tk.Canvas(frame, bg='#607482', highlightthickness=0)
    scrollbar = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg='#607482')

    canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

    entries = []

    # Create button frame FIRST
    button_frame = tk.Frame(scrollable_frame, bg='#607482')
    button_frame.pack(fill='x', pady=10)

    def show_context_menu(event, entry):
        menu = tk.Menu(root, tearoff=0)
        menu.add_command(label='Cut', command=lambda: entry.event_generate('<<Cut>>'))
        menu.add_command(label='Copy', command=lambda: entry.event_generate('<<Copy>>'))
        menu.add_command(label='Paste', command=lambda: entry.event_generate('<<Paste>>'))
        menu.add_command(label='Delete', command=lambda: entry.delete(0, tk.END))
        menu.tk_popup(event.x_root, event.y_root)

    def delete_shortcut(row_frame, entry_pair):
        entries.remove(entry_pair)
        row_frame.destroy()

    def add_shortcut_row(name='', url=''):
        row_frame = tk.Frame(scrollable_frame, bg='#607482')
        row_frame.pack(fill='x', pady=5, before=button_frame)

        name_entry = tk.Entry(row_frame, width=20)
        name_entry.insert(0, name)
        name_entry.pack(side='left', padx=5)
        name_entry.bind("<Button-3>", lambda e: show_context_menu(e, name_entry))

        url_entry = tk.Entry(row_frame, width=40)
        url_entry.insert(0, url)
        url_entry.pack(side='left', padx=5)
        url_entry.bind("<Button-3>", lambda e: show_context_menu(e, url_entry))

        delete_btn = tk.Button(
            row_frame,
            text='Delete',
            bg='red',
            fg='white',
            font=('Arial', 10, 'bold'),
            command=lambda: delete_shortcut(row_frame, (name_entry, url_entry)),
            cursor='hand2'  # ✅ This adds the hand cursor
        )
        delete_btn.pack(side='left', padx=5)

        entries.append((name_entry, url_entry))

    def add_new_shortcut():
        add_shortcut_row()

    def save_shortcuts():
        """Saves the edited shortcuts to the settings file."""
        global ftpbd_shortcuts
        ftpbd_shortcuts = {}
        for i, (name_entry, url_entry) in enumerate(entries, 1):
            name = name_entry.get().strip()
            url = url_entry.get().strip()
            if name and url:
                ftpbd_shortcuts[i] = (name, url)
        with open(SHORTCUT_SETTINGS, 'w') as f:
            for name, url in ftpbd_shortcuts.values():
                f.write(f'{name}|{url}\n')
        on_close_edit_window()

    # Add all existing shortcuts
    for name, url in ftpbd_shortcuts.values():
        add_shortcut_row(name, url)

    # Buttons
    add_button = tk.Button(button_frame, text='Add New Shortcut', font=('Arial', 10, 'bold'),
                           bg='#002F1A', fg='white', command=add_new_shortcut, cursor='hand2')
    add_button.pack(side='left', padx=5)

    save_button = tk.Button(button_frame, text='Save Shortcuts', font=('Arial', 10, 'bold'),
                            bg='#002F1A', fg='white', command=save_shortcuts, cursor='hand2')
    save_button.pack(side='left', padx=5)

    # Mouse scroll bindings
    scrollable_frame.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(-1 * (e.delta // 120), 'units'))
    scrollable_frame.bind_all('<Button-4>', lambda e: canvas.yview_scroll(-1, 'units'))  # Linux scroll up
    scrollable_frame.bind_all('<Button-5>', lambda e: canvas.yview_scroll(1, 'units'))   # Linux scroll down

    def on_close_edit_window():
        scrollable_frame.unbind_all('<MouseWheel>')
        scrollable_frame.unbind_all('<Button-4>')
        scrollable_frame.unbind_all('<Button-5>')
        edit_window.destroy()
        clear_window()
        show_homepage()

    edit_window.protocol("WM_DELETE_WINDOW", on_close_edit_window)


if __name__ == '__main__':

    global dont_settings
    global cache_history
    cache_history = []
    load_history_from_file()
    dont_settings = load_dont_settings()
    dont_settings['session_count'] += 1  # Fixed: Corrected increment
    save_dont_settings(dont_settings)
    root = tk.Tk()
    root.title('FTPaddict v11.0')
    icon_path = os.path.join(os.path.dirname(__file__), 'ftpaddict.ico')
    root.iconbitmap(default=icon_path)

    root.geometry('800x650')
    root.configure(bg='#36454F')
    root.resizable(True, True)

    root.update_idletasks()  # Force geometry update before querying size/position

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 800
    window_height = 650
    center_x = (screen_width // 2) - (window_width // 2)
    center_y = (screen_height // 2) - (window_height // 2)

    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    if not dont_settings['never_show_donation'] and dont_settings[
        'session_count'] % 4 == 0:  # Fixed: Corrected donation prompt condition
        open_donation_window(show_never_show_checkbox=True)
    show_homepage()
    root.mainloop()