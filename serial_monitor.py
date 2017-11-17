#!/bin/bash

import os
import pty
import select
import serial
import sys
import threading
import time

def out(msg):
    print(msg)
    sys.stdout.flush()

# child process
def serial_select():
    time.sleep(1)

    out("CHILD THREAD: connecting to serial {}".format(serial_name))
    conn = serial.Serial(serial_name, timeout=0)
    conn.nonblocking()

    out("CHILD THREAD: selecting on serial connection")
    avail_read, avail_write, avail_error = select.select([conn],[],[], 7)
    out("CHILD THREAD: selected!")

    output = conn.read(0x100)
    out("CHILD THREAD: output was {!r}".format(output))

    out("CHILD THREAD: normal read serial connection, set timeout to 7")
    conn.timeout = 7

    # len("GOODBYE FROM MAIN THREAD") == 24
    # serial.Serial.read will attempt to read NUM bytes for entire
    # duration of the timeout. It will only return once either NUM
    # bytes have been read, OR the timeout has been reached
    output = conn.read(len("GOODBYE FROM MAIN THREAD"))
    out("CHILD THREAD: read data! output was {!r}".format(output))

master, slave = pty.openpty()
serial_name = os.ttyname(slave)

child_thread = threading.Thread(target=serial_select)
child_thread.start()

out("MAIN THREAD: sleeping for 5")
time.sleep(5)

out("MAIN THREAD: writing to serial")
os.write(master, "HELLO FROM MAIN THREAD")

out("MAIN THREAD: sleeping for 5")
time.sleep(5)

out("MAIN THREAD: writing to serial")
os.write(master, "GOODBYE FROM MAIN THREAD")

child_thread.join()