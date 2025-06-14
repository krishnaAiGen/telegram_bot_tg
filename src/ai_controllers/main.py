# src/ai_controllers/main.py
import subprocess
import sys
import time
import os

# --- Configuration ---
# A list of the scripts that must be run as persistent processes for the bot to function.
PROCESSES_TO_RUN = [
    "telegram.py",        # The "Ears" - Data Ingestor
    "response.py",        # The "Brain" - Main Logic Loop
    "telegram_utils.py"   # The "Mouth" - Message Sender
]

def run_main():
    """
    Launches all required bot processes in separate, parallel subprocesses.
    This script acts as a central starting point for the entire application.
    """
    print("--- Conversational Bot Application Launcher ---")
    print(f"Attempting to launch {len(PROCESSES_TO_RUN)} processes...")
    
    running_processes = []

    for script_name in PROCESSES_TO_RUN:
        # Construct the full path to the script to ensure it can be found
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        
        if not os.path.exists(script_path):
            print(f"Error: Script not found at '{script_path}'. Skipping.")
            continue

        try:
            # sys.executable ensures that the subprocess uses the same Python
            # interpreter that is running this launcher script.
            process = subprocess.Popen([sys.executable, script_path])
            running_processes.append(process)
            print(f"  -> Successfully launched: {script_name} (Process ID: {process.pid})")
            time.sleep(2) # A small delay to stagger the launches and allow for initialization.
        except Exception as e:
            print(f"  -> Failed to launch {script_name}. Error: {e}")

    print("\n--- All bot processes have been launched. ---")
    print("The bot is now running. Monitor the console for output from each process.")
    print("To stop the bot, press Ctrl+C in this terminal.")
    
    try:
        # This will wait until all child processes have finished. Since they are
        # infinite loops, this will run until the user interrupts it.
        for process in running_processes:
            process.wait()
    except KeyboardInterrupt:
        # This block catches Ctrl+C
        print("\n--- Launcher interrupted by user. Sending termination signal to all processes... ---")
        for process in running_processes:
            process.terminate() # A clean way to ask the processes to stop
        print("All bot processes terminated.")

if __name__ == "__main__":
    run_main()