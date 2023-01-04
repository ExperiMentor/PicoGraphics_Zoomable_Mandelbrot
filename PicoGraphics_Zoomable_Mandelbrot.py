# Mandelbrot Pico in MicroPython with Zoom - by Hari Wiguna, 2021
# https://github.com/hwiguna/HariFun_202_MandelbrotPico

# Math courtesy of:
# https://www.codingame.com/playgrounds/2358/how-to-plot-the-mandelbrot-set/mandelbrot-set

# Amended by Ian Carbarns, (c)2023 to:
# 1. use PicoGraphics, set for 240 x 240 Pimoroni Pico Explorer display
# 2. multi-colour display, with easily-adjustable number of colours to use
# 3. have "HighRez" operational (temporarily toggles ondoubled resolution)

# Built on a Pimoroni Pico Explorer base, this uses:
# a. The display
# b. The 4 buttons
# c. 3x potentiometers mounted on the breadboard and connected to ADC0, ADC1 and ADC2
# d. Raspberry Pi Pico (Wireless is not needed for this project)

#### Setup pen colours to use. Need adjacent colours to contrast, not be one end of a rainbow.
# With PEN_RGB332, each of R, G, B can be 0-255. But only 3 bits are actually used for R and G and 2 bits for B; max 256 colours in total
# Rather than assigning all 256 colours, it seems better to assign only a few or primary colours and use them repeatedly
pen_colour = [[0,0,0],
              [255,0,0], [0,255,0], [0,0,255], [255,255,0], [255,0,255], [0,255,255], [255,255,255], #1-7
              [128,0,0], [0,128,0], [0,0,128], [128,128,0], [128,0,128], [0,128,128], [128,128,128] ] #8-14 

from picographics import PicoGraphics, DISPLAY_PICO_EXPLORER, PEN_RGB332
import time
import _thread
from pimoroni import Button, Analog

#-- Parameters --

# USER CONTROLS

# Cursor knobs - move the cursor box once the screen has been written
# Zoom knob - changes size of cursor box.
# ZoomIn (button A): redraws screen with area of the cursor boxn
# ZoomOut (button X): redraws twice the area with same centre as currently
# Centre (button B): redraws same size but recentred on centre of cursor box
# HiRez (button Y): temporarily doubles resolution (toggles back). Adds detail into the otherwise blank-looking central area

# USER SETTINGS
MAX_ITER = 15 # low values eg 8 are less intricate, but show pattern better. Above 20-30 make little difference, but draw more slowly
# MAX_ITER is temporarily doubled / restored (toggle) by button Y (HiRez)
print("Max number of Iterations is ", MAX_ITER)

MAX_COLOURS = 10 # will only use the first MAX of the colours specified in the list above
MAX_COLOURS = min(MAX_COLOURS, len(pen_colour)) # limit to number of colours that have been specified
print("Max number of colours (before repeating) is ", MAX_COLOURS)

# Set initial area to display. Mandelbrot sets are based on showing colours corresponding to the number of iterations required
# to get a simple formula (z = z*z +c) to have a value >2, where c is a complex number with co-ordinates (x,y)
# The following parameters are the start and end values to display for the real part of c (X-axis) and the imaginary part of c (Y-axis)
realStart, realEnd = -2.05, 0.55 # -2.05, 1 is nice. Start and End in X direction, but right end looks boring >1
imStart, imEnd = -1.2, 1.2 # Start and End in Y direction; if diff gives assymetric

# SETUP SYSTEM PARAMETERS
# User should not need to change these

# set up the display
display = PicoGraphics(display=DISPLAY_PICO_EXPLORER, rotate=0, pen_type=PEN_RGB332) # 8bit colour as insuf memory for 16bit on larger display
WIDTH, HEIGHT = display.get_bounds() # gets display size, expecting 240, 240
width2 = WIDTH >> 1 #int(WIDTH / 2)
height2 = HEIGHT >> 1 #int(HEIGHT / 2)

# Special colours
WHITE = display.create_pen(255, 255, 255)
BLACK = display.create_pen(0, 0, 0)
#YELLOW = display.create_pen(255, 255, 0)
#PINK = display.create_pen(90, 10, 90)
#RED = display.create_pen(255, 0, 0)
# Otherwise: colour = display.create_pen(r, g, b)

