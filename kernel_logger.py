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
import os

DIR_OUTPUT = "kernel_log"

class Device:
    __slots__ =  ['id', 'commonName', 'baud', 'timeout', 'ser']
    def __init__(self,  id, commonName, baud, timeout, ser):
        self.id = id
        self.commonName = commonName
        self.baud = baud
        self.timeout = timeout
        self.ser = ser

class RadTestController():

    def __init__(self, arduinoPort):
        self.windows = False
        self.unix = False
        self.fd = None
        self.old_settings = None

        self.arduino = Device(id=arduinoPort, commonName='Arduino', baud=9600, timeout=1, ser=None)
        
        if not os.path.exists(DIR_OUTPUT):
            os.makedirs(DIR_OUTPUT)

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

    def __connect_arduino(self):
        print("Connecting to Arduino...")
        self.__connect_device(self.arduino)
        print("Connected!\n")

    def connect(self):
        self.__connect_arduino()

    def __disconnect_arduino(self):
        if self.arduino.ser != None:
            print("Disconnecting from Arduino...")
            self.arduino.ser.close()
            self.arduino.ser = None
            print("Disconnected!")

    def disconnect(self):
        self.__disconnect_arduino()

    def run(self, errorFile):
        self.arduino.ser.flushInput()

        self.currentFilename = DIR_OUTPUT + "/output_" + str(int(time.time())) + ".txt"
        
        with open(self.currentFilename, 'w') as outputFile:
            while True:
                if not self.input_queue.empty():
                    keyboardInput = self.input_queue.get()
                    if ord(keyboardInput) == 27: # Escape key
                        self.stop_queue.put('stop')
                        self.cleanUp()
                        sys.exit(1)

                # Check for Arduino output:
                try:
                    lineBytes = self.arduino.ser.readline()
                    line = lineBytes.decode('utf-8').strip()
                    if line == '':
                        pass
                    else:
                        print("RECEIVED: " + line)
                        outputFile.write(line + "\n")
                except IOError as e:
                    raise e
                except:
                    errorInfo = "GENERAL ERROR"
                    print(errorInfo)
                    errorFile.write("[" + str(int(time.time())) + "]" + errorInfo + "\n")

# end RadTestController

# MAIN

if len(sys.argv) <= 1:
    print("\nUsage:")
    print("rad_test_controller.py <arduino port>\n")
    exit(1)

controller = RadTestController(sys.argv[1])

with open("output/errors.txt", 'w') as errorFile:
    while True:
        try:
            time.sleep(1) # Delay one second
            controller.connect()
            controller.run(errorFile)
        except serial.SerialException:
            print ("Error: Disconnected (Serial exception)")
            errorFile.write("Serial Exception: " + str(int(time.time())) + "\n")
        except IOError as e:
            print ("Error: Disconnected (I/O Error)")
            errorFile.write("IO Error: " + str(int(time.time())) + "\n")
        except KeyboardInterrupt:
            print ("Keyboard Interrupt. Exiting Now...")
            break

        controller.disconnect()
    # end while