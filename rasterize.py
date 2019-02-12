# Kyle McGrath 2019
# Commission for Scott Young
# MINUS ONE

from __future__ import print_function
print('Libraries loading:\n')
from PIL import ImageFont, ImageDraw, Image
from Adafruit_Thermal import *
import RPi.GPIO as GPIO
import smbus
import subprocess, time, socket
import traceback
import numpy as np
import requests
import pickle
import datetime
import os
print('Libraries loaded.')

#logging.basicConfig(filename='traceback.log', level=os.environ.get("LOGLEVEL", "INFO"))

# GPIO configuration
ledPin       = 18
buttonPin    = 23
holdTime     = 10
tapTime      = 0.01
nextInterval = 0.0
dailyFlag    = False
lastId       = '1'
printer      = Adafruit_Thermal('/dev/serial0', 19200, timeout=5)

# Arduino GPIO connection
bus = smbus.SMBus(1)
address = 0x04

i2cID = {'wifi_on'  : 11,
         'wifi_off' : 42,
         'loading'  : 69,
         'printing' : 44}

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT) # Program status wire
bus.write_byte(address, i2cID['loading'])

# Set connection, printer, and image layout variables
ip           = 'minus1.net'
local_ip     = 'http://localhost:3000'
port         = '5000'
host         = ('http://' + ip + '/press')
upper_text   = "There are"
bottom1_text = "humans in my way"
bottom2_text = "of finding you."
handle       = '@scottyoung11'
dim_x        = 1380
dim_y        = 660
padding_l    = 20
padding_r    = dim_x - 50
line_height  = 305
channels     = 3
black        = (0,0,0,255)
buttonid     = 0

workingDir = sys.path[0]

# Dashed line spec
steps       = 68
line_size   = 30
step_length = (padding_r-padding_l)/steps

# Import truetype fonts
helveticaneue  = ImageFont.truetype(os.path.join(workingDir, 'fonts/helveticaneue/HelveticaNeueBd.ttf'), 90)
major_mono_reg = ImageFont.truetype(os.path.join(workingDir, 'fonts/major_mono_display/MajorMonoDisplay-Regular.ttf'), 90)
teko_med       = ImageFont.truetype(os.path.join(workingDir, 'fonts/teko/Teko-Medium.ttf'), 200)
teko_reg       = ImageFont.truetype(os.path.join(workingDir, 'fonts/teko/Teko-Regular.ttf'), 50)
teko_sign      = ImageFont.truetype(os.path.join(workingDir, 'fonts/teko/Teko-Regular.ttf'), 60)


def tap():
    bus.write_byte(address, i2cID['printing'])
    pop, status = grab_population()
    print('got button request at population: ', pop)
    population_img = create_image(pop)
    # printer.printImage(pil_im)
    population_img.save('/tmp/bittest.bmp', 'PNG')
    subprocess.call(["lp", "-o", "fit-to-page", "/tmp/bittest.bmp"])
    time.sleep(20)
    if status:
      print('wifi on status sent')
      bus.write_byte(address, i2cID['wifi_on'])
    else:
      print('wifi off status sent')
      bus.write_byte(address, i2cID['wifi_off'])


# Called when button is held down.  Prints image, invokes shutdown process.
def hold():
    bus.write_byte(address, i2cID['loading'])
    print('button held')
    printer.println('SHUTTING DOWN')
    printer.feed(3)
    subprocess.call("sync")
    GPIO.cleanup()
    #subprocess.call(["shutdown", "-h", "now"])

def save_last_pop(population):
    currentDate = datetime.datetime.now()
    currentStatus = [population, currentDate]
    with open(os.path.join(workingDir, 'lastpop.pckl'), 'wb') as f:
        pickle.dump(currentStatus, f)
        f.close()

def load_last_pop():
    with open(os.path.join(workingDir, 'lastpop.pckl'), 'rb') as f:
        pop, date = pickle.load(f)
        f.close()
    print('last population: ', pop, ' at time: ', date)
    return pop, date

def local_interpolation():
    global lastDate, lastPop
    birthRate = 2.597982
    timeChange = (datetime.datetime.now() - lastDate).seconds
    popEstimate = int(round((timeChange*birthRate) + lastPop))
    print('population estimate: ', popEstimate)
    return popEstimate

def grab_population():
    # Define which device is sending
    payload = {'button': buttonid}
    global lastPop

    try:
        # Grab population from remote server, subtract one *wink wink*
        population_get = requests.get(host, params=payload, timeout=2)
        population = int(population_get.text)
        save_last_pop(population)
        print (population_get.url)
        connection = True

    except requests.exceptions.ConnectionError as errc:
        population = local_interpolation()
        #lastPop = lastPop + 19
        # Add I2C status??
        print('connectionError, set population: ', population, '\n', errc)
        connection = False
    except requests.exceptions.Timeout as errt:
        population = local_interpolation()
        print('timeout error, set population: ', population, '\n', errt)
        connection = False
    except requests.exceptions.HTTPError as errh:
        population = local_interpolation()
        print('timeout error, set population: ', population, '\n', errh)

    except requests.exceptions.RequestException as e:
        print (e)

    # add thousandths commas, replace with periods.
    population = '{:,}'.format(population)

    # just add commas
    #population = '{:,}'.format(population)

    #population = population.replace(',', '.')
    return population, connection