# Assign own framebuffer so we can read from it (to be able to restore colours under cursor when it is moved)
display.set_framebuffer(None)
buffer = bytearray(int(WIDTH*HEIGHT))
display.set_framebuffer(buffer)

# assign storage for colours about to be overwritten by cursor rectangle
top_pix = bytearray(WIDTH)
bottom_pix = bytearray(WIDTH)
left_pix = bytearray(HEIGHT)
right_pix = bytearray(HEIGHT)
top_pix[0], bottom_pix[0], left_pix[0], right_pix[0] = 0,0,0,0

left0, right0, top0, bottom0, left, right, top, bottom = 0,0,0,0,0,0,0,0

results = [False] * HEIGHT # One column of the display. Initialize thread result to all off
resultsReady = False

def mandelbrot(c):
    global MAX_ITER
    mz,n = 0,0 # changed z to mz as z is used elsewhere for zoom
    while abs(mz) <= 2 and n <= MAX_ITER:
        mz = mz*mz + c
        n += 1
    return n

def mandelbrotThreadX(x):
    global MAX_ITER
    global WIDTH, HEIGHT, realStart, realEnd, imStart, imEnd
    global results, resultsReady
    #print("Thread Begin x=",x)
    xx = realStart + (x / WIDTH) * (realEnd - realStart)
    #for y in range(HEIGHT): # IC merged into following loop
        #results[y]=False
    for y in range(HEIGHT):
        results[y]=False
        yy = imStart + (y / HEIGHT) * (imEnd - imStart)
        c = complex(xx, yy) # Convert pixel coordinate to complex number
        m = mandelbrot(c)   # Compute the number of iterations
        colour = int(m - 1) % 15 # restrict to colour 0-15 # int(m - 1) if specifying all 200+ colours
        #print("(",x,y,") m=",m,"colour=",colour)
        results[y] = colour # >0
    resultsReady = True
    #print("Thread Done x=", x)
    _thread.exit() # when done, commit suicide so we could be re-incarnated for next X.

def DrawMandelbrotX():
    global isHiRez, nextRefresh, MAX_ITER
    global results, resultsReady
    print("DRAWINGX: RealStart End", realStart, realEnd, "imStart End", imStart, imEnd)
    stopWatch = time.ticks_ms()
    RE_START = realStart
    RE_END = realEnd
    IM_START = imStart
    IM_END = imEnd

    for x in range(0, WIDTH, 2): # We're drawing two columns at a time. One by the thread, the other by main.
        resultsReady=False # Will be set by thread to True when it's done computing column.
        _thread.start_new_thread(mandelbrotThreadX,(x,))
        
        x1 = x+1
        #print("Main begin x1=",x1)
        xx = RE_START + (x1 / WIDTH) * (RE_END - RE_START)
        for y in range(0, HEIGHT, 1):
            yy = IM_START + (y / HEIGHT) * (IM_END - IM_START)
            c = complex(xx, yy) # Convert pixel coordinate to complex number
            m = mandelbrot(c)   # Compute the number of iterations for that pixel
            colour = int(m - 1) % MAX_COLOURS # restrict to colour 0-MAX # int(m - 1) if specifying all 200+ colours
            if colour > 0:
                display.set_pen(display.create_pen(pen_colour[colour][0], pen_colour[colour][1], pen_colour[colour][2]))
                display.pixel(x1,y)
        #print("Main End x1=",x1)
                   
        #stopwatchStart = time.ticks_ms()
        while not resultsReady:
            pass
        #print("waited ", time.ticks_ms()-stopwatchStart, "ms")
        
        # Plot the X column computed by the thread
        for y in range(HEIGHT):
            # brotFB.pixel(x,y, 1 if results[y] else 0)
            if results[y]:
                display.set_pen(display.create_pen(pen_colour[results[y]][0], pen_colour[results[y]][1], pen_colour[results[y]][2]))
                display.pixel(x,y)

        if x % 2 == 0: # No need to refresh everytime we go through X loop
            display.update()

    display.update()
    
def Setup():
    global mPot0, mPot1, mZoomPot
    global buttonZoomIn, buttonZoomOut, buttonCenter, buttonRez
    
    print("Starting Setup()")
    mPot0 = Analog(26) # X axis
    mPot1 = Analog(27) # Y axis
    mZoomPot = Analog(28) # Zoom
    
    buttonZoomIn =  Button(12) # button A
    buttonCenter =  Button(13) # button B
    buttonZoomOut = Button(14) # button X
    buttonRez =     Button(15) # button Y
 
