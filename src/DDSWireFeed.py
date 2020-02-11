
from inco_32 import *
import time
import sys
import os
from Tkinter import *
    

# The target name
TargetRoot = "LocalSAM"
# Count of measurements to perform
# time to wait between axis moves.
g_uSleepTimeInSec = 0.2 # [ms]
g_speedSet = 15

def DoMoveSS(Axis,Position,SpeedSet):
        CallProcedure(TargetRoot, "Axis." +str(Axis)+ ".Cmd.ActivateMoveParam(" + str(SpeedSet)+ ":l)")
        DoMove(Axis,Position)
        
def DoMove(Axis,Position):
        CallProcedure(TargetRoot, "Axis." + str(Axis) + ".Cmd.Move(" + str(Position) + ":d)")
        

def WireFeed():
		CallProcedure(TargetRoot, "Axis.DDSSys1WDHWireFeed.Cmd.Test.Zero()")
		pos = 0.000
		len = float(entryMoveLength.get())
		cnt = int(entryMoveCount.get())
		DoMoveSS("DDSSys1WDHWireFeed", pos,15)
		for i in range(cnt):
				time.sleep(0.2)
				pos -= len
				DoMoveSS("DDSSys1WDHWireFeed", pos,15)
	


	
Main = Tk()
frame=Frame(Main)



    
Font='\'arial\', 16'
font='\'arial\', 8'
Main.title("Wire Feed Test")
windowExists=0                 

BtnStartTest = Button(master=Main, text='Start', command=WireFeed ,justify=LEFT)
BtnStartTest.grid(row=1, column=1)
BtnStartTest.config(font=(font))


entryStripLengthstext = Label(master=Main)
entryStripLengthstext['text']= "Move Length:"
entryStripLengthstext.grid(row=3, column=1, columnspan=1)
entryStripLengthstext.config(font=(font))

entryMoveLength = Entry(master=Main)
entryMoveLength.grid(row=3, column=2, columnspan=1)
entryMoveLength["text"] = "Move Length:"
entryMoveLength.config(font=(font))
entryMoveLength.delete(0, END)
entryMoveLength.insert(0, "0.001")

entryStripLengthstext = Label(master=Main)
entryStripLengthstext['text']= "m"
entryStripLengthstext.grid(row=3, column=3, columnspan=1)
entryStripLengthstext.config(font=(font))

entryMoveCountText = Label(master=Main)
entryMoveCountText['text']= "Move Count:"
entryMoveCountText.grid(row=4, column=1, columnspan=1)
entryMoveCountText.config(font=(font))

entryMoveCount = Entry(master=Main)
entryMoveCount.grid(row=4, column=2, columnspan=1)
entryMoveCount["text"] = "Move Count:"
entryMoveCount.config(font=(font))
entryMoveCount.delete(0, END)
entryMoveCount.insert(0, "10")




Main.mainloop()

 
