#
# lensometer
#
import numpy as np
import cv2
import math
import array
import datetime
import glob
import sys
import argparse


lenses_data = {
'+1' : (1,0,0),
'+2' : (2,0,0),
'-2' : (-2,0,0),
'-3' : (-3,0,0),
"""
'+0,5+1,75' : (0.5,1.75,0),
'+0,25-0,25' : (0.25,-0.25,0),
'+2,5+1,75' : (2.5,1.75,0),
'+2-2' : (2.0,-2.0,0),
'-3,75-2,25' : (-3.75,-2.25,0),
'-3-0,75' : (-3.0,-0.75,0),
'-1-1,75' : (-1.0,-1.75,0),
'-4-0,5' : (-4.0,-0.5,0)
"""
}

            
                            
# for testing lesometer algoritm
if __name__ == '__main__':  
    print('Process lenses')
    for v in lenses_data.keys():
        print('for ',v)
      