def getCursorX(pot):
    global WIDTH
    return int(pot.read_voltage() / 3.3 * WIDTH)

def getCursorY(pot):
    global HEIGHT
    return int((HEIGHT - (pot.read_voltage() / 3.3 * HEIGHT) ) )

def getZoomLevel(pot):
    global HEIGHT, WIDTH
    return int(pot.read_voltage() / 3.3 * min(HEIGHT, WIDTH))

def MoveCursor():
    # This resizes and re-displays screen cursor rectangle, plot is not recomputed until a button is pressed
    # ie is showing where the pots are set to; pressing button a button actions those positions
    global nextSensorRead
    global left0, right0, top0, bottom0 # previous positions
    global left, right, top, bottom
    global buffer
    global WIDTH, HEIGHT
    global x0, y0, z # centre of cursor; zoom
    global newHeight, newWidth # half height & width of cursor box

    if time.ticks_ms() >= nextSensorRead:          
        # Process zoom first as need newHeight and newWidth of cursor to ensure it does not go out of bounds
        z = getZoomLevel(mZoomPot)
        newHeight = int(z / 2) # new cursor height (halved)
        newWidth = int((z * WIDTH / HEIGHT) / 2) # make cursor same aspect ratio as display
        
        # x0, y0 are MIDDLE of cursor rectangle
        x0 = getCursorX(mPot0)
        x0 = max(newWidth, x0) # Ensure not off left
        x0 = min(x0, WIDTH -1 - newWidth) # Ensure not off right
        
        y0 = getCursorY(mPot1)
        y0 = max(newHeight, y0) # Ensure not off top
        y0 = min(y0, HEIGHT -1 - newHeight) # Ensure not off bottom
        
        left, right = x0-newWidth, x0+newWidth
        top, bottom = y0-newHeight, y0+newHeight
        #print("NewCursor (x0, y0) (", x0, ",", y0, ") Zoom: ", z)
        #print("Left, Right, Top, Bottom:", left, right, top, bottom)

        # if cursor rectangle has changed
        if left0 != left or right0 != right or top0 != top or bottom0 != bottom:
            # restore previous cursor rectangle outline 
            if left0 + right0 + top0 + bottom0 != 0: # don't restore if there isn't a previous cursor
                #print("Restoring previous cursor rectangle")
                #print("Prev cursor: left0, right0, top0, bottom0:", left0, right0, top0, bottom0)
                for i in range(right0 - left0 +1): 
                    buffer[left0 + i -1 + (top0 * WIDTH)] = top_pix[i] # -1 is to allow for corner pixel being stored once
                    buffer[left0 + i + (bottom0 * WIDTH)] = bottom_pix[i] 
                for i in range(bottom0 - top0 +1):
                    buffer[left0 + ((top0 + i) * WIDTH)] = left_pix[i]
                    buffer[right0 + ((top0 + i -1) * WIDTH)] = right_pix[i]
            #else:
                #print("NOT RESTORING previous cursor rectangle", left0, right0, top0, bottom0)
                        
            # store new cursor rectangle outline
            #print("New cursor: left, right, top, bottom:", left, right, top, bottom)
            for i in range(right - left +1):
                top_pix[i] = buffer[left + i -1 + (top * WIDTH)] # -1 is to allow for corner pixel being stored once
                bottom_pix[i] = buffer[left + i + (bottom * WIDTH)]  
            for i in range(bottom - top +1):
                left_pix[i] = buffer[left + ((top + i) * WIDTH)]
                right_pix[i] = buffer[right + ((top + i -1) * WIDTH)]
                
            # draw cursor rectangle outline
            display.set_pen(WHITE)
            display.line(left,top,      right,top)
            display.line(right,top,     right,bottom)
            display.line(left, bottom,  right,bottom)
            display.line(left,top,      left,bottom)
            
            display.update()
            left0, right0, top0, bottom0 = left, right, top, bottom # store current values 
        
        nextSensorRead = time.ticks_ms() + 100

