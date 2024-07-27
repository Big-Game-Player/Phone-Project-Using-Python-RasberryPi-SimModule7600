#! /usr/bin/python3

import RPi.GPIO as GPIO
import serial
import time
import threading
import pygame
import sys
from datetime import datetime
import os

# Set the working directory to the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)


buffer = ""  # Initialize buffer variable here

# Initialize serial communication
ser = serial.Serial('/dev/ttyS0', 115200)
ser.flushInput()

# Define constants
power_key = 6

# Define concise and descriptive variable names for AT commands
DIAL_PHONE = 'ATD{};'
HANG_UP = 'AT+CHUP'
ENABLE_CLIP = 'AT+CLIP=1'

# Define an event to signal threads to stop
stop_event = threading.Event()

call_active = False
incoming_call = False
current_call_number = ""  # Track the current call number
incoming_number_logged = False  # Flag to ensure the incoming number is logged once

call_log_file = "call_log.txt"
incoming_call_notification = ""
notification_start_time = None
last_call_time = None

def send_at(command, back, timeout): 
    """Send AT command to the SIM7600X and check for a specific response."""
    rec_buff = ''
    if ser.isOpen():
        ser.write((command + '\r\n').encode())
        time.sleep(timeout)
        if ser.inWaiting():
            time.sleep(0.01)
            rec_buff = ser.read(ser.inWaiting()).decode()  # Decode byte string to regular string
    if back not in rec_buff:
        print(command + ' ERROR')
        print(command + ' back:\t' + rec_buff)
        return False
    else:
        print(rec_buff)
        return True

def power_on(power_key):
    """Power on the SIM7600X module and enable caller ID notification."""
    print('SIM7600X is starting:')
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(power_key, GPIO.OUT)
    time.sleep(0.1)
    GPIO.output(power_key, GPIO.HIGH)
    time.sleep(2)
    GPIO.output(power_key, GPIO.LOW)
    time.sleep(3)
    ser.flushInput()
    print('SIM7600X is ready')
    send_at(ENABLE_CLIP, 'OK', 1)  # Enable CLIP to show incoming call numbers

def power_down(power_key):
    """Power down the SIM7600X module."""
    print('SIM7600X is logging off:')
    GPIO.output(power_key, GPIO.HIGH)
    time.sleep(3)
    GPIO.output(power_key, GPIO.LOW)
    time.sleep(120)
    print('Goodbye')

def log_call(number, call_type):
    """Log a call to the call log file with a timestamp."""
    with open(call_log_file, 'a') as f:
        f.write(f"{datetime.now().strftime('%a %b %d, %Y %I:%M %p')} - {call_type}: {number}\n")

def get_call_log():
    """Retrieve the last 16 calls from the call log file in reverse order."""
    try:
        with open(call_log_file, 'r') as f:
            lines = f.readlines()
            return lines[-16:][::-1]  # Get last 16 calls in reverse order
    except FileNotFoundError:
        return []

def get_last_call():
    """Retrieve the last call entry from the call log file."""
    try:
        with open(call_log_file, 'r') as f:
            lines = f.readlines()
            if lines:
                return lines[-1].strip()
            else:
                return None
    except FileNotFoundError:
        return None

def make_call(number):
    """Initiate an outgoing call and log it."""
    global call_active, current_call_number
    send_at(f'ATD{number};', 'OK', 1)
    print(f"Calling {number}...")
    log_call(number, "Outgoing call")
    call_active = True
    current_call_number = number

def end_call():
    """End the current call and reset related variables."""
    global call_active, incoming_call, current_call_number, incoming_number_logged, incoming_call_notification, notification_start_time
    send_at('AT+CHUP', 'OK', 1)
    print("Call hung up.")
    call_active = False
    incoming_call = False
    current_call_number = ""
    incoming_number_logged = False  # Reset the flag when the call ends
    incoming_call_notification = ""  # Clear the incoming call notification
    notification_start_time = None

def receive_call():
    """Wait for incoming calls and log the caller's number."""
    global incoming_call, current_call_number, incoming_number_logged
    try:
        power_on(power_key)
        while not stop_event.is_set():
            send_at('AT', 'OK', 1)
            print("Waiting for incoming call...")
            buffer = ""
            while not stop_event.is_set():
                if ser.isOpen() and ser.inWaiting():
                    buffer += ser.read(ser.inWaiting()).decode()
                    print("Buffer: " + buffer)
                    if 'RING' in buffer:
                        print("Incoming call detected.")
                        incoming_call = True
                        incoming_number_logged = False  # Reset the flag for the new incoming call
                        buffer = ""  # Clear the buffer to capture the next data
                        while incoming_call:
                            if ser.isOpen() and ser.inWaiting():
                                buffer += ser.read(ser.inWaiting()).decode()
                                print("Buffer (updated): " + buffer)
                                if not incoming_number_logged and '+CLIP' in buffer:
                                    start = buffer.find('+CLIP: "') + len('+CLIP: "')  # Find the start of the number
                                    end = buffer.find('"', start)
                                    current_call_number = buffer[start:end]
                                    print(f"Caller number extracted: {current_call_number}")
                                    log_call(current_call_number, "Incoming call")
                                    incoming_number_logged = True  # Set the flag to avoid logging multiple times
                            time.sleep(1)  # Wait for user to accept or reject call
                        break
    except Exception as e:
        print("Error:", str(e))
    finally:
        if ser is not None:
            ser.close()
            GPIO.cleanup()

def start_threads():
    """Create and start the thread for receiving calls."""
    receive_thread = threading.Thread(target=receive_call)
    receive_thread.start()

# Initialize Pygame
pygame.init()

# Screen dimensions
screen_width = 675
screen_height = 450
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Super Super Ultrasonic Mega Phone")

