from __future__ import print_function
# --- FIX FOR PYTHON 3.10+ ---
import collections
import collections.abc
collections.MutableMapping = collections.abc.MutableMapping

import math
import pvporcupine
import pyaudio
import struct
import numpy as np
import soundfile as sf
import io
import pyttsx3
import librosa
import wave
import time
import threading
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain.agents import create_agent
from faster_whisper import WhisperModel
from dronekit import connect, VehicleMode, LocationGlobalRelative
from pymavlink import mavutil



speech_lock = threading.Lock()
def _speak_worker(text):
    # This thread waits here if someone else is already speaking
    with speech_lock:
        try:
            # Initialize a fresh engine every time for reliability
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")

def speak(text: str):
    print(f"🗣️ Speaking: {text}")
    # Start the thread. It will run in background and wait for the lock if needed.
    t = threading.Thread(target=_speak_worker, args=(text,), daemon=True)
    t.start()

# --- 2. DRONE STATE & SAFETY ---
vehicle = None 
manual_override = False # Global safety flag

def mode_callback(self, attr_name, value):
    """
    Safety Watchdog: Runs automatically when flight mode changes.
    If the pilot switches out of GUIDED/AUTO, we abort script control.
    """
    global manual_override
    # Allowable modes for script control
    safe_modes = ['GUIDED', 'AUTO', 'LAND', 'BRAKE']
    
    if value.name not in safe_modes:
        if not manual_override:
            print(f"\n⚠️ MANUAL CONTROL DETECTED! Mode changed to {value.name}")
            print("⚠️ Aborting autonomous commands...")
            manual_override = True
            speak("Manual control detected. Pausing script.")

def connect_drone(connection_string, waitready=True, baudrate=57600):
    global vehicle
    if vehicle is None:
        print(f"📡 Connecting to drone: {connection_string}")
        vehicle = connect(connection_string, wait_ready=waitready, baud=baudrate)
        
        # --- ATTACH SAFETY LISTENER ---
        print("👀 Attaching Safety Listener...")
        vehicle.add_attribute_listener('mode', mode_callback)
        
    print("✅ Drone connected")

def arm_and_takeoff(aTargetAltitude):
    global vehicle
    if vehicle is not None:
        print("Basic pre-arm checks")
        while not vehicle.is_armable:
            print(" Waiting for vehicle to initialise...")
            time.sleep(1)
            
        print("Arming motors")
        vehicle.mode = VehicleMode("GUIDED")
        vehicle.armed = True
        
        while not vehicle.armed:
            print(" Waiting for arming...")
            time.sleep(1)
            
        print("Taking off!")
        vehicle.simple_takeoff(aTargetAltitude)
        
        while True:
            # Check for manual override during takeoff
            if vehicle.mode.name != 'GUIDED':
                print("Takeoff aborted by manual control.")
                return

            alt = vehicle.location.global_relative_frame.alt
            print(f" Altitude: {alt:.2f}")
            if alt >= aTargetAltitude * 0.95:
                print("Reached target altitude")
                break
            time.sleep(1)

# --- 3. TOOLS ---
@tool
def answer_general_question(response_text: str) -> str:
    """
    Use this tool to answer general questions or chitchat that are NOT flight commands.
    Example: If user says "What is your name?", call this tool with response_text="I am a drone."
    """
    return response_text # Just returns the text so the agent can speak it


@tool
def emergency_land() -> str:
    """
    Forces the drone to land.
    CRITICAL: This tool will REFUSE to run if the pilot has already taken manual control.
    """
    global vehicle, manual_override
    
    if not vehicle: return "No drone connected."
    if  not vehicle.mode : return " No drone connected"
    
    # --- 1. CHECK FOR SAFE MANUAL MODES ---
    # If you are in LOITER, ALT_HOLD, or STABILIZE, the AI should NOT touch the drone.
    safe_manual_modes = ['LOITER', 'ALT_HOLD', 'STABILIZE', 'POSHOLD']
    current_mode = vehicle.mode.name
    
    if current_mode in safe_manual_modes:
        print(f"🛑 AI BLOCKED: Pilot is flying manually in {current_mode} mode.")
        return f"Command ignored. Pilot is in control ({current_mode})."

    # --- 2. EXECUTE LANDING (Only if in GUIDED/AUTO) ---
    print("🚨 AI INITIATING EMERGENCY LANDING")
    vehicle.mode = VehicleMode("LAND")
    return "Emergency landing initiated."