def ZoomIn():
    global mPot0, mPot1, mZoomPot
    global buttonZoomIn, buttonZoomOut, buttonCenter
    global realStart, realEnd, imStart, imEnd #????
    global x0, y0, z # centre of cursor; zoom
    global WIDTH, HEIGHT, newWidth, newHeight
    global left, right, top, bottom

    pressed = buttonZoomIn.is_pressed
    if pressed:
        print("BEFORE ZOOM IN: RealStart End", realStart, realEnd, "imStart End", imStart, imEnd)
        # Amended to use values already stored rather than looking at pots again
        print("z=", z, "newWidth=", newWidth, "newHeight", newHeight)
        realRange = realEnd-realStart
        imRange = imEnd-imStart
        realStart = realStart + (realRange*left/WIDTH)
        realEnd = realStart + (right-left)*realRange/WIDTH
        imStart = imStart + (imRange*top/HEIGHT)
        imEnd = imStart + (bottom-top)*imRange/HEIGHT
        print(" AFTER ZOOM IN: RealStart End", realStart, realEnd, "imStart End", imStart, imEnd)
        time.sleep_ms(500) # Allow human to release button
    return pressed

def ZoomOut():
    global realStart, realEnd, imStart, imEnd #????
    pressed = buttonZoomOut.is_pressed
    if pressed:
        print("BEFORE ZOOM OUT: RealStart End", realStart, realEnd, "imStart End", imStart, imEnd)
        zoomDelta = 2
        realRange, imRange = realEnd-realStart, imEnd-imStart
        realDelta, imDelta = realRange/zoomDelta, imRange/zoomDelta
        left, right = realStart-realDelta, realEnd+realDelta
        top, bottom = imStart-imDelta, imEnd+imDelta
        realStart = left
        realEnd = right
        imStart = top
        imEnd = bottom
        print(" AFTER ZOOM OUT: RealStart End", realStart, realEnd, "imStart End", imStart, imEnd)
        time.sleep_ms(500) # Allow human to release button
    return pressed

def ChangeRez():
    global buttonRez, isHiRez, MAX_ITER
    pressed = buttonRez.is_pressed
    if pressed:
        isHiRez = not isHiRez
        if isHiRez:
            MAX_ITER = MAX_ITER *2
        else:
            MAX_ITER = MAX_ITER /2
        print("isHiRez=", isHiRez)
        time.sleep_ms(500) # Allow human to release button
    return pressed

def ButtonPressed():
    pressed = ChangeRez() or Center() or ZoomIn() or ZoomOut()
    return pressed

def Center():
    global mPot0, mPot1
    global realStart, realEnd, imStart, imEnd #????
    
    pressed = buttonCenter.is_pressed
    if pressed:
        print("BEFORE CENTER: RealStart End", realStart, realEnd, "imStart End", imStart, imEnd)
        realRange, imRange  = realEnd-realStart, imEnd-imStart
        print("Ranges:",realRange, imRange)
        #width2, height2 = WIDTH/2, HEIGHT/2 # these should have been set at start of prog, so not needed here???
        xDelta = getCursorX(mPot0) - width2
        yDelta = getCursorY(mPot1) - height2
        print("Cursors:",getCursorX(mPot0) , getCursorY(mPot1) ) # Don't like re-reading, Shoukd use a stored value
        print("Screen Deltas:",xDelta, yDelta)
        realDelta, imDelta = (realRange*xDelta/WIDTH), (imRange*yDelta/HEIGHT)
        print("Mandel Deltas:",realDelta, imDelta)
        realStart = realStart + realDelta
        realEnd = realEnd + realDelta
        imStart = imStart + imDelta
        imEnd = imEnd + imDelta
        print(" AFTER CENTER: RealStart End", realStart, realEnd, "imStart End", imStart, imEnd)
    return pressed

def Loop():
    #print("Starting Loop()")
    global mPot0, mPot1, mZoomPot
    global buttonZoomIn, buttonZoomOut, buttonCenter
    global nextSensorRead, nextRefresh, lastX0, lastY0
    global isHiRez
    global left0, right0, top0, bottom0
    global left_pix, right_pix, top_pix, bottom_pix
    
    isHiRez = False
    nextSensorRead, nextRefresh =-1,-1
    lastX0, lastY0 = -1024,-1024

    while True:
        print("Starting DrawMandelbrotX()")
        # Clear screen
        display.set_pen(BLACK)
        display.clear()
        display.update()
        
        # reset previous cursor
        left0, right0, top0, bottom0 = 0,0,0,0
        top_pix[0], bottom_pix[0], left_pix[0], right_pix[0] = 0,0,0,0        
    
        DrawMandelbrotX()
        while not ButtonPressed():
            MoveCursor()

def main():
    Setup()
    Loop()

# Run program
main()