# Load background image
background_image = pygame.image.load("Phone_GUI.png")

# Define colors
transparent_color = (0, 0, 0, 0)  # Fully transparent
text_color = (255, 255, 255)  # White color for text
notification_color = (255, 0, 0)  # Red color for notifications

# Define button information
buttons = {
    "1": (435, 126, 40, 40),
    "2": (499, 126, 40, 40),
    "3": (565, 126, 40, 40),
    "4": (435, 183, 40, 40),
    "5": (499, 183, 40, 40),
    "6": (565, 183, 40, 40),
    "7": (435, 243, 40, 40),
    "8": (499, 243, 40, 40),
    "9": (565, 243, 40, 40),
    "0": (499, 303, 40, 40),
    "del": (565, 303, 40, 40),
    "send call": (566, 363, 40, 40),
    "accept call": (435, 363, 40, 40),  # Accept call button on the right
    "end call": (500, 363, 40, 40)      # End call button on the right
}

# Create a surface for the button with per-pixel alpha
button_surface = pygame.Surface((40, 40), pygame.SRCALPHA)
button_surface.fill(transparent_color)

# Initialize font
pygame.font.init()
font = pygame.font.SysFont('Arial', 36)
time_font = pygame.font.SysFont('Arial', 16)  # Smaller font for time
date_font = pygame.font.SysFont('Arial', 16)  # Smaller font for date
log_font = pygame.font.SysFont('Arial', 13)  # Smaller font for call log
notification_font = pygame.font.SysFont('Arial', 24)  # Font for notifications

# Store the entered numbers and current number as a string
entered_numbers = ""
current_number = ""

def handle_button_press(button_name):
    """Handle button press events to manage input and calls."""
    global entered_numbers, current_number, incoming_call, call_active, incoming_call_notification, notification_start_time
    if button_name == "del":
        entered_numbers = entered_numbers[:-1]
        current_number = current_number[:-1]
    elif button_name in "0123456789":
        entered_numbers += button_name
        current_number += button_name
    elif button_name == "send call" and current_number:
        make_call(current_number)
    elif button_name == "end call":
        end_call()
    elif button_name == "accept call" and incoming_call:
        send_at('ATA', 'OK', 1)
        print("Call answered.")
        call_active = True
        incoming_call = False
        incoming_call_notification = ""  # Clear the incoming call notification
        notification_start_time = None
    print(f"Button '{button_name}' pressed")

def get_current_time():
    """Return the current time formatted as a string."""
    return datetime.now().strftime('%I:%M %p')

def get_current_date():
    """Return the current date formatted as a string."""
    return datetime.now().strftime('%a %b %d, %Y')

# Record the last call time at the start
last_call = get_last_call()
if last_call and "Incoming call" in last_call:
    last_call_time = datetime.strptime(last_call.split(" - ")[0], '%a %b %d, %Y %I:%M %p')

# Start the threads for handling calls
start_threads()

# Main loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = event.pos
            for button_name, (x, y, width, height) in buttons.items():
                if x <= mouse_x <= x + width and y <= mouse_y <= y + height:
                    handle_button_press(button_name)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_0:
                handle_button_press("0")
            elif event.key == pygame.K_1:
                handle_button_press("1")
            elif event.key == pygame.K_2:
                handle_button_press("2")
            elif event.key == pygame.K_3:
                handle_button_press("3")
            elif event.key == pygame.K_4:
                handle_button_press("4")
            elif event.key == pygame.K_5:
                handle_button_press("5")
            elif event.key == pygame.K_6:
                handle_button_press("6")
            elif event.key == pygame.K_7:
                handle_button_press("7")
            elif event.key == pygame.K_8:
                handle_button_press("8")
            elif event.key == pygame.K_9:
                handle_button_press("9")
            elif event.key == pygame.K_BACKSPACE:
                handle_button_press("del")

    # Check for the last call log entry and set notification if it's an incoming call after the program started
    last_call = get_last_call()
    if last_call and "Incoming call" in last_call:
        call_time = datetime.strptime(last_call.split(" - ")[0], '%a %b %d, %Y %I:%M %p')
        if last_call_time is None or call_time > last_call_time:
            incoming_call_notification = last_call
            notification_start_time = time.time()
            last_call_time = call_time

    # Clear notification if 25 seconds have passed
    if notification_start_time and time.time() - notification_start_time >= 25:
        incoming_call_notification = ""
        notification_start_time = None

    # Blit the background image onto the screen
    screen.blit(background_image, (0, 0))

    # Blit the transparent button surfaces onto the screen
    for x, y, width, height in buttons.values():
        screen.blit(button_surface, (x, y))

    # Render the entered numbers and blit to the screen
    text_surface = font.render(entered_numbers, True, text_color)
    screen.blit(text_surface, (410, 64))

    # Get and render the current time
    current_time = get_current_time()
    time_surface = time_font.render(current_time, True, text_color)
    screen.blit(time_surface, (screen_width // 2 + 76, 20))

    # Get and render the current date
    current_date = get_current_date()
    date_surface = date_font.render(current_date, True, text_color)
    screen.blit(date_surface, (screen_width - date_surface.get_width() - 44, 20))

    # Get and render the call log
    call_log = get_call_log()
    y_offset = 95
    for log in call_log:
        log_surface = log_font.render(log.strip(), True, text_color)
        screen.blit(log_surface, (44, y_offset))
        y_offset += 20 

    # Render the incoming call notification if it exists
    if incoming_call_notification:
        notification_surface = notification_font.render(incoming_call_notification, True, notification_color)
        screen.blit(notification_surface, (44, screen_height - 40))

    # Update the display
    pygame.display.flip()

# Quit Pygame
pygame.quit()
sys.exit()