@tool
def control_drone_movement(direction: str, meters: int) -> str:
    """
    Moves the drone in a specific direction.
    
    ARGS:
        direction (str): The specific direction to move. 
                            MUST be one of these exact words: 'forward', 'backward', 'left', 'right', 'up', 'down'.
                            - If user says "turn right", use 'right'.
                            - If user says "turn left", use 'left'.
                            - If user says "climb" or "ascend", use 'up'.
                            - If user says "descend" or "drop", use 'down'.
        meters (int): The distance to travel in meters.
    """

    global vehicle, manual_override
    if vehicle is None:
        return "vehi is not connected"
    if vehicle.mode is None:
        return "No connection"
    
    if not vehicle or not vehicle.armed:
        return "Error: Drone is not connected or not armed."

    # Reset override flag if we are starting a fresh command in GUIDED mode
    if vehicle.mode.name == 'GUIDED':
        manual_override = False
    else:
        return f"Error: Cannot execute. Drone is in {vehicle.mode.name} mode."

    # 1. ENSURE LOCAL FRAME IS INITIALIZED
    if vehicle.location.local_frame.north is None:
        return "Error: Drone local position is not initialized. Wait for GPS fix."

    # 2. Capture Start Position
    start_pos = vehicle.location.local_frame
    
    # NED logic
    n, e, d = 0, 0, 0
    direction = direction.lower()
    if direction == "forward": n = meters
    elif direction == "backward": n = -meters
    elif direction == "right": e = meters
    elif direction == "left": e = -meters
    elif direction == "up": d = -meters
    elif direction == "down": d = meters
    else: return "Invalid direction."

    msg = vehicle.message_factory.set_position_target_local_ned_encode(
        0, 0, 0,
        mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED, 
        0b0000111111111000, 
        n, e, d, 0, 0, 0, 0, 0, 0, 0, 0)
    
    vehicle.send_mavlink(msg)
    vehicle.flush()

    # 3. Safe Distance Tracking Loop
    timeout = time.time() + (meters * 2) + 20  # Dynamic timeout
    
    while True:
        if vehicle.mode is None:
            return "No connection"
        # --- CRITICAL SAFETY CHECK ---
        if manual_override or vehicle.mode.name != 'GUIDED':
            return f"❌ ABORTED: Manual control taken (Mode: {vehicle.mode.name})."
        # -----------------------------

        curr_pos = vehicle.location.local_frame
        
        if curr_pos.north is None or start_pos.north is None or curr_pos.east is None or curr_pos.down is None:
            return "Error: Lost local position fix during movement."

        distance_moved = math.sqrt(
            (curr_pos.north - start_pos.north)**2 + 
            (curr_pos.east - start_pos.east)**2 + 
            (curr_pos.down - start_pos.down)**2
        )
        
        if distance_moved >= (meters - 0.5):
            break
            
        if time.time() > timeout:
            return "Movement timed out. Drone stopped or slowed down."
            
        time.sleep(0.5)

    return f"Success. Completed {direction} movement for {meters} meters."

# --- 4. AGENT SETUP ---
# functiongemma:270m
# llama3.1:8b
# qwen2.5:latest
llm = ChatOllama(model="qwen2.5:latest", temperature=0.1)

system_msg = (
    "You are an expert drone pilot. "
    "Your PRIMARY goal is safety. "
    
    "GUIDELINES:"
    "1. If the user gives a valid movement command (turn, go, move, climb), use 'control_drone_movement'."
    
    "3. If the user asks a question or says anything else (e.g., 'Hello', 'Who are you?'), use 'answer_general_question'."
    "4. NEVER use 'emergency_land' unless the user specifically implies stopping."
)
"2. If the user says 'LAND', 'STOP', or 'ABORT', use 'emergency_land'."

agent = create_agent(llm, tools=[control_drone_movement,answer_general_question,emergency_land], system_prompt=system_msg,debug=False)