def create_image(population):
    # Create blank array, fill white
    img = np.zeros((dim_y, dim_x, channels), dtype=np.uint8)
    img.fill(255)

    # Convert to Pillow image, initialize drawing object
    pil_im = Image.fromarray(img)
    draw = ImageDraw.Draw(pil_im)

    # Grab time/date
    currentTime = str(datetime.datetime.now()).split(' ')

    draw.text((padding_l, 50), upper_text, font=helveticaneue, fill=black, width = 2)
    draw.text((padding_l, 340), bottom1_text, font=helveticaneue, fill=black, width = 2)
    draw.text((padding_l, 440), bottom2_text, font=helveticaneue, fill=black, wdith = 2)


    draw.text((padding_l, 600), currentTime[0], font=teko_reg, fill=black, width = 1)
    draw.text((padding_l + 300, 600), currentTime[1], font=teko_reg, fill=black, width=1)
    draw.text((padding_l + 1100, 600), 'minus1.net', font=teko_sign, fill=black, width=1)

    # Draw population from webserver in Teko
    draw.text((padding_l, 120), population, font=teko_med, fill=black, width=1)

    # Straight lines
    #draw.line([(padding_l, line_height), (dim_x, line_height)], fill=black, width=3)
    #draw.line([(padding_l, line_height+15), (dim_x, line_height+15)], fill=black, width=3)

    # dashed line for the win!
    #for i in range(steps):
    #    spacer = step_length*i

        # 45 degree
        #draw.line([(padding_l + line_size + spacer, 300), (padding_l + spacer, 300+line_size)],
	#	 fill=black, width=3)

        # 135 degree
        #draw.line([(padding_l+spacer, line_height), (padding_l+line_size+spacer, line_height+line_size)],
	#	 fill=black, width=3)
    return pil_im

def epic_fail():
  subprocess.call("sync")
  GPIO.output(ledPin, GPIO.HIGH)
  GPIO.cleanup()
  raise ValueError('SHUTDOWN')

def create_lastpop():
    pickleDir = os.path.join(workingDir, 'lastpop.pckl')
    try:
        with open (pickleDir, 'rb') as f:
            print('------file exists------')
            if os.stat(pickleDir).st_size == 0:
                print('file is empty')
                f.close()
                raise IOError
            else:
                print('file is not empty')
                f.close()

    except IOError:
        print('-------creating file-------')
        with open (pickleDir, 'wb') as f:
            fakePop = 7683435471
            currentDate = datetime.datetime.now()
            currentStatus = [fakePop, currentDate]
            pickle.dump(currentStatus, f)
            f.close()


def main_button_loop():
    global lastPop, lastDate
    global serverStatus

    create_lastpop()

    lastPop, lastDate = load_last_pop()

    GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    time.sleep(5)

    local_interpolation()

    # Poll initial button state and time
    prevButtonState = GPIO.input(buttonPin)
    prevTime        = time.time()
    tapEnable       = False
    holdEnable      = False

    popTest, serverStatus = grab_population()
    print('ready: ', popTest, ' wifi: ', serverStatus)

    if serverStatus:
      bus.write_byte(address, i2cID['wifi_on'])
    else:
      bus.write_byte(address, i2cID['wifi_off'])

    # Main loop
    while(True):
      # Poll current button state and time
      buttonState = GPIO.input(buttonPin)
      t           = time.time()

      GPIO.output(17, GPIO.HIGH)

      # Has button state changed?
      if buttonState != prevButtonState:
        prevButtonState = buttonState   # Yes, save new state/time
        prevTime        = t
      else:                             # Button state unchanged
        if (t - prevTime) >= holdTime:  # Button held more than 'holdTime'?
          # Yes it has.  Is the hold action as-yet untriggered?
          if holdEnable == True:        # Yep!
            hold()                      # Perform hold action (usu. shutdown)
            holdEnable = False          # 1 shot...don't repeat hold action
            tapEnable  = False          # Don't do tap action on release
        elif (t - prevTime) >= tapTime: # Not holdTime.  tapTime elapsed?
          # Yes.  Debounced press or release...
          if buttonState == True:       # Button released?
            if tapEnable == True:       # Ignore if prior hold()
              tap()                     # Tap triggered (button released)
              tapEnable  = False        # Disable tap and hold
              holdEnable = False
          else:                         # Button pressed
            tapEnable  = True           # Enable tap and hold actions
            holdEnable = True


def main():
    try:
        print('trying main')
        main_button_loop()
        return 0

    except KeyboardInterrupt:
        print('error: KeyboardInterrupt')
        GPIO.cleanup()
        time.sleep(2)
        return 1

    except Exception, err:
        print('error: (should highlight)')

        print(err)
        traceback.print_exc()
        GPIO.cleanup()
        return 1

    finally:
        print('cleanup')
        GPIO.cleanup()
        print('GPIO cleanup')
        return 1


if __name__ == "__main__":
    sys.exit(main())
