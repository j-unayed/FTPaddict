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

# List of FTPBD shortcuts


# Global variables to handle history, root window, and pagination
progress_window = None
history = []
current_page_type = None
current_url = None
root = None
folders = []
current_page = 0
chunk_size = 150  # Number of folders per page


def get_app_directory():
    if getattr(sys, 'frozen', False):  # Check if the app is running as an executable
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return app_dir


def get_download_directory():
    if getattr(sys, 'frozen', False):
        # If the program is frozen (exe)
        base_dir = os.path.dirname(sys.executable)
    else:
        # If the program is running as a script
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Create a new folder "Downloaded Videos" in the base directory
    download_folder = os.path.join(base_dir, "Downloaded Videos")

    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    return download_folder

# Create FTPaddict_cache folder in the app directory
def create_cache_folder():
    app_dir = get_app_directory()
    cache_dir = os.path.join(app_dir, "FTPaddict_cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return cache_dir


# Define paths to files inside FTPaddict_cache
def get_file_paths():
    cache_dir = create_cache_folder()

    SETTINGS_FILE = os.path.join(cache_dir, "settings.txt")
    SHORTCUT_SETTINGS = os.path.join(cache_dir, "SCsettings.txt")
    playlist_file = os.path.join(cache_dir, "new_playlist.m3u")

    return SETTINGS_FILE, SHORTCUT_SETTINGS, playlist_file
SETTINGS_FILE, SHORTCUT_SETTINGS, playlist_file = get_file_paths()

# Function to save user selection to file
def save_player_selection(selection):
    with open(SETTINGS_FILE, "w") as f:
        f.write(selection)

# Function to load user selection from file
def load_player_selection():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return f.read().strip()
    return "PotPlayer"  # Default to PotPlayer if no settings found

def extract_links(base_url):
    '''Extracts all folder and video links from the webpage.'''
    try:
        response = requests.get(base_url)
        response.raise_for_status()
    except requests.RequestException:
        messagebox.showerror("Error", "Failed to access the URL.")
        return [], []

    soup = BeautifulSoup(response.text, 'html.parser')
    folder_links = []
    video_links = []

    video_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.wmv']

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        full_url = urljoin(base_url, href)
        name = a_tag.get_text(strip=True) or href.split('/')[-1]

        # Filter out non-folder links that do not share the base URL
        if not full_url.startswith(base_url):
            continue

        if any(href.lower().endswith(fmt) for fmt in video_formats):
            video_links.append((full_url, name))
        elif href.endswith('/'):
            folder_links.append((full_url, name))

    return folder_links, video_links


def validate_and_open_url(url):
    """Validate the URL and navigate to the appropriate page."""
    global current_page_type, current_url, folders, current_page, history
    # Fix the URL format
    if not url.startswith('http://'):
        if url.startswith('https://'):
            url = 'http://' + url[8:]  # Replace https:// with http://
        else:
            url = 'http://' + url  # Add http:// if missing

    try:
        response = requests.get(url)
        if response.status_code == 200:
            folder_links, video_links = extract_links(url)

            if video_links:
                # Check if this video page is already in history to avoid duplicate entries
                if not history or history[-1].get('url') != url or history[-1].get('type') != 'video':
                    history.append({
                        'type': 'video',
                        'url': url,
                        'video_links': video_links
                    })
                current_page_type = 'video'
                show_video_list(video_links)

            elif folder_links:
                # Check if this folder page is already in history to avoid duplicate entries
                if not history or history[-1].get('url') != url or history[-1].get('type') != 'folder':
                    history.append({
                        'type': 'folder',
                        'url': url,
                        'page': 0,
                        'folders': folder_links
                    })
                current_page_type = 'folder'
                folders = folder_links  # Store folder links for pagination
                current_page = 0  # Reset to the first page
                show_folder_list()
            else:
                messagebox.showerror("Error", "0 Videos")
                return
            current_url = url
        else:
            raise ValueError
    except (requests.exceptions.RequestException, ValueError):
        messagebox.showerror("Error", "Please check the URL or your WIFI")
        return None




def show_folder_list():
    """Displays a paginated list of folders with a search bar."""
    clear_window()
    # Display folder list heading
    heading_label = tk.Label(root, text="Click on any folder to open", font=("Arial", 12, "bold"), bg="navy",
                             fg="white")
    heading_label.pack(fill="x", pady=(10, 5))
    def search_folders():
        # Get the search term from the entry
        search_term = search_entry.get().lower().strip()

        # Create regex for exact word match or phrase match
        search_regex = re.compile(rf'\b{re.escape(search_term)}\b')

        # Filter folders that contain the exact word/phrase in the folder name
        filtered_folders = [f for f in folders if search_regex.search(f[1].lower())]

        # Display the filtered results
        show_search_results(search_term, filtered_folders)

    def on_entry_click(event):
        """Clear the placeholder text when the entry gains focus."""
        if search_entry.get() == "Find a folder...":
            search_entry.delete(0, tk.END)
            search_entry.config(fg='black')  # Change text color to black when typing

    def on_focusout(event):
        """Restore the placeholder text if the entry is empty when it loses focus."""
        if search_entry.get() == "":
            search_entry.insert(0, "Find a folder...")
            search_entry.config(fg='light gray')  # Change text color to light gray for placeholder

    # Create a frame for the search bar
    search_frame = tk.Frame(root)
    search_frame.pack(pady=5, padx=5, anchor='center', fill='x')  # Center the frame and allow it to fill horizontally

    # Add Go Home button (close to the left side)
    go_home_button = tk.Button(search_frame, text="<<Homepage", font=("Arial", 10, "bold"),
                               fg="blue", command=show_homepage, cursor="hand2")
    go_home_button.pack(side="left", padx=(5, 10), pady=5)  # Pack the Go Home button to the left with padding

    # Create another frame to center the search entry and button
    center_frame = tk.Frame(search_frame)
    center_frame.pack(pady=5, padx=130,side="left")  # Center this frame in the remaining space

    # Add search entry with a specified width and placeholder text
    search_entry = tk.Entry(center_frame, fg='gray', width=20)  # Set a specific width
    search_entry.insert(0, "Find a folder...")
    search_entry.pack(side="left", padx=(0, 10), pady=5)  # Pack the entry next to the center frame

    # Bind focus events to handle placeholder text
    search_entry.bind("<FocusIn>", on_entry_click)
    search_entry.bind("<FocusOut>", on_focusout)

    # Add search button
    search_button = tk.Button(center_frame, text="Search", font=("Arial", 12, "bold"), bg="green", fg="white",
                              command=search_folders, cursor="hand2", borderwidth=1)
    search_button.pack(side="left", padx=(0, 10), pady=5)  # Pack the button next to the entry

    # Bind Enter key to Search button
    search_entry.bind("<Return>", lambda event: search_button.invoke())





    # Display folder list with pagination
    display_folder_list()

    # Add back button
    back_button = tk.Button(root, text="Back",font=("Arial", 12, "bold"), bg="green",
                                  fg="white", command=navigate_back, cursor="hand2", borderwidth=1)
    back_button.pack(pady=10)

    footer_frame = tk.Frame(root)
    footer_frame.pack(side="bottom", fill="x", pady=10)

    footer_label_left = tk.Label(footer_frame, text="Developed by ©", font=("Arial", 10),fg="gray")
    footer_label_left.pack(side="left", anchor="w", padx=10)

    credit_link = tk.Label(footer_frame, text="Md. Junayed", font=("Arial", 10, "underline", "bold"), fg="gray",
                           cursor="hand2")
    credit_link.pack(side="left", anchor="w")
    credit_link.bind("<Button-1>", lambda e: webbrowser.open("https://facebook.com/junayed733"))

    footer_label_right = tk.Label(footer_frame, text="FTPaddict V10 ~ 2024", font=("Arial", 10), anchor="e",fg="gray")
    footer_label_right.pack(side="right", padx=10)

def show_search_results(search_term, filtered_folders):
    """Displays the search results on the same page without pagination."""


    # Display search results heading

    if not filtered_folders:
        messagebox.showerror("Search Results", "0 Folders Found")
        return
    else:
        clear_window()
        heading_label = tk.Label(root, text=f"Results for '{search_term}'", font=("Arial", 12, "bold"), bg="navy",
                                 fg="white")
        heading_label.pack(fill="x", pady=(10, 5))

        # Display filtered folder list without pagination
        frame = tk.Frame(root)
        frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(frame)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        # Add this block to store search result state in history
        if not history or history[-1].get('type') != 'search_results':
            history.append({
                'type': 'search_results',
                'search_term': search_term,
                'filtered_folders': filtered_folders
            })
        # Set margins for the folder list
        scrollable_frame.config(padx=40, pady=40)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, (url, name) in enumerate(filtered_folders):
            button = tk.Button(scrollable_frame, text=f"{i + 1}. {name}", fg="blue", cursor="hand2",
                               command=lambda url=url: validate_and_open_url(url))
            button.pack(pady=2, anchor="w")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable scrolling anywhere within the canvas
        frame.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        frame.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        frame.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    # Unbind Enter key when no search bar is present
    root.unbind("<Return>")

    # Add back button to reload the full folder list
    back_button = tk.Button(root, text="Back",font=("Arial", 12, "bold"), bg="green",
                                  fg="white", command=navigate_back, cursor="hand2", borderwidth=1)
    back_button.pack(pady=10)

    footer_frame = tk.Frame(root)
    footer_frame.pack(side="bottom", fill="x", pady=10)

    footer_label_left = tk.Label(footer_frame, text="Developed by ©", font=("Arial", 10), fg="gray")
    footer_label_left.pack(side="left", anchor="w", padx=10)

    credit_link = tk.Label(footer_frame, text="Md. Junayed", font=("Arial", 10, "underline", "bold"), fg="gray",
                           cursor="hand2")
    credit_link.pack(side="left", anchor="w")
    credit_link.bind("<Button-1>", lambda e: webbrowser.open("https://facebook.com/junayed733"))

    footer_label_right = tk.Label(footer_frame, text="FTPaddict V10 ~ 2024", font=("Arial", 10), anchor="e", fg="gray")
    footer_label_right.pack(side="right", padx=10)



def display_folder_list():
    """Displays folders with pagination, scrollbar, media player selection, and a 'Open URL in browser' button."""
    global current_page  # Assuming last_saved_url is used to store the URL

    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(frame)
    scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)

    # Set margins for the folder list
    scrollable_frame.config(padx=20, pady=20)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Add "Open URL in browser" button
    def open_url_in_browser():
        url = get_last_url_from_history()
        if url:
            webbrowser.open(url)
        else:
            messagebox.showerror("Error", "No URL found in history.")



    # Display folders for the current page
    start = current_page * chunk_size
    end = start + chunk_size
    paginated_folders = folders[start:end]

    for i, (url, name) in enumerate(paginated_folders):
        button = tk.Button(scrollable_frame, text=f"{start + i + 1}. {name}", fg="blue", cursor="hand2",
                           command=lambda url=url: validate_and_open_url(url))
        button.pack(pady=2, anchor="w")

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Enable scrolling anywhere within the canvas
    frame.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
    frame.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
    frame.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    # Pagination controls
    pagination_frame = tk.Frame(root, pady=10)
    pagination_frame.pack()

    # Total folder info
    total_folders_info = tk.Label(pagination_frame, text=f"Total folders: {len(folders)}",
                                  font=("Arial", 10, "bold"))
    total_folders_info.pack(side="left", padx=20)

    # Previous Button
    prev_button = tk.Button(pagination_frame, text="Previous", command=go_to_previous_page,
                            state="normal" if current_page > 0 else "disabled",
                            font=("Arial", 10, "bold"), bg="lightgray", relief="raised", bd=2, cursor="hand2")
    prev_button.pack(side="left", padx=5)

    # Next Button
    next_button = tk.Button(pagination_frame, text="Next", command=go_to_next_page,
                            state="normal" if end < len(folders) else "disabled",
                            font=("Arial", 10, "bold"), bg="lightgray", relief="raised", bd=2, cursor="hand2")
    next_button.pack(side="left", padx=5)

    # Page Info
    num_pages = ((len(folders) - 1) // chunk_size) + 1
    page_info = tk.Label(pagination_frame, text=f"Go to page:", font=("Arial", 10, "bold"))
    page_info.pack(side="left", padx=5)

    # Dropdown Box
    page_options = list(range(1, num_pages + 1))
    page_dropdown = ttk.Combobox(pagination_frame, values=page_options, width=4, state="readonly", cursor="hand2")
    page_dropdown.set(current_page + 1)  # Set current page
    page_dropdown.pack(side="left", padx=5)

    # Total pages info
    total_pages_info = tk.Label(pagination_frame, text=f"of {num_pages}", font=("Arial", 10, "bold"))
    total_pages_info.pack(side="left", padx=5)

    # Open URL in browser
    open_url_button = tk.Button(
        pagination_frame, text="Open URL in browser", fg="black", bg="lightgray",
        borderwidth=1, relief="solid", command=open_url_in_browser, cursor="hand2"
    )
    open_url_button.pack(side="right", padx=20)

    page_dropdown.bind("<<ComboboxSelected>>", lambda event: go_to_page(int(page_dropdown.get()) - 1))


def go_to_page(page_num):
    """Navigate to a specific page of the folder list."""
    global current_page, history
    current_page = page_num

    # Check if the current state in history is from the same folder
    if history and history[-1]['type'] == 'folder':
        # Update the existing folder state with the new page number
        history[-1]['page'] = current_page
    else:
        # Add a new folder state if not already present
        history.append({
            'type': 'folder',
            'page': current_page,
            'folders': folders.copy()
        })

    show_folder_list()


def go_to_previous_page():
    """Navigate to the previous page of the folder list."""
    global current_page, history
    if current_page > 0:
        current_page -= 1

        # Update the existing folder state with the new page number
        if history and history[-1]['type'] == 'folder':
            history[-1]['page'] = current_page
        else:
            history.append({
                'type': 'folder',
                'page': current_page,
                'folders': folders.copy()
            })

        show_folder_list()

def go_to_next_page():
    """Navigate to the next page of the folder list."""
    global current_page, history
    if (current_page + 1) * chunk_size < len(folders):
        current_page += 1

        # Update the existing folder state with the new page number
        if history and history[-1]['type'] == 'folder':
            history[-1]['page'] = current_page
        else:
            history.append({
                'type': 'folder',
                'page': current_page,
                'folders': folders.copy()
            })

        show_folder_list()


def show_video_list(video_links):
    """Displays a list of videos with a header."""
    clear_window()

    # Add header for video list
    header_label = tk.Label(root, text="Click on any tab to Stream or Download", font=("Arial", 12, "bold"),
                            bg="navy", fg="white")
    header_label.pack(fill="x", pady=(10, 5))

    # Display video list
    display_video_list(video_links)

    # Create a frame for the navigation buttons
    nav_frame = tk.Frame(root)
    nav_frame.pack(pady=10, fill='x')  # Allow the frame to fill horizontally

    # Add Go Home button (close to the left side)
    go_home_button = tk.Button(nav_frame, text="<< Homepage", font=("Arial", 10, "bold"),
                               fg="blue", command=show_homepage, cursor="hand2")
    go_home_button.pack(side="left", padx=(15, 10), pady=5)  # Pack the Go Home button to the left

    back_frame = tk.Frame(nav_frame)
    back_frame.pack(pady=5, padx=180, side="left")

    # Add Back button (centered in the remaining space)
    back_button = tk.Button(back_frame, text="Back", font=("Arial", 12, "bold"), bg="green",
                            fg="white", command=navigate_back, cursor="hand2", borderwidth=1)
    back_button.pack(side="left", padx=(0, 10), expand=True)  # Add a little padding on the left

    footer_frame = tk.Frame(root)
    footer_frame.pack(side="bottom", fill="x", pady=10)

    footer_label_left = tk.Label(footer_frame, text="Developed by ©", font=("Arial", 10), fg="gray")
    footer_label_left.pack(side="left", anchor="w", padx=10)

    credit_link = tk.Label(footer_frame, text="Md. Junayed", font=("Arial", 10, "underline", "bold"), fg="gray",
                           cursor="hand2")
    credit_link.pack(side="left", anchor="w")
    credit_link.bind("<Button-1>", lambda e: webbrowser.open("https://facebook.com/junayed733"))

    footer_label_right = tk.Label(footer_frame, text="FTPaddict V10 ~ 2024", font=("Arial", 10), anchor="e",fg="gray")
    footer_label_right.pack(side="right", padx=10)


def get_last_url_from_history():
    if history:
        last_entry = history[-1]  # Get the most recent history entry
        if 'url' in last_entry:
            return last_entry['url']
    return None

def find_open_url():
    url = get_last_url_from_history()
    if url:
        webbrowser.open(url)
    else:
        messagebox.showerror("Error", "No URL found in history.")

def is_connected():
    """Check if the internet is available by pinging a lightweight server."""
    try:
        # You can use a simple request to a known IP for a faster response
        requests.get('https://1.1.1.1', timeout=3)
        return True
    except requests.ConnectionError:
        return False
    except requests.Timeout:
        return False


def display_video_list(video_links):
    """Displays videos with tabs for streaming and downloading."""
    canvases = {}

    def create_stream_tab():
        """Create the Stream tab with existing functionality."""
        # Create the Stream tab
        stream_tab = ttk.Frame(notebook)
        notebook.add(stream_tab, text="Stream")

        # Existing display code for streaming
        frame = tk.Frame(stream_tab)
        frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(frame, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        # Set margins for the video list
        scrollable_frame.config(padx=40, pady=40)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvases[scrollable_frame] = canvas

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Load the previous selection or default to PotPlayer
        selected_player = load_player_selection()

        # Radio button options
        player_var = tk.StringVar(value=selected_player)

        def on_player_change():
            save_player_selection(player_var.get())


        # Font styling for the radio buttons and the label
        bold_font = tkfont.Font(weight="bold")

        # Create a frame to hold the labels
        label_frame = tk.Frame(scrollable_frame)
        label_frame.pack(pady=1, anchor="nw")

        # Instruction text
        label1 = tk.Label(label_frame, text="Please select your preferred video player", fg="green", font=bold_font)
        label1.pack(side='left', padx=(0, 10), pady=5)

        label2 = tk.Label(label_frame, text="(It must be installed in default installation path)", fg="green")
        label2.pack(side='left', pady=5)

        # Create radio buttons with larger size, bold text, and aligned side by side
        button_frame = tk.Frame(scrollable_frame)
        button_frame.pack(pady=5)

        vlc_radio = tk.Radiobutton(button_frame, text="VLC", variable=player_var, value="VLC", command=on_player_change,
                                   font=bold_font, width=10, height=2, cursor="hand2")
        potplayer_radio = tk.Radiobutton(button_frame, text="PotPlayer", variable=player_var, value="PotPlayer",
                                         command=on_player_change, font=bold_font, width=10, height=2, cursor="hand2")
        kmplayer_radio = tk.Radiobutton(button_frame, text="KMPlayer", variable=player_var, value="KMPlayer",
                                        command=on_player_change, font=bold_font, width=10, height=2, cursor="hand2")
        open_url_button = tk.Button(button_frame, text="Open URL in browser", bg="light grey", fg="black", bd=1,
                                    relief="solid",
                                    highlightthickness=1, command=find_open_url, cursor="hand2")

        # Pack the radio buttons side by side and centered
        vlc_radio.pack(side="left", padx=10)
        potplayer_radio.pack(side="left", padx=10)
        kmplayer_radio.pack(side="left", padx=10)
        open_url_button.pack(side="left", padx=100)

        # Create buttons for each video link
        for i, (url, name) in enumerate(video_links):
            button = tk.Button(scrollable_frame, text=f"{i + 1}. {name}", fg="navy", cursor="hand2",
                               command=lambda i=i: add_to_playlist_and_open(i, video_links, player_var.get()))
            button.pack(pady=2, anchor="w")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


    def create_download_tab():
        """Create the Download tab with input boxes for range and download button."""

        # Create the Download tab
        download_tab = ttk.Frame(notebook)
        notebook.add(download_tab, text="Download")

        # Font styling for the labels
        bold_font = tkfont.Font(weight="bold")

        # Create a scrollable frame for the video list
        list_frame = tk.Frame(download_tab)
        list_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(list_frame, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        video_list_frame = tk.Frame(canvas)

        video_list_frame.config(padx=40, pady=40)

        video_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvases[video_list_frame] = canvas

        canvas.create_window((0, 0), window=video_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)


        def create_progress_window():
            """Create a new window to show download progress."""
            global progress_window
            if progress_window is not None and progress_window.winfo_exists():
                messagebox.showinfo("Cannot Initiate Downloading", "Close any other download progress window first!")
                return
            progress_window = tk.Toplevel()
            progress_window.title("Download Progress")

            # Create a scrollable frame to show progress for multiple videos
            progress_canvas = tk.Canvas(progress_window, height=300, width=400)
            progress_scrollbar = ttk.Scrollbar(progress_window, orient="vertical", command=progress_canvas.yview)
            progress_frame = tk.Frame(progress_canvas)

            progress_frame.bind(
                "<Configure>", lambda e: progress_canvas.configure(scrollregion=progress_canvas.bbox("all"))
            )
            canvases[progress_frame] = progress_canvas
            progress_canvas.create_window((0, 0), window=progress_frame, anchor="nw")
            progress_canvas.configure(yscrollcommand=progress_scrollbar.set)

            progress_canvas.pack(side="left", fill="both", expand=True)
            progress_scrollbar.pack(side="right", fill="y")
            progress_window=progress_window

            return progress_window, progress_frame

        def create_progress_label(progress_frame, url, name):
            """Create a label and progress bar for a video in the progress window."""
            # Create label to show video URL and name
            label = tk.Label(progress_frame, text=f"From URL: {url}\nDownloading {name}",
                             anchor="w", justify="left", wraplength=380)
            label.pack(pady=5, anchor="w", padx=10)

            # Create a progress bar with a fixed length of 200 pixels
            progress_var = tk.DoubleVar()

            progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100,
                                           length=300)  # Fixed length of 200 pixels
            progress_bar.pack(pady=5, padx=10, anchor="w")  # Anchor to the west (left)

            return label, progress_var

        def download_process(url, name, progress_var, label):
            """Download a single video with a fixed progress bar length."""

            try:
                if not label.winfo_exists():
                    return  # Exit if the label (progress window) doesn't exist

                download_dir = get_download_directory()  # Get the path to "Downloaded Videos" folder
                filename = os.path.join(download_dir, name)  # Create the full file path for the video
                label.config(text=f"\nDownloading {name}")
                response = requests.get(url, stream=True)

                if response.status_code == 200:
                    with open(filename, 'wb') as file:
                        total_size = int(response.headers.get('content-length', 0)) or 1  # Default to 1 if unknown
                        downloaded = 0
                        last_percentage = 0  # Track last updated percentage

                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                file.write(chunk)
                                downloaded += len(chunk)

                                # Calculate the percentage of completion
                                percentage = (downloaded / total_size) * 100

                                # Update the progress bar and cap it at 100%
                                if percentage - last_percentage >= 0.5:  # Update if increased by 1%
                                    last_percentage = percentage
                                    progress_var.set(min(percentage, 100))  # Ensure it never exceeds 100

                                    # Check if the label still exists before updating
                                    if label.winfo_exists():
                                        label.config(text=f"\nDownloading {name}\n[{percentage:.1f}%]")
                                    else:
                                        return  # Exit if label no longer exists

                    if label.winfo_exists():
                        label.config(text=f"Downloaded {name} successfully!\n[100%]")
                else:
                    if label.winfo_exists():
                        label.config(text=f"Failed to download {name}. HTTP Status code: {response.status_code}")
                        return

            except Exception as e:
                if label.winfo_exists():
                    label.config(text=f"Error downloading {name}: {str(e)}")

        def download_videos(video_links, start, end):
            """Download multiple videos in sequence."""
            global progress_window
            if not is_connected():
                messagebox.showerror("Connection Error", "No internet connection available.")
                return

            if progress_window is not None and progress_window.winfo_exists():
                messagebox.showinfo("Cannot Initiate Downloading", "Close any other download progress window first!")
                return
            progress_window, progress_frame = create_progress_window()

            # Sequentially download each video in the range
            for i in range(start - 1, end):
                url, name = video_links[i]
                label, progress_var = create_progress_label(progress_frame, url, name)

                # Download one video at a time
                download_process(url, name, progress_var, label)

                # Check if the label still exists before updating
                if not label.winfo_exists():
                    break  # Exit the loop if the label no longer exists

        def on_download_button_click(video_links, from_entry, to_entry):
            """Handle the Download Now button click event."""
            try:
                start = int(from_entry.get())
                end = int(to_entry.get())

                if start <= 0 or end <= 0 or start > end or end > len(video_links):
                    raise ValueError("Invalid range")

                # Start the download process in a separate thread to avoid freezing the GUI
                threading.Thread(target=download_videos, args=(video_links, start, end), daemon=True).start()
            except ValueError as e:
                messagebox.showerror("Input Error", str(e))

        def on_download_all_button_click(video_links):
            """Handle the Download All button click event."""
            try:
                start = 1  # Start from the first video
                end = len(video_links)  # End at the last video

                # Start the download process in a separate thread to avoid freezing the GUI
                threading.Thread(target=download_videos, args=(video_links, start, end), daemon=True).start()
            except Exception as e:
                messagebox.showerror("Download Error", str(e))

        def download_single_video(url, name):

            """Download a single video in a separate thread."""
            progress_window, progress_frame = create_progress_window()

            # Create the progress bar and label for the single video
            label, progress_var = create_progress_label(progress_frame, url, name)

            # Start the download in a separate thread to avoid freezing the GUI
            threading.Thread(target=download_process, args=(url, name, progress_var, label), daemon=True).start()

        # This function is triggered when the user clicks a single video button
        def on_video_button_click(url, name):
            """Handle the single video download button click event."""
            global progress_window
            if progress_window is not None and progress_window.winfo_exists():
                messagebox.showinfo("Cannot Initiate Downloading", "Close any other download progress window first!")
                return

            if not is_connected():
                messagebox.showerror("Connection Error", "No internet connection available.")
                return

            download_single_video(url, name)

        # Modified video button code to trigger the download


        # Frame for download inputs
        download_frame = tk.Frame(list_frame)
        download_frame.pack(padx=10,pady=15, anchor="center",fill="x")


        # Create input boxes for range
        from_label = tk.Label(download_frame, text="Download videos from", fg="green", font=bold_font)
        from_entry = tk.Entry(download_frame, width=5)
        to_label = tk.Label(download_frame, text="to", fg="green", font=bold_font)
        from_label.pack(side="left")
        to_entry = tk.Entry(download_frame, width=5)
        download_button = tk.Button(download_frame, text="Download Now", bg="green", fg="white", bd=1,
                                    relief="solid", highlightthickness=1,
                                    command=lambda: on_download_button_click(video_links, from_entry, to_entry),
                                    cursor="hand2")

        # Create the Download All button
        download_all_button = tk.Button(
            download_frame,
            text="Download All",
            bg="blue",
            fg="white",
            bd=1,
            relief="solid",
            highlightthickness=1,
            command=lambda: on_download_all_button_click(video_links),
            cursor="hand2"
        )

        open_url_button = tk.Button(download_frame, text="Open URL in browser", bg="light grey", fg="black", bd=1,
                                    relief="solid", highlightthickness=1, command=find_open_url, cursor="hand2")

        from_entry.pack(side="left", padx=5)
        to_label.pack(side="left")
        to_entry.pack(side="left", padx=5)
        download_button.pack(side='left', padx=5)
        download_all_button.pack(side='left',padx=10)
        open_url_button.pack(side='left', padx=50)

        location_frame = tk.Frame(list_frame)
        location_frame.pack(padx=10,pady=5,anchor='w')
        location_label = tk.Label(location_frame,
                                  text="The videos will be downloaded to the same folder where FTPaddict.exe is located!",
                                  fg="green")
        location_label.pack(side="left")

        # Create a button for each video in the list
        for i, (url, name) in enumerate(video_links):
            video_button = tk.Button(
                video_list_frame,
                text=f"{i + 1}. {name}",
                fg="blue",
                cursor="hand2",
                command=lambda url=url, name=name: on_video_button_click(url, name)
            )
            video_button.pack(pady=2, anchor="w")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        to_entry.bind("<Return>", lambda event: download_button.invoke())

    def scroll_canvas(e):
        # Iterate over all canvases and their associated frames
        for frame, canvas in list(canvases.items()):
            try:
                # Check if the frame is still mapped (visible)
                if frame.winfo_ismapped():
                    canvas.yview_scroll(-1 * (e.delta // 120), "units")
            except tk.TclError:
                # If the frame or canvas is not available (destroyed), remove it from the canvases dict
                del canvases[frame]
    root.bind_all("<MouseWheel>", scroll_canvas)
    root.bind_all("<Button-4>", lambda e: scroll_canvas(e))
    root.bind_all("<Button-5>", lambda e: scroll_canvas(e))

    # Create a ttk Style object
    style = ttk.Style()
    bold_font = ('TkDefaultFont', 10, 'bold')
    # Modify the notebook tab style
    style.configure('Custom.TNotebook.Tab', background='lightblue', foreground='black', padding=[10, 5],font=bold_font)
    style.map('Custom.TNotebook.Tab', background=[('selected', 'lightgreen')], foreground=[('selected', 'blue')])

    # Create notebook (tab container)
    notebook = ttk.Notebook(root, style='Custom.TNotebook')
    notebook.pack(fill=tk.BOTH, expand=True)

    # Create tabs
    create_stream_tab()
    create_download_tab()

def add_to_playlist_and_open(index, video_links, selected_player):
    """Adds videos to playlist and opens with selected player priority."""

    # Create playlist with videos from the selected index
    playlist_videos = video_links[index:] + video_links[:index]

    with open(playlist_file, 'w') as f:
        f.write("#EXTM3U\n")
        for url, title in playlist_videos:
            f.write(f"#EXTINF:-1,{title}\n{url}\n")

    # Define player priority based on the selected option
    if selected_player == "VLC":
        if open_with_vlc(playlist_file): return
        if open_with_potplayer(playlist_file): return
        if open_with_kmplayer(playlist_file): return
    elif selected_player == "PotPlayer":
        if open_with_potplayer(playlist_file): return
        if open_with_vlc(playlist_file): return
        if open_with_kmplayer(playlist_file): return
    elif selected_player == "KMPlayer":
        if open_with_kmplayer(playlist_file): return
        if open_with_vlc(playlist_file): return
        if open_with_potplayer(playlist_file): return

    # Fall back to default app
    open_with_default_app(playlist_file)


def find_vlc_path():
    '''Finds the path to VLC in common installation directories.'''
    # Get the current username
    username = os.getlogin()

    # Define potential paths
    paths = [
        r'C:\Program Files\VideoLAN\VLC\vlc.exe',
        r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe',
        r'C:\Program Files\VLC\vlc.exe',
        r'C:\Program Files (x86)\VLC\vlc.exe',
        r'C:\VLC\vlc.exe',
        r'C:\VideoLAN\VLC\vlc.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\VideoLAN\\VLC', 'vlc.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\VideoLAN\\VLC', 'vlc.exe')
    ]

    # Add Mac OS-specific paths
    if sys.platform == 'darwin':
        paths.extend([
            '/Applications/VLC.app/Contents/MacOS/VLC',
            '/usr/local/bin/vlc',
            '/opt/local/bin/vlc'
        ])

    # Check each path to see if the file exists
    for path in paths:
        if os.path.isfile(path):
            return path

    return None

def find_potplayer_path():
    '''Finds the path to PotPlayer in common installation directories.'''
    # Get the current username
    username = os.getlogin()

    # Define potential paths
    paths = [
        r'C:\Program Files\DAUM\PotPlayer\PotPlayer.exe',
        r'C:\Program Files\DAUM\PotPlayer\PotPlayerMini.exe',
        r'C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe',
        r'C:\Program Files\PotPlayer\PotPlayer.exe',
        r'C:\Program Files\PotPlayer\PotPlayerMini.exe',
        r'C:\Program Files\PotPlayer\PotPlayerMini64.exe',
        r'C:\Program Files (x86)\PotPlayer\PotPlayer.exe',
        r'C:\Program Files (x86)\PotPlayer\PotPlayerMini.exe',
        r'C:\Program Files (x86)\PotPlayer\PotPlayerMini64.exe',
        r'C:\PotPlayer\PotPlayer.exe',
        r'C:\PotPlayer\PotPlayerMini.exe',
        r'C:\PotPlayer\PotPlayerMini64.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\PotPlayer', 'PotPlayer.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\PotPlayer', 'PotPlayer.exe')
    ]
    # Add Mac OS-specific paths
    if sys.platform == 'darwin':
        paths.extend([
            '/Applications/PotPlayer.app/Contents/MacOS/PotPlayer',
            '/usr/local/bin/potplayer',
            '/opt/local/bin/potplayer'
        ])
    # Check each path to see if the file exists
    for path in paths:
        if os.path.isfile(path):
            return path

    return None


def find_kmplayer_path():
    '''Finds the path to KMPlayer in common installation directories.'''
    # Get the current username
    username = os.getlogin()

    # Define potential paths
    paths = [
        r'C:\Program Files\KMPlayer 64X\KMPlayer64.exe',
        r'C:\Program Files\KMPlayer 64X\KMPlayer.exe',
        r'C:\Program Files\KMPlayer\KMPlayer.exe',
        r'C:\Program Files (x86)\KMPlayer\KMPlayer.exe',
        r'C:\KMPlayer\KMPlayer.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\KMPlayer', 'KMPlayer.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\KMPlayer', 'KMPlayer.exe'),
        r'C:\Program Files\KMPlayer\KMPlayer64.exe',
        r'C:\Program Files (x86)\KMPlayer\KMPlayer64.exe',
        r'C:\KMPlayer\KMPlayer.exe',
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\KMPlayer', 'KMPlayer64.exe'),
        os.path.join(f'C:\\Users\\{username}\\AppData\\Local\\Programs\\KMPlayer', 'KMPlayer64.exe')
    ]

    # Add Mac OS-specific paths
    # Add Mac OS-specific paths
    if sys.platform == 'darwin':
        paths.extend([
            '/Applications/KMPlayer.app/Contents/MacOS/KMPlayer',
            '/usr/local/bin/kmplayer',
            '/opt/local/bin/kmplayer'
        ])

    # Check each path to see if the file exists
    for path in paths:
        if os.path.isfile(path):
            return path

    return None



def open_with_vlc(filename):
    '''Attempts to open the M3U playlist with VLC.'''
    vlc_path = find_vlc_path()
    if vlc_path:
        try:
            if sys.platform == 'darwin':
                subprocess.call(('open', '-a', 'VLC', filename))
            else:
                subprocess.Popen([vlc_path, filename], shell=True, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error opening with VLC: {e}")
            return False
    return False


def open_with_potplayer(filename):
    '''Attempts to open the M3U playlist with PotPlayer.'''
    potplayer_path = find_potplayer_path()
    if potplayer_path:
        try:
            if sys.platform == 'darwin':
                subprocess.call(('open', '-a', 'PotPlayer', filename))
            else:
                subprocess.Popen([potplayer_path, filename], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error opening with PotPlayer: {e}")
            return False
    return False


def open_with_kmplayer(filename):
    '''Attempts to open the M3U playlist with KMPlayer.'''
    kmplayer_path = find_kmplayer_path()
    if kmplayer_path:
        try:
            if sys.platform == 'darwin':
                subprocess.call(('open', '-a', 'KMPlayer', filename))
            else:
                subprocess.Popen([kmplayer_path, filename], shell=True, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error opening with KMPlayer: {e}")
            return False
    return False

def open_with_default_app(filename):
    '''Opens the M3U playlist with the default application.'''
    try:
        if sys.platform == 'darwin':
            subprocess.call(('open', filename))
        else:
            os.startfile(filename)  # Windows only
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open playlist with the default app: {e}")





def navigate_back():
    """Navigates back to the previous page or homepage."""
    global current_page, history, current_page_type, folders
    if history:
        last_state = history.pop()
        if history:
            prev_state = history[-1]
            if prev_state['type'] == 'video':
                show_video_list(prev_state['video_links'])
            elif prev_state['type'] == 'folder':
                current_page = prev_state['page']
                folders = prev_state['folders']
                show_folder_list()
            elif prev_state['type'] == 'search_results':
                show_search_results(prev_state['search_term'], prev_state['filtered_folders'])
            else:
                show_homepage()
        else:
            show_homepage()  # Default action if history is empty
    else:
        show_homepage()  # Default action if history is empty


def clear_window():
    """Clears all widgets from the main window except the progress window."""
    for widget in root.winfo_children():
        # Check if the widget is the progress window, skip it if it is
        if progress_window is not None and widget == progress_window:
            continue
        widget.destroy()

    # Unbind mouse scrolling events to prevent errors
    root.unbind_all("<MouseWheel>")
    root.unbind_all("<Button-4>")
    root.unbind_all("<Button-5>")



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
    except (FileNotFoundError, ValueError) as e:
        reset_to_default()

def open_donation_window():
    # Create a new small window
    donation_window = tk.Toplevel(root)
    donation_window.title("$ Buy me a coffee $")
    donation_window.geometry("350x250")  # Set window size
    donation_window.resizable(False, False)
    donation_window.configure(bg="black")  # Light gray background

    # Create a frame in the middle of the window
    donation_frame = tk.Frame(donation_window, bg="black", relief=tk.RAISED)
    donation_frame.pack(expand=True)

    # Add the donation message with colors and styling
    message1 = tk.Label(donation_frame, text="Trying to normalize this in Bangladesh :3", font=("Arial", 11), fg="white",bg="black")
    message1.pack(pady=5)

    message2 = tk.Label(donation_frame, text="Feel free to donate even 0.01 Taka xD", font=("Arial", 11), fg="white",bg="black")
    message2.pack(pady=5)

    message3 = tk.Label(donation_frame, text="bKash/Rocket: 01728078733", font=("Arial", 12, "bold"), bg="black", fg="yellow")  # Chocolate color
    message3.pack(pady=5)

    # Button to copy the number to clipboard with style
    copy_button = tk.Button(donation_frame, text="Copy Number", font=("Arial", 13,"bold"), cursor="hand2", command=copy_to_clipboard, bg="#4CAF50", fg="white",  relief=tk.FLAT)
    copy_button.pack(pady=10)

    # Appreciation message
    appreciation = tk.Label(donation_frame, text="Appreciate it <3", font=("Arial", 10), fg="white",bg="black")
    appreciation.pack(pady=5)

def copy_to_clipboard():
    # Copy the number to clipboard
    pyperclip.copy("01728078733")

def show_homepage():
    global history, current_page, current_page_type, folders, current_url

    # Load shortcuts from file or use default
    load_shortcuts_from_file()

    history.clear()
    current_page = 0
    current_page_type = None
    folders = []
    current_url = None
    clear_window()

    root.geometry("800x600")
    root.resizable(False, False)

    heading_frame = tk.Frame(root, bg="green")
    heading_frame.pack(fill="x", pady=10)
    heading_label = tk.Label(heading_frame, text="FTPaddict – Ultimate Streaming and Downloading Tool",
                             font=("Arial", 16, "bold"), fg="white", bg="green")
    heading_label.pack(pady=10)

    instruction_label = tk.Label(root, text="↓↓↓Click on any FTP shortcut below↓↓↓",
                                 font=("Arial", 12, "bold"), fg="white", bg="black")
    instruction_label.pack(fill="x", pady=(10, 20))

    shortcut_frame = tk.Frame(root)
    shortcut_frame.pack(pady=20)

    for i, (name, url) in ftpbd_shortcuts.items():
        button = tk.Button(shortcut_frame, text=name, command=lambda i=i: open_ftpbd_shortcut(i),
                           font=("Arial", 12, "bold"), bg="navy", fg="white", cursor="hand2")
        button.grid(row=i, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

    edit_shortcuts_button = tk.Button(shortcut_frame, text="Edit Shortcuts", command=open_edit_shortcuts_window,
                                     font=("Arial", 12), bg="green", fg="white", cursor="hand2")
    edit_shortcuts_button.grid(row=6, column=0, padx=10, pady=5)

    reset_button = tk.Button(shortcut_frame, text="Reset to Default", command=reset_to_default,
                            font=("Arial", 12), bg="green", fg="white", cursor="hand2")
    reset_button.grid(row=6, column=1, padx=10, pady=5)

    search_label = tk.Label(root, text="Or, enter a FTP website URL:", font=("Arial", 12, "bold"))
    search_label.pack(pady=(20, 5))

    def on_entry_click(event):
        """Clear the placeholder text when the entry gains focus."""
        if url_entry.get() == "http://www.example.com/path/to/folder/or/video/list/":
            url_entry.delete(0, tk.END)
            url_entry.config(fg='black')  # Change text color to black when typing

    def on_focusout(event):
        """Restore the placeholder text if the entry is empty when it loses focus."""
        if url_entry.get() == "":
            url_entry.insert(0, "http://www.example.com/path/to/folder/or/video/list/")
            url_entry.config(fg='light gray')  # Change text color to light gray for placeholder

    global url_entry
    url_entry = tk.Entry(root,fg="gray", width=41)
    url_entry.insert(0, "http://www.example.com/path/to/folder/or/video/list/")
    url_entry.pack(pady=5)

    # Bind focus events to handle placeholder text
    url_entry.bind("<FocusIn>", on_entry_click)
    url_entry.bind("<FocusOut>", on_focusout)

    go_button = tk.Button(root, text="Go", command=open_url_from_entry, font=("Arial", 12, "bold"), bg="black",
                          fg="white", relief="raised", bd=3, width=10, cursor="hand2", borderwidth=1)
    go_button.pack(pady=5)

    bind_enter_key()

    footer_frame = tk.Frame(root)
    footer_frame.pack(side="bottom", fill="x", pady=10)

    footer_label_left = tk.Label(footer_frame, text="Developed by ©", font=("Arial", 10))
    footer_label_left.pack(side="left", anchor="w", padx=10)

    credit_link = tk.Label(footer_frame, text="Md. Junayed", font=("Arial", 10, "underline", "bold"),fg="navy", cursor="hand2")
    credit_link.pack(side="left", anchor="w")
    credit_link.bind("<Button-1>", lambda e: webbrowser.open("https://facebook.com/junayed733"))

    buy_me_coffee = tk.Label(footer_frame, text="$ Buy me a coffee $", font=("Arial", 10, "underline", "bold"),
                             fg="brown", cursor="hand2")
    buy_me_coffee.pack(side="left", padx=130)
    buy_me_coffee.bind("<Button-1>", lambda e: open_donation_window())

    footer_label_right = tk.Label(footer_frame, text="FTPaddict V10 ~ 2024", font=("Arial", 10), anchor="e")
    footer_label_right.pack(side="right", padx=10)

def open_edit_shortcuts_window():
    """Opens a smaller window to edit FTPBD shortcuts."""
    edit_window = tk.Toplevel(root)
    edit_window.title("Edit Shortcuts")
    edit_window.geometry("800x250")

    entries = []

    def save_shortcuts():
        global ftpbd_shortcuts
        for i, (name_entry, url_entry) in enumerate(entries):
            name = name_entry.get().strip()
            url = url_entry.get().strip()
            if name and url:
                ftpbd_shortcuts[i + 1] = (name, url)

        # Save the updated shortcuts to file
        save_shortcuts_to_file()
        edit_window.destroy()
        show_homepage()

    # Display current shortcuts
    for i, (name, url) in ftpbd_shortcuts.items():
        tk.Label(edit_window, text=f"Shortcut {i}").grid(row=i, column=0, padx=10, pady=5)
        name_entry = tk.Entry(edit_window, width=30)
        name_entry.insert(0, name)
        name_entry.grid(row=i, column=1, padx=10, pady=5)
        url_entry = tk.Entry(edit_window, width=50)
        url_entry.insert(0, url)
        url_entry.grid(row=i, column=2, padx=10, pady=5)
        entries.append((name_entry, url_entry))

    # Add Save button
    save_button = tk.Button(edit_window, text="Save Shortcuts", command=save_shortcuts, font=("Arial", 12), bg="green", fg="white",cursor="hand2")
    save_button.grid(row=6, column=0, columnspan=3, pady=10)

def save_shortcuts_to_file():
    """Saves the shortcuts to the settings file for persistence."""
    with open(SHORTCUT_SETTINGS, 'w') as f:
        for i, (name, url) in ftpbd_shortcuts.items():
            f.write(f"{name}|{url}\n")

def reset_to_default():
    """Resets the shortcuts to their default values and restarts the app."""
    global ftpbd_shortcuts
    ftpbd_shortcuts = {
        1: ("English TV Series", "http://server4.ftpbd.net/FTP-4/English%20%26%20Foreign%20TV%20Series/"),
        2: ("All English Movies", "http://server2.ftpbd.net/FTP-2/"),
        3: ("Animation, Anime, Documentary", "http://server5.ftpbd.net/FTP-5/"),
        4: ("Hindi Series", "http://server3.ftpbd.net/FTP-3/Hindi%20TV%20Series/"),
        5: ("Bangla-Hindi-Foreign-Awards-Series-Movies", "http://server3.ftpbd.net/FTP-3/")
    }
    save_shortcuts_to_file()
    show_homepage()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("FTPaddict")
    show_homepage()
    root.mainloop()