# --- 5. AUDIO PROCESSING ---
model = WhisperModel("turbo", device="cuda", compute_type="float16")

def transcribe_audio(wav_buffer):
    wav_buffer.seek(0)
    try:
        audio_array, _ = sf.read(wav_buffer, dtype="float32")
        if len(audio_array.shape) > 1: audio_array = np.mean(audio_array, axis=1)
        audio_array = librosa.resample(audio_array, orig_sr=16000, target_sr=16000)
        segments, _ = model.transcribe(audio_array, beam_size=5, language="en")
        return " ".join([s.text for s in segments]).strip()
    except Exception as e:
        print(f"❌ STT Error: {e}"); return ""

def process_command(text):
    if not text: return
    print(f"🤖 Processing command: {text}")

    # --- INSTANT SAFETY OVERRIDE ---
    if "stop" in text.lower() or "abort" in text.lower() or "halt" in text.lower():
        if vehicle: 
            vehicle.mode = VehicleMode("BRAKE")
        speak("Stopping immediately.")
        return
    # -------------------------------

    try:
        result = agent.invoke({"messages": [{"role": "user", "content": text}]})
        reply = result["messages"][-1].content
        speak(reply)
    except Exception as e:
        print(f"❌ Agent Error: {e}")
        speak("I encountered an error.")

def record_command(pa, rate):
    CHUNK = 1024
    SILENCE_THRESHOLD = 500 
    SILENCE_LIMIT = 1.5
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True, frames_per_buffer=CHUNK)
    print("🎙️ Listening...")
    frames, silent_chunks = [], 0
    max_silent_chunks = int(SILENCE_LIMIT * (rate / CHUNK))
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        if np.abs(np.frombuffer(data, dtype=np.int16)).mean() < SILENCE_THRESHOLD:
            silent_chunks += 1
        else: silent_chunks = 0
        if silent_chunks > max_silent_chunks: break
    stream.stop_stream(); stream.close()
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate); wf.writeframes(b''.join(frames))
    return buf

# --- 6. MAIN LOOP ---
def main():
    # 1. CONNECT TO DRONE
    # Change "0.0.0.0:14550" to your specific connection string if needed
    connect_drone("0.0.0.0:14550")
    
    # 2. WAIT FOR USER CONFIRMATION BEFORE TAKEOFF (Safety)
    input("Press Enter to Arm and Takeoff...")
    arm_and_takeoff(5)

    # 3. WAKE WORD SETUP
    # IMPORTANT: Use Environment Variable for security in production!
    # PORCUPINE_KEY = os.getenv("PORCUPINE_ACCESS_KEY")
    PORCUPINE_KEY = "DxYCbQQDWQAHnXDX4wzNd9i5r7NGYovQ//x+5twQTJQDlOkq2zLeAQ==" 
    keyword_path = "alexa_en_windows_v4_0_0.ppn"
    
    try:
        porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keyword_paths=[keyword_path], sensitivities=[0.95])
    except Exception as e:
        print(f"Failed to initialize Porcupine: {e}")
        return

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)

    print("👂 Assistant active. Say 'Alexa' followed by a drone command.")
    speak("System ready.")

    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length)
            pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
            if vehicle is None or vehicle.mode is None:
                return "No connection"
            if porcupine.process(pcm_unpacked) >= 0:
                # --- SAFETY CHECK BEFORE LISTENING ---
                if vehicle.mode.name != 'GUIDED':
                    print(f"⚠️ Ignored 'Alexa': Drone is in {vehicle.mode.name} mode.")
                    continue 
                
                print("✅ Wake word detected!")
                audio_stream.stop_stream()
                
                audio_data = record_command(pa, porcupine.sample_rate)
                transcript = transcribe_audio(audio_data)
                
                if transcript:
                    print(f"💬 User: {transcript}")
                    process_command(transcript)
                
                audio_stream.start_stream()
                print("\n👂 Waiting for 'Alexa'...")

    except KeyboardInterrupt:
        print("Closing...")
    finally:
        audio_stream.close()
        pa.terminate()
        porcupine.delete()
        if vehicle: vehicle.close()

if __name__ == "__main__":
    main()