#!/usr/bin/env python

# Source: https://github.com/adamwtow/python-serial-monitor

# Some of this monitor was made possible with help from those at:
# http://shallowsky.com/blog/hardware/ardmonitor.html
# http://code.activestate.com/recipes/134892/

import sys
import threading
import time
import serial
import queue

SIGNAL_HEARTBEAT = "HEARTBEAT" # no \n for checking incoming signals because of newline inconsistencies (\r\n vs \n vs \r)
SIGNAL_POWER_CYCLE = "POWER_CYCLE\n" # \n for outgoing signal

class Device:
    __slots__ =  ['id', 'commonName', 'baud', 'timeout', 'ser']
    def __init__(self,  id, commonName, baud, timeout, ser):
        self.id = id
        self.commonName = commonName
        self.baud = baud
        self.timeout = timeout
        self.ser = ser

class RadTestController():

    def __init__(self):
        self.windows = False
        self.unix = False
        self.fd = None
        self.old_settings = None

        self.tx2 = Device(id='COM7', commonName='TX2', baud=9600, timeout=5, ser=None)
        self.arduino = Device(id='COM8', commonName='Arduino', baud=9600, timeout=1, ser=None)

        self.heartbeatReceived = False

        try:
            # Windows
            import msvcrt
            self.windows = True
        except ImportError:
            # Unix
            import sys, tty, termios
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            self.unix = True

        self.input_queue = queue.Queue()
        self.stop_queue = queue.Queue()
        self.pause_queue = queue.Queue()

        self.input_thread = threading.Thread(target=self.add_input, args=(self.input_queue,self.stop_queue,self.pause_queue,))
        self.input_thread.daemon = True
        self.input_thread.start()

    def getch(self):
        if self.unix:
            import sys, tty, termios
            try:
                tty.setcbreak(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            return ch
        if self.windows:
            import msvcrt
            return msvcrt.getch()

    def cleanUp(self):
        if self.unix:
            import sys, tty, termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def add_input(self, input_queue, stop_queue, pause_queue):
        while True:
            input_queue.put(self.getch())
            if not pause_queue.empty():
                if pause_queue.get() == 'pause':
                    while True:
                        if not pause_queue.empty():
                            if pause_queue.get() == 'resume':
                                break
            if not stop_queue.empty():
                if stop_queue.get() == 'stop':
                    break

    def __checkEscape(self):
        while True:
            if not self.input_queue.empty():
                keyboardInput = self.input_queue.get()
                if ord(keyboardInput) == 27:
                    self.stop_queue.put('stop')
                    self.cleanUp()
                    sys.exit(1)
                else:
                    # Pressing any key other than 'esc' will continue the monitor
                    break
                        
    def __connect_device(self, device):
        while not device.ser:
            try:
                device.ser = serial.Serial(device.id, device.baud, timeout=device.timeout)
            except:
                device.ser = None
                pass

            if not device.ser:
                print("ERROR: Unable to connect to " + device.commonName + " at " + device.id)
                print("Retrying...")

                time.sleep(1) # Wait 1 seconds before retrying

                if not self.input_queue.empty():
                    keyboardInput = self.input_queue.get()
                    if ord(keyboardInput) == 27:
                        self.stop_queue.put('stop')
                        self.cleanUp()
                        sys.exit(1)
                    else:
                        # Pressing any key other than 'esc' will continue the monitor
                        break

    def __connect_tx2(self):
        print("Connecting to TX2...")
        self.__connect_device(self.tx2)
        print("Connected!\n")

    def __connect_arduino(self):
        print("Connecting to Arduino...")
        self.__connect_device(self.arduino)
        print("Connected!\n")

    def connect(self):
        self.__connect_tx2()
        self.__connect_arduino()

    def __disconnect_tx2(self):
        if self.tx2.ser != None:
            print("Disconnecting from TX2...")
            self.tx2.ser.close()
            self.tx2.ser = None
            print("Disconnected!")

    def __disconnect_arduino(self):
        if self.arduino.ser != None:
            print("Disconnecting from Arduino...")
            self.arduino.ser.close()
            self.arduino.ser = None
            print("Disconnected!")

    def disconnect(self):
        self.__disconnect_tx2()
        self.__disconnect_arduino()

    def __cycle_power(self):
        self.__disconnect_tx2()

        print("Sending POWER_CYCLE signal...\n")
        self.arduino.ser.write(SIGNAL_POWER_CYCLE.encode('utf-8'))

        self.__connect_tx2()

    def run(self):
        self.tx2.ser.flushInput()
        self.arduino.ser.flushInput()

        while True:
            if not self.input_queue.empty():
                keyboardInput = self.input_queue.get()
                if ord(keyboardInput) == 27: # Escape key
                    self.stop_queue.put('stop')
                    self.cleanUp()
                    sys.exit(1)
                elif ord(keyboardInput) == 13: # Enter key
                    # Manuall cycle power
                    self.__cycle_power()

            # Check for TX2 output:
            try:
                lineBytes = self.tx2.ser.readline()
                line = lineBytes.decode('utf-8').strip()
                if line == '':
                    if self.heartbeatReceived: # Only start caring about the TX2 once we've received a heartbeat signal
                        # TX2 Not Responding
                        print("\nERROR: TX2 Not Responding\n")
                        self.__cycle_power()
                elif line == SIGNAL_HEARTBEAT:
                    self.heartbeatReceived = True
                else:
                    print("RECEIVED: " + line)
            except IOError as e:
                # Manually raise the error again so it can be caught outside of this method
                raise e


# MAIN

controller = RadTestController()

while True:
    try:
        time.sleep(1) # Delay one second
        controller.connect()
        controller.run()
    except serial.SerialException:
        print ("Error: Disconnected (Serial exception)")
    except IOError as e:
        print ("Error: Disconnected (I/O Error)")
    except KeyboardInterrupt:
        print ("Keyboard Interrupt. Exiting Now...")
        break

    controller.disconnect()